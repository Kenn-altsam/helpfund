
import json
import time
import uuid
from typing import Dict, Optional, Any
from sqlalchemy.orm import Session

import google.generativeai as genai
from google.generativeai import types

from ..core.config import get_settings
from ..companies.service import CompanyService
from ..auth.models import User
from ..chats import service as chat_service


class GeminiFundAssistant:
    def __init__(self):
        self.settings = get_settings()
        # TODO: Consider instantiating the genai Client once at application startup to avoid repeated auth overhead
        self.client = genai.Client(api_key=self.settings.GEMINI_API_KEY)

        # Using JSON schema declarations; parameters_json_schema ensures strict validation
        search_fn = types.FunctionDeclaration(
            name="search_companies",
            description="Searches for companies by name and location",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "company_name": {"type": "string", "description": "Company name to search for"},
                    "location": {"type": "string", "description": "Location to search in"},
                    "activity_keywords": {"type": "string", "description": "Keywords for company activity"},
                    "limit": {"type": "integer", "description": "Max results to return", "default": 50},
                    "page": {"type": "integer", "description": "Page number for pagination", "default": 1},
                },
                "required": ["company_name"],
            },
        )

        details_fn = types.FunctionDeclaration(
            name="get_company_details",
            description="Get details for a company by ID",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "company_id": {"type": "string", "description": "ID of the company"},
                },
                "required": ["company_id"],
            },
        )

        # TODO: Extract chat_config to a constant or config file if reused across multiple assistants
        self.chat_config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[search_fn, details_fn])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    def _call_model_with_backoff(self, prompt: str) -> types.GenerateContentResponse:
        """Calls the Gemini API with simple backoff; consider using a retry library for exponential backoff"""
        time.sleep(1)
        # FIXME: Creating a new chat per request may add latency; consider reusing chat sessions for context
        chat = self.client.chats.create(
            model=self.settings.GEMINI_MODEL_NAME,
            config=self.chat_config,
        )
        return chat.send_message(prompt)

    def handle_tool_call(self, tool_call: types.FunctionCall, db: Session, chat_id: Optional[uuid.UUID]) -> Dict[str, Any]:
        name = tool_call.name
        args = tool_call.args or {}
        # Consider mapping function names to handlers via a dict to avoid if/elif chains
        if name == "search_companies":
            return self.search_companies_tool(args, db, chat_id)
        if name == "get_company_details":
            return self.get_company_details_tool(args, db)
        return {"error": f"Unknown tool: {name}"}

    def search_companies_tool(self, args: Dict[str, Any], db: Session, chat_id: Optional[uuid.UUID]) -> Dict[str, Any]:
        # Validation: ensure args contain required keys; pydantic could simplify this
        service = CompanyService(db)
        limit = int(args.get("limit", 50))
        page = self._calculate_page(args, db, chat_id)
        items = service.search_companies(
            location=args.get("location"),
            company_name=args.get("company_name"),
            activity_keywords=args.get("activity_keywords"),
            limit=limit,
            offset=(page - 1) * limit,
        )
        return {
            "companies": items,
            "total_found": len(items),
            "search_criteria": args,
            "page": page,
            "limit": limit,
        }

    def get_company_details_tool(self, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
        service = CompanyService(db)
        company = service.get_company_by_id(args.get("company_id"))
        return company or {"error": "Company not found."}

    def _calculate_page(self, args: Dict[str, Any], db: Session, chat_id: Optional[uuid.UUID]) -> int:
        # Simplify pagination logic by defaulting page to 1; chat history dependency might leak context
        if args.get("page") is not None:
            return int(args["page"])
        if chat_id:
            prev = chat_service.count_search_requests(db, chat_id)
            return max(1, prev)
        return 1


def handle_conversation_with_context(
    user_input: str,
    db: Session,
    user: User,
    chat_id: Optional[uuid.UUID] = None,
    assistant_id: Optional[str] = None,
) -> Dict[str, Any]:
    assistant = GeminiFundAssistant()
    chat = chat_service.get_chat_by_id(db, chat_id, user.id) if chat_id else None
    if not chat:
        # Consider unifying chat creation logic to avoid duplication
        chat = chat_service.create_chat(db=db, user_id=user.id, name=user_input[:50])
    chat_service.create_message(db, chat_id=chat.id, content=user_input, role="user")

    resp = assistant._call_model_with_backoff(user_input)
    if getattr(resp, "function_calls", None):
        tool_call = resp.function_calls[0]
        result = assistant.handle_tool_call(tool_call, db, chat.id)
        # TODO: Handle errors from tool_call and provide fallback messages
        final = assistant.client.chats.send_message(
            f"Tool response: {json.dumps(result)}",
            chat_id=resp.chat_id,
        )
        text = final.text
        companies = result.get("companies", [])
    else:
        text = resp.text
        companies = []

    # Persist assistant response; consider batching DB writes for performance
    chat_service.create_message(
        db,
        chat_id=chat.id,
        content=text,
        role="assistant",
        metadata={"companies_found": companies},
    )
    return {
        "chat_id": str(chat.id),
        "assistant_id": assistant_id,
        "thread_id": None,
        "response": text,
        "companies_found": companies,
    } 