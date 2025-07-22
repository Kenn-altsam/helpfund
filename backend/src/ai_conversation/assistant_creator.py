
import json
import time
import uuid
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..companies.service import CompanyService
from ..auth.models import User
from ..chats import service as chat_service


class GeminiFundAssistant:
    def __init__(self):
        self.settings = get_settings()
        genai.configure(api_key=self.settings.GEMINI_API_KEY)
        search_companies_tool = FunctionDeclaration(
            name="search_companies",
            description="Searches for companies by name and location",
            parameters={
                "type": "object",
                "properties": {
                    "company_name": {"type": "string", "description": "Company name to search for"},
                    "location": {"type": "string", "description": "Location to search in"},
                    "activity_keywords": {"type": "string", "description": "Keywords for company activity"},
                    "limit": {"type": "integer", "description": "Max results to return"},
                    "page": {"type": "integer", "description": "Page number for pagination"}
                },
                "required": ["company_name"]
            }
        )
        get_company_details_tool = FunctionDeclaration(
            name="get_company_details",
            description="Get details for a company by ID",
            parameters={
                "type": "object",
                "properties": {
                    "company_id": {"type": "string", "description": "ID of the company"}
                },
                "required": ["company_id"]
            }
        )
        self.model = genai.GenerativeModel(
            model_name=self.settings.GEMINI_MODEL_NAME,
            tools=[search_companies_tool, get_company_details_tool]
        )

    def _call_model_with_backoff(self, prompt: str, is_json_output: bool = False):
        """Calls the Gemini API with exponential backoff."""
        time.sleep(1)
        # Simplified for brevity, in production use a library like `tenacity`
        try:
            chat_session = self.model.start_chat(
                enable_automatic_function_calling=True
            )
            response = chat_session.send_message(prompt)
            return response
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            raise

    def handle_tool_call(self, tool_call, db: Session, chat_id: Optional[uuid.UUID]):
        """Executes the appropriate function based on the tool call."""
        function_name = tool_call.name
        function_args = tool_call.args
        print(f"Executing function: {function_name} with args: {function_args}")

        if function_name == "search_companies":
            return self.search_companies_tool(function_args, db, chat_id)
        elif function_name == "get_company_details":
            return self.get_company_details_tool(function_args, db)
        else:
            return {"error": f"Unknown tool: {function_name}"}

    def search_companies_tool(self, args: Dict, db: Session, chat_id: Optional[uuid.UUID]) -> Dict:
        """Handles the search_companies tool call."""
        try:
            company_service = CompanyService(db)
            limit = int(args.get("limit", 50))
            page = self._calculate_page(args, db, chat_id)

            companies = company_service.search_companies(
                location=args.get("location"),
                company_name=args.get("company_name"),
                activity_keywords=args.get("activity_keywords"),
                limit=limit,
                offset=(page - 1) * limit
            )
            
            # Here, we assume `companies` is a list of dictionaries with the correct keys
            return {
                "companies": companies,
                "total_found": len(companies),
                "search_criteria": args,
                "page": page,
                "limit": limit
            }
        except Exception as e:
            return {"error": str(e)}

    def get_company_details_tool(self, args: Dict, db: Session) -> Dict:
        """Handles the get_company_details tool call."""
        try:
            company_service = CompanyService(db)
            company_id = args.get("company_id")
            company_dict = company_service.get_company_by_id(company_id)
            return company_dict if company_dict else {"error": "Company not found."}
        except Exception as e:
            return {"error": str(e)}

    def _calculate_page(self, args: Dict, db: Session, chat_id: Optional[uuid.UUID]) -> int:
        """Calculates the pagination page number."""
        page = args.get("page")
        if page is not None:
            return int(page)
        
        if chat_id:
            prev_search_calls = chat_service.count_search_requests(db, chat_id)
            return max(1, prev_search_calls)
        
        return 1

def handle_conversation_with_context(
    user_input: str,
    db: Session,
    user: User,
    chat_id: Optional[uuid.UUID] = None,
    assistant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles a user's message using Gemini, maintaining context.
    The `assistant_id` is kept for schema compatibility but is not used by Gemini.
    """
    assistant_manager = GeminiFundAssistant()
    
    current_chat = None
    if chat_id:
        current_chat = chat_service.get_chat_by_id(db, chat_id, user.id)

    if not current_chat:
        # We need a chat to save messages, create one.
        # `thread_id` and `assistant_id` will be null but the columns exist.
        current_chat = chat_service.create_chat(
            db=db,
            user_id=user.id,
            name=user_input[:50]
        )
    
    chat_id = current_chat.id

    try:
        # Save user message to DB
        chat_service.create_message(db, chat_id=chat_id, content=user_input, role="user")

        # Call Gemini
        response = assistant_manager._call_model_with_backoff(user_input)
        
        # Check for tool calls
        if response.function_calls:
            tool_call = response.function_calls[0]
            tool_response = assistant_manager.handle_tool_call(tool_call, db, chat_id)
            
            # Send tool response back to Gemini
            final_response_obj = assistant_manager.model.send_message(
                f"Tool response: {json.dumps(tool_response)}",
                tool_response=tool_response
            )
            assistant_message_content = final_response_obj.text
            companies_found = tool_response.get("companies", [])
        else:
            assistant_message_content = response.text
            companies_found = []

        # Save assistant response to DB
        chat_service.create_message(
            db,
            chat_id=chat_id,
            content=assistant_message_content,
            role="assistant",
            metadata={"companies_found": companies_found}
        )

        return {
            "chat_id": str(chat_id),
            "assistant_id": assistant_id,  # Keep for compatibility
            "thread_id": None,  # Keep for compatibility
            "response": assistant_message_content,
            "companies_found": companies_found
        }

    except Exception as e:
        print(f"Error in Gemini conversation handling: {str(e)}")
        return {
            "error": "An unexpected error occurred while processing your request.",
            "details": str(e)
        } 