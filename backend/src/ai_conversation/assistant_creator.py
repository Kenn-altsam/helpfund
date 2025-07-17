"""
AI Assistant Creator for Charity Fund Discovery

Creates and manages OpenAI assistants specifically designed for helping charity funds
discover potential corporate sponsors in Kazakhstan. This assistant integrates with
the database to provide company information and maintains conversation history.
"""

import json
import time
from typing import Dict, List, Optional, Any
from openai import OpenAI
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..companies.service import CompanyService
from .models import ChatResponse, CompanyData
from ..auth.models import User
from ..chats import models
from ..chats import service as chat_service
import uuid


class CharityFundAssistant:
    """
    Assistant specifically designed for charity fund discovery use case.
    Manages conversation history and integrates with company database.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(
            api_key=self.settings.OPENAI_API_KEY,
        )
        
        # Assistant configuration for charity fund discovery
        self.system_instructions = """
        You are an AI assistant for the Ayala Foundation project, specifically designed to help charity funds discover potential corporate sponsors in Kazakhstan.

        Your primary capabilities:
        1. Help charity funds find companies based on location, industry, and other criteria
        2. Provide detailed company information including contact details, financial data, and potential sponsorship opportunities
        3. Maintain conversation context to understand follow-up requests
        4. Suggest matching strategies between charity funds and companies
        5. Explain company data in a helpful, contextual manner

        Key guidelines:
        - Always respond in the language the user prefers (Russian, English, or Kazakh)
        - Be helpful and professional in tone
        - Provide actionable insights about potential sponsorship opportunities
        - Remember previous requests in the conversation to provide consistent help
        - When providing company lists, include relevant details like location, industry, and contact availability
        - Suggest next steps for charity funds to approach potential sponsors

        You have access to a comprehensive database of companies in Kazakhstan with information about:
        - Company names, BIN numbers, and registration details
        - Industry classifications and business activities
        - Geographic locations (regions, cities)
        - Company sizes and employee counts
        - Contact information (when available)
        - Financial indicators and tax compliance data
        """

    def create_assistant(self) -> str:
        """
        Create a new OpenAI assistant configured for charity fund discovery.
        Returns the assistant ID.
        """
        try:
            assistant = self.client.beta.assistants.create(
                model=self.settings.OPENAI_MODEL_NAME,
                name="Charity Fund Discovery Assistant",
                instructions=self.system_instructions,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "search_companies",
                            "description": "Search for companies in Kazakhstan based on location, industry, or other criteria",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": "string",
                                        "description": "City or region to search in (e.g., 'Алматы', 'Астана')"
                                    },
                                    "activity_keywords": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Keywords related to company activities or industries"
                                    },
                                    "limit": {
                                        "type": "integer",
                                        "description": "Maximum number of companies to return (defaults to 50 if not specified)",
                                        "default": 10
                                    },
                                    "page": {
                                        "type": "integer",
                                        "description": "Page number for pagination (default: 1)",
                                        "default": 1
                                    }
                                },
                                "required": []
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_company_details",
                            "description": "Get detailed information about a specific company",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "company_id": {
                                        "type": "string",
                                        "description": "The unique ID of the company"
                                    }
                                },
                                "required": ["company_id"]
                            }
                        }
                    }
                ]
            )
            
            print(f"✅ Created assistant: {assistant.id}")
            return assistant.id
            
        except Exception as e:
            print(f"❌ Error creating assistant: {str(e)}")
            raise

    def create_conversation_thread(self) -> str:
        """
        Create a new conversation thread for maintaining history.
        Returns the thread ID.
        """
        try:
            thread = self.client.beta.threads.create()
            print(f"✅ Created conversation thread: {thread.id}")
            return thread.id
        except Exception as e:
            print(f"❌ Error creating thread: {str(e)}")
            raise

    def add_message_to_thread(self, thread_id: str, message: str, role: str = "user", metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a message to an existing conversation thread, with optional metadata.
        This version automatically converts non-string metadata values to JSON strings.
        """
        processed_metadata = {}
        if metadata:
            for key, value in metadata.items():
                if not isinstance(value, str):
                    # If value is a list, dict, or number, convert it to a JSON string
                    print(f"🔄 Converting metadata key '{key}' to JSON string.")
                    processed_metadata[key] = json.dumps(value, ensure_ascii=False)
                else:
                    processed_metadata[key] = value

        try:
            message_obj = self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role=role,
                content=message,
                # Use the processed metadata. Pass None if it's empty.
                metadata=processed_metadata if processed_metadata else None
            )
            return message_obj.id
        except Exception as e:
            print(f"❌ Error adding message to thread: {str(e)}")
            raise

    def run_assistant_with_tools(
        self,
        assistant_id: str,
        thread_id: str,
        db: Session,
        instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs the assistant. Returns the company data instead of saving it to metadata.
        This version does NOT reference tax_payment_2025.
        """
        companies_found_in_turn = []

        print(f"[run_assistant_with_tools] Using assistant_id={assistant_id}, thread_id={thread_id}")

        try:
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                instructions=instructions or "Help the user find potential corporate sponsors for their charity fund. Use the provided functions to search for companies and provide detailed information."
            )

            while run.status in ["queued", "in_progress", "requires_action"]:
                time.sleep(1)
                run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

                if run.status == "requires_action":
                    tool_outputs = []
                    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        print(f"🔧 Executing function: {function_name} with args: {function_args}")

                        if function_name == "search_companies":
                            try:
                                company_service = CompanyService(db)
                                limit = int(function_args.get("limit", 50))
                                # Fallback: determine page/offset if missing
                                page = function_args.get("page")
                                offset = function_args.get("offset")
                                if offset is None:
                                    # Try to infer page/offset from thread history
                                    # Fetch all previous tool calls in this thread
                                    # (Assume self.client is OpenAI client)
                                    prev_search_calls = 0
                                    try:
                                        messages = self.client.beta.threads.messages.list(thread_id=thread_id)
                                        for msg in messages.data:
                                            for content in msg.content:
                                                if hasattr(content, 'tool_calls'):
                                                    for tool_call in content.tool_calls:
                                                        if getattr(tool_call.function, 'name', None) == 'search_companies':
                                                            prev_search_calls += 1
                                    except Exception as e:
                                        print(f"[Pagination Fallback] Could not fetch thread messages: {e}")
                                    # The current call is not yet counted, so offset = prev_search_calls * limit
                                    offset = prev_search_calls * limit
                                    print(f"[Pagination Fallback] Calculated offset={offset} (prev_search_calls={prev_search_calls}, limit={limit})")
                                else:
                                    offset = int(offset)
                                companies = company_service.search_companies(
                                    location=function_args.get("location"),
                                    activity_keywords=function_args.get("activity_keywords"),
                                    limit=limit,
                                    offset=offset
                                )
                                formatted_companies = []
                                for company_dict in companies:
                                    formatted_company = {
                                        "id": company_dict.get("id"),
                                        "name": company_dict.get("name"),
                                        "bin": company_dict.get("bin"),
                                        "activity": company_dict.get("activity"),
                                        "location": company_dict.get("locality"),
                                        "oked": company_dict.get("oked_code"),
                                        "size": company_dict.get("company_size"),
                                        "kato": company_dict.get("kato_code"),
                                        "krp": company_dict.get("krp_code"),
                                        "tax_data_2023": company_dict.get("tax_data_2023"),
                                        "tax_data_2024": company_dict.get("tax_data_2024"),
                                        "tax_data_2025": company_dict.get("tax_data_2025"),
                                        "contacts": company_dict.get("contacts"),
                                        "website": company_dict.get("website"),
                                    }
                                    formatted_companies.append(formatted_company)
                                    companies_found_in_turn.append(formatted_company)
                                
                                result = {"companies": formatted_companies, "total_found": len(formatted_companies), "search_criteria": function_args, "page": page, "limit": limit}
                                tool_outputs.append({"tool_call_id": tool_call.id, "output": json.dumps(result, ensure_ascii=False)})
                                print(f"✅ Search completed: {len(formatted_companies)} companies found")
                            except Exception as e:
                                print(f"❌ Error in search_companies: {str(e)}")
                                tool_outputs.append({"tool_call_id": tool_call.id, "output": f"Error searching companies: {str(e)}."})

                        elif function_name == "get_company_details":
                            try:
                                company_service = CompanyService(db)
                                company_id = function_args.get("company_id")
                                company_dict = company_service.get_company_by_id(company_id)
                                if company_dict:
                                    company_details = {
                                        "id": company_dict.get("id"),
                                        "name": company_dict.get("name"),
                                        "bin": company_dict.get("bin"),
                                        "registration_date": company_dict.get("registration_date"),
                                        "address": company_dict.get("address"),
                                        "activity": company_dict.get("activity"),
                                        "ceo_name": company_dict.get("ceo_name"),
                                        "locality": company_dict.get("locality"),
                                        "tax_payments": company_dict.get("tax_payments", []),
                                        "founders": company_dict.get("founder_names", [])
                                    }
                                    companies_found_in_turn.append(company_details)
                                    tool_outputs.append({"tool_call_id": tool_call.id, "output": json.dumps(company_details, ensure_ascii=False)})
                                else:
                                    tool_outputs.append({"tool_call_id": tool_call.id, "output": f"Company with ID {company_id} not found."})
                            except Exception as e:
                                print(f"❌ Error in get_company_details: {str(e)}")
                                tool_outputs.append({"tool_call_id": tool_call.id, "output": f"Error fetching company details: {str(e)}."})

                    run = self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs,
                    )

            messages = self.client.beta.threads.messages.list(thread_id=thread_id)
            latest_message = messages.data[0].content[0].text.value if messages.data else "No response from assistant."

            return {
                "message": latest_message,
                "companies": companies_found_in_turn,
            }

        except Exception as e:
            print(f"❌ Error running assistant: {str(e)}")
            return {
                "status": "error",
                "message": f"An error occurred while running the assistant: {str(e)}",
                "companies": []
            }

    def get_conversation_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages from a conversation thread, including metadata.
        """
        try:
            messages = self.client.beta.threads.messages.list(thread_id=thread_id)
            history = []
            for msg in messages.data:
                content = msg.content[0].text.value if msg.content else ""
                metadata = msg.metadata if msg.metadata else {}
                
                # Try to parse metadata values back from JSON strings if they were stringified
                parsed_metadata = {}
                for key, value in metadata.items():
                    try:
                        # Attempt to load value as JSON, if it fails, keep it as a string
                        parsed_metadata[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        parsed_metadata[key] = value

                history.append({"role": msg.role, "content": content, "metadata": parsed_metadata})
            return history
        except Exception as e:
            print(f"❌ Error getting conversation history: {str(e)}")
            return []

    def sync_history_with_thread(self, thread_id: str, external_history: List[Dict[str, Any]]) -> str:
        """
        Synchronizes an external chat history (e.g., from a database) with an OpenAI thread.
        This is a simplified version that adds missing messages. A more robust implementation
        would handle out-of-order messages or conflicts.
        """
        try:
            thread_messages = self.client.beta.threads.messages.list(thread_id=thread_id, order="asc")
            thread_message_contents = [msg.content[0].text.value for msg in thread_messages.data]

            for entry in external_history:
                if entry["content"] not in thread_message_contents:
                    print(f"➕ Syncing missing message to thread {thread_id}: '{entry['content'][:30]}...'")
                    self.add_message_to_thread(
                        thread_id=thread_id,
                        message=entry["content"],
                        role=entry["role"],
                        metadata=entry.get("metadata", {})
                    )
            return "Sync completed"
        except Exception as e:
            print(f"❌ Error syncing history: {str(e)}")
            raise

    def cleanup_assistant(self, assistant_id: str):
        """
        Deletes the assistant from OpenAI to avoid clutter.
        """
        try:
            response = self.client.beta.assistants.delete(assistant_id)
            print(f"✅ Deleted assistant {assistant_id}: {response}")
        except Exception as e:
            print(f"❌ Error deleting assistant {assistant_id}: {str(e)}")


def create_charity_fund_assistant() -> str:
    """
    Standalone function to create the assistant.
    """
    assistant_manager = CharityFundAssistant()
    return assistant_manager.create_assistant()

def start_conversation(assistant_id: str, initial_message: str, db: Session) -> Dict[str, Any]:
    """
    Starts a new conversation with a welcome message and an initial user query.
    Returns the initial AI response, thread ID, and any company data.
    """
    assistant_manager = CharityFundAssistant()
    thread_id = assistant_manager.create_conversation_thread()

    # Add the initial user message
    assistant_manager.add_message_to_thread(
        thread_id=thread_id,
        message=initial_message
    )

    # Run the assistant to get the first response
    run_result = assistant_manager.run_assistant_with_tools(
        assistant_id=assistant_id,
        thread_id=thread_id,
        db=db
    )

    return {
        "thread_id": thread_id,
        "message": run_result.get("message", "Error: No initial message."),
        "companies": run_result.get("companies", [])
    }

def continue_conversation(
    assistant_id: str, 
    thread_id: str, 
    message: str, 
    db: Session
) -> Dict[str, Any]:
    """
    Continues an existing conversation.
    Returns the latest AI response and any company data.
    """
    assistant_manager = CharityFundAssistant()

    # Add the new user message
    assistant_manager.add_message_to_thread(thread_id=thread_id, message=message)

    # Run the assistant
    run_result = assistant_manager.run_assistant_with_tools(
        assistant_id=assistant_id,
        thread_id=thread_id,
        db=db,
        instructions="Please continue the conversation based on the user's latest message."
    )

    # Fetch the complete history to return to the client
    history = assistant_manager.get_conversation_history(thread_id)

    return {
        "message": run_result.get("message", "Error: No message from AI."),
        "companies": run_result.get("companies", []),
        "history": history
    }


def handle_conversation_with_context(
    user_input: str,
    db: Session,
    user: User, # Changed from user_id to user object
    chat_id: Optional[uuid.UUID] = None,
    assistant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles a user's message, maintaining conversation context within a single chat session.
    It creates a new assistant and thread if they don't exist, or uses existing ones.
    This version returns company data directly instead of saving it to metadata.
    """
    assistant_manager = CharityFundAssistant()
    
    current_chat = None
    if chat_id:
        current_chat = chat_service.get_chat_by_id(db, chat_id, user.id)

    # If no chat_id is provided or the chat doesn't exist, create a new one
    if not current_chat:
        assistant_id = assistant_manager.create_assistant()
        thread_id = assistant_manager.create_conversation_thread()
        current_chat = chat_service.create_chat(
            db=db,
            user_id=user.id,
            name=user_input[:50],  # Use the first part of the message as the chat name
            openai_assistant_id=assistant_id,
            openai_thread_id=thread_id
        )
    else:
        # Use existing IDs from the chat
        assistant_id = current_chat.openai_assistant_id
        thread_id = current_chat.openai_thread_id

        # Make sure the assistant and thread still exist on OpenAI's side
        try:
            assistant_manager.client.beta.assistants.retrieve(assistant_id)
            assistant_manager.client.beta.threads.retrieve(thread_id)
        except Exception:
            # If they don't exist, create new ones and update the chat
            assistant_id = assistant_manager.create_assistant()
            thread_id = assistant_manager.create_conversation_thread()
            chat_service.update_chat_openai_ids(db, current_chat.id, assistant_id, thread_id)
            
    print(f"[handle_conversation_with_context] Using assistant_id={assistant_id}, thread_id={thread_id}, chat_id={getattr(current_chat, 'id', None)}")
    try:
        # Save the user's message to the database first
        chat_service.create_message(db, chat_id=current_chat.id, content=user_input, role="user")

        # Add the message to the OpenAI thread
        assistant_manager.add_message_to_thread(thread_id, user_input)

        # Run the assistant and get the response, including any tool outputs (company data)
        response = assistant_manager.run_assistant_with_tools(assistant_id, thread_id, db)

        # Retrieve the latest assistant message from the thread
        messages = assistant_manager.client.beta.threads.messages.list(thread_id=thread_id, limit=1)
        assistant_message_content = "No response from assistant."
        if messages.data:
            assistant_message_content = messages.data[0].content[0].text.value
        
        # Save the assistant's response to the database
        chat_service.create_message(
            db,
            chat_id=current_chat.id,
            content=assistant_message_content,
            role="assistant",
            # Store structured company data if available from the run
            metadata={"companies_found": response.get("companies", [])}
        )

        return {
            "chat_id": str(current_chat.id),
            "assistant_id": assistant_id,
            "thread_id": thread_id,
            "response": assistant_message_content,
            "companies_found": response.get("companies", [])
        }

    except Exception as e:
        print(f"❌ Error in conversation handling: {str(e)}")
        # This is a critical failure, so we return a structured error
        return {
            "error": "An unexpected error occurred while processing your request.",
            "details": str(e)
        }

charity_assistant = CharityFundAssistant()