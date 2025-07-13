"""
AI Assistant Creator for Charity Fund Discovery

Creates and manages OpenAI assistants specifically designed for helping charity funds
discover potential corporate sponsors in Kazakhstan. This assistant integrates with
the database to provide company information and maintains conversation history.
"""

import json
import asyncio
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
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
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        
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

    async def create_assistant(self) -> str:
        """
        Create a new OpenAI assistant configured for charity fund discovery.
        Returns the assistant ID.
        """
        try:
            assistant = await self.client.beta.assistants.create(
                name="Charity Fund Discovery Assistant",
                instructions=self.system_instructions,
                model="gpt-4o",
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

    async def create_conversation_thread(self) -> str:
        """
        Create a new conversation thread for maintaining history.
        Returns the thread ID.
        """
        try:
            thread = await self.client.beta.threads.create()
            print(f"✅ Created conversation thread: {thread.id}")
            return thread.id
        except Exception as e:
            print(f"❌ Error creating thread: {str(e)}")
            raise

    async def add_message_to_thread(self, thread_id: str, message: str, role: str = "user", metadata: Optional[Dict[str, Any]] = None) -> str:
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
            message_obj = await self.client.beta.threads.messages.create(
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

    async def run_assistant_with_tools(
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

        try:
            run = await self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                instructions=instructions or "Help the user find potential corporate sponsors for their charity fund. Use the provided functions to search for companies and provide detailed information."
            )

            while run.status in ["queued", "in_progress", "requires_action"]:
                await asyncio.sleep(1)
                run = await self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

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
                                page = function_args.get("page", 1)
                                offset = (page - 1) * limit

                                companies = await company_service.search_companies(
                                    location=function_args.get("location"),
                                    activity_keywords=function_args.get("activity_keywords"),
                                    limit=limit,
                                    offset=offset
                                )
                                formatted_companies = []
                                for company_dict in companies:
                                    formatted_company = {
                                        "id": company_dict.get("id"),
                                        "name": company_dict.get("company_name"),
                                        "bin": company_dict.get("bin"),
                                        "activity": company_dict.get("activity"),
                                        "location": company_dict.get("locality"),
                                        "oked": company_dict.get("oked_code"),
                                        "size": company_dict.get("company_size"),
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
                                company_dict = await company_service.get_company_by_id(company_id)
                                if company_dict:
                                    company_details = {
                                        "id": company_dict.get("id"),
                                        "name": company_dict.get("company_name"),
                                        "bin": company_dict.get("bin"),
                                        "activity": company_dict.get("activity"),
                                        "location": company_dict.get("locality"),
                                        "oked": company_dict.get("oked"),
                                        "kato": company_dict.get("kato"),
                                        "krp": company_dict.get("krp"),
                                        "size": company_dict.get("size"),
                                    }
                                    companies_found_in_turn.append(company_details)
                                    tool_outputs.append({"tool_call_id": tool_call.id, "output": json.dumps(company_details, ensure_ascii=False)})
                                    print(f"✅ Company details retrieved for: {company_details.get('name')}")
                                else:
                                    tool_outputs.append({"tool_call_id": tool_call.id, "output": "Company not found."})
                            except Exception as e:
                                print(f"❌ Error in get_company_details: {str(e)}")
                                tool_outputs.append({"tool_call_id": tool_call.id, "output": f"Error getting company details: {str(e)}."})
                    
                    run = await self.client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id, run_id=run.id, tool_outputs=tool_outputs)

            messages = await self.client.beta.threads.messages.list(thread_id=thread_id)
            latest_message = messages.data[0]
            assistant_response_content = latest_message.content[0].text.value if latest_message.content else ""
            print(f"🤖 Assistant completed with status: {run.status}")
            print(f"📊 Companies processed in this turn: {len(companies_found_in_turn)}")

            return {
                "status": run.status,
                "message": assistant_response_content,
                "companies": companies_found_in_turn,
                "run_id": run.id,
                "companies_found": len(companies_found_in_turn)
            }

        except Exception as e:
            print(f"❌ Error running assistant: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"Извините, произошла ошибка при обработке запроса: {str(e)}",
                "companies": companies_found_in_turn,
                "run_id": None,
                "companies_found": len(companies_found_in_turn)
            }

    async def get_conversation_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve the conversation history from a thread with metadata.
        This is crucial for preserving company data across turns.
        """
        try:
            messages = await self.client.beta.threads.messages.list(
                thread_id=thread_id,
                order="asc"
            )

            history = []
            for message in messages.data:
                role = message.role
                content = message.content[0].text.value if message.content and message.content[0].type == 'text' else ""

                # Extract metadata, especially 'companies'
                companies_meta = message.metadata.get("companies") if getattr(message, "metadata", None) else None

                history.append({
                    "role": role,
                    "content": content,
                    "companies": companies_meta,  # Expose companies directly for convenience
                    "metadata": {"companies": companies_meta} if companies_meta else {}  # Full metadata
                })

            print(f"📚 Retrieved {len(history)} messages from thread {thread_id}")
            return history

        except Exception as e:
            print(f"❌ Error getting conversation history: {str(e)}")
            return []

    async def sync_history_with_thread(self, thread_id: str, external_history: List[Dict[str, Any]]) -> str:
        """
        Synchronize external conversation history with the OpenAI thread.
        This ensures context is preserved when switching between systems.
        
        Args:
            thread_id: The OpenAI thread ID
            external_history: History from the external system (can include 'companies' metadata)
            
        Returns:
            Updated thread ID (same as input)
        """
        try:
            current_thread_messages = await self.client.beta.threads.messages.list(
                thread_id=thread_id, order="asc"
            ).data

            # Convert current thread messages to a comparable format
            current_history_comparable = [
                {"role": msg.role, "content": msg.content[0].text.value if msg.content and msg.content[0].type == 'text' else ""}
                for msg in current_thread_messages
            ]

            added_count = 0
            for ext_msg in external_history:
                ext_msg_comparable = {"role": ext_msg.get("role", ""), "content": ext_msg.get("content", "")}

                # Check if this external message already exists in the thread
                if ext_msg_comparable not in current_history_comparable:
                    role = ext_msg.get("role", "user")
                    content = ext_msg.get("content", "")
                    metadata = ext_msg.get("metadata", {})  # Pass any existing metadata

                    if role and content:
                        await self.add_message_to_thread(thread_id, content, role, metadata)
                        print(f"🔄 Added missing message to thread: {role} - {content[:50]}...")
                        added_count += 1

            print(f"✅ Synchronized {added_count} missing messages with thread")
            return thread_id
            
        except Exception as e:
            print(f"❌ Error synchronizing history with thread: {str(e)}")
            return thread_id

    async def cleanup_assistant(self, assistant_id: str):
        """
        Delete an assistant when no longer needed.
        """
        try:
            await self.client.beta.assistants.delete(assistant_id)
            print(f"✅ Deleted assistant: {assistant_id}")
        except Exception as e:
            print(f"❌ Error deleting assistant: {str(e)}")


# Global assistant instance
charity_assistant = CharityFundAssistant()


async def create_charity_fund_assistant() -> str:
    """
    Convenience function to create a new charity fund discovery assistant.
    Returns the assistant ID.
    """
    return await charity_assistant.create_assistant()


async def start_conversation(assistant_id: str, initial_message: str, db: Session) -> Dict[str, Any]:
    """
    Start a new conversation with the charity fund assistant.
    Returns conversation thread ID and initial response.
    """
    try:
        # Create thread
        thread_id = await charity_assistant.create_conversation_thread()
        
        # Add initial message
        await charity_assistant.add_message_to_thread(thread_id, initial_message)
        
        # Run assistant
        response = await charity_assistant.run_assistant_with_tools(
            assistant_id=assistant_id,
            thread_id=thread_id,
            db=db
        )
        
        return {
            "thread_id": thread_id,
            "response": response["message"],
            "status": response["status"],
            "companies": response.get("companies", []),  # Include companies from initial run
            "companies_found": response.get("companies_found", 0)
        }
        
    except Exception as e:
        print(f"❌ Error starting conversation: {str(e)}")
        return {
            "thread_id": None,
            "response": f"Error starting conversation: {str(e)}",
            "status": "error",
            "companies": [],
            "companies_found": 0
        }


async def continue_conversation(
    assistant_id: str, 
    thread_id: str, 
    message: str, 
    db: Session
) -> Dict[str, Any]:
    """
    Continue an existing conversation with the charity fund assistant.
    The primary goal is to add the new message and let the assistant respond,
    then retrieve the full updated history.
    """
    try:
        # Add the new user message
        await charity_assistant.add_message_to_thread(thread_id, message)

        # Run assistant to get a response and execute tools
        response = await charity_assistant.run_assistant_with_tools(
            assistant_id=assistant_id, thread_id=thread_id, db=db
        )

        # Get updated conversation history (including assistant's response and any metadata)
        updated_history = await charity_assistant.get_conversation_history(thread_id)

        return {
            "response": response["message"],
            "status": response["status"],
            "updated_history": updated_history,
            "thread_id": thread_id,
            "companies": response.get("companies", []),  # Companies from this specific turn
            "companies_found": response.get("companies_found", 0)
        }
    except Exception as e:
        print(f"❌ Error continuing conversation: {str(e)}")
        import traceback
        traceback.print_exc()
        # Fallback: retrieve current history and append an error message if possible
        try:
            current_history = await charity_assistant.get_conversation_history(thread_id)
            current_history.append({"role": "user", "content": message})
            current_history.append({"role": "assistant", "content": f"Извините, произошла ошибка: {str(e)}"})
        except Exception:
            current_history = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": f"Извините, произошла ошибка: {str(e)}"}
            ]

        return {
            "response": f"Извините, произошла ошибка при обработке запроса: {str(e)}",
            "status": "error",
            "updated_history": current_history,
            "thread_id": thread_id,
            "companies": [],
            "companies_found": 0
        }


async def handle_conversation_with_context(
    user_input: str,
    db: Session,
    user: User, # Changed from user_id to user object
    chat_id: Optional[uuid.UUID] = None,
    assistant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle a conversation turn with full context preservation.
    This is the main orchestrator that bridges the database and OpenAI.
    
    Args:
        user_input (str): The new message from the user.
        db (Session): The database session.
        user (User): The authenticated user object.
        chat_id (Optional[uuid.UUID]): The ID of the chat in our database.
        assistant_id (Optional[str]): The OpenAI assistant ID.

    Returns:
        Dict[str, Any]: A dictionary containing the response and state.
    """
    try:
        print(f"🎯 Starting context-aware conversation for user {user.id}. Chat ID: {chat_id}")

        # 1. Get or Create Assistant ID
        if not assistant_id:
            print("📝 Assistant ID not provided, creating a new one...")
            assistant_id = await charity_assistant.create_assistant()

        # 2. Get or Create Chat and OpenAI Thread ID
        thread_id: Optional[str] = None
        chat: Optional[models.Chat] = None
        conversation_history = []

        if chat_id:
            chat = chat_service.get_chat_history(db, chat_id=chat_id, user=user)
            if not chat:
                 raise ValueError("Chat not found or permission denied.")
            thread_id = chat.openai_thread_id
            conversation_history = [{"role": msg.role, "content": msg.content, "metadata": {}} for msg in chat.messages]
            print(f"✅ Found existing chat {chat.id} with thread {thread_id}")

        # If no thread ID, create a new one and sync history if any
        if not thread_id:
            print("🧵 Creating new OpenAI conversation thread...")
            thread_id = await charity_assistant.create_conversation_thread()
            if chat:
                chat.openai_thread_id = thread_id
                db.commit()
                print(f"🔗 Linked new thread {thread_id} to existing chat {chat.id}")
                # Sync existing messages to the new thread
                if conversation_history:
                    print(f"📚 Populating new thread with {len(conversation_history)} history items...")
                    await charity_assistant.sync_history_with_thread(thread_id, conversation_history)


        # 3. Add the NEW user message to the thread
        print(f"💬 Adding new user message to thread {thread_id}...")
        await charity_assistant.add_message_to_thread(thread_id, user_input, "user")

        # 4. Run the assistant with tools
        response_from_run = await charity_assistant.run_assistant_with_tools(
            assistant_id=assistant_id,
            thread_id=thread_id,
            db=db
        )

        # 5. Get the complete updated history from the thread (for potential future use, though we rely on db)
        updated_history_from_openai = await charity_assistant.get_conversation_history(thread_id)

        # The saving logic will be handled in the router after this function returns.
        
        print(f"✅ Context-aware conversation turn completed.")
        return {
            "message": response_from_run["message"],
            "companies": response_from_run.get("companies", []),
            "assistant_id": assistant_id,
            "thread_id": thread_id, # This is the OpenAI thread_id
            "chat_id": chat.id if chat else None, # This is our DB chat_id
            "status": response_from_run["status"],
            "companies_found": response_from_run.get("companies_found", 0)
        }

    except Exception as e:
        print(f"❌ Error in context-aware conversation: {str(e)}")
        import traceback
        traceback.print_exc()

        # We don't create history here, just report the error
        return {
            "message": "Извините, произошла техническая ошибка. Ваш контекст разговора сохранен, попробуйте переформулировать вопрос.",
            "companies": [],
            "assistant_id": assistant_id,
            "thread_id": None,
            "chat_id": chat_id,
            "status": "error",
            "companies_found": 0,
        }