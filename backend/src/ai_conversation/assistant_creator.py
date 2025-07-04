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
                                        "description": "Maximum number of companies to return (default: 10)",
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

    async def add_message_to_thread(self, thread_id: str, message: str, role: str = "user") -> str:
        """
        Add a message to an existing conversation thread.
        Returns the message ID.
        """
        try:
            message_obj = await self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role=role,
                content=message
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
        Run the assistant with function calling capabilities.
        Handles company search and data retrieval from the database.
        Now tracks companies data for context preservation.
        """
        companies_found = []  # Track all companies found during this run
        
        try:
            # Create a run with the assistant
            run = await self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                instructions=instructions or "Help the user find potential corporate sponsors for their charity fund. Use the provided functions to search for companies and provide detailed information."
            )
            
            # Poll for completion and handle function calls
            while run.status in ["queued", "in_progress", "requires_action"]:
                await asyncio.sleep(1)
                run = await self.client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                )
                
                # Handle function calls
                if run.status == "requires_action":
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    tool_outputs = []
                    
                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        print(f"🔧 Executing function: {function_name} with args: {function_args}")
                        
                        # Handle company search
                        if function_name == "search_companies":
                            try:
                                # Create company service with database session
                                company_service = CompanyService(db)
                                
                                # Calculate offset for pagination
                                page = function_args.get("page", 1)
                                limit = function_args.get("limit", 10)
                                offset = (page - 1) * limit
                                
                                companies = await company_service.search_companies(
                                    location=function_args.get("location"),
                                    activity_keywords=function_args.get("activity_keywords"),
                                    limit=limit,
                                    offset=offset
                                )
                                
                                # The search_companies method already returns dictionaries
                                companies_data = []
                                for company_dict in companies:
                                    formatted_company = {
                                        "id": company_dict.get("id"),
                                        "name": company_dict.get("Company"),
                                        "bin": company_dict.get("BIN"),
                                        "activity": company_dict.get("Activity"),
                                        "location": company_dict.get("Locality"),
                                        "oked": company_dict.get("OKED"),
                                        "size": company_dict.get("Size")
                                    }
                                    companies_data.append(formatted_company)
                                    companies_found.append(formatted_company)  # Track for context
                                
                                result = {
                                    "companies": companies_data,
                                    "total_found": len(companies_data),
                                    "search_criteria": function_args,
                                    "page": page,
                                    "limit": limit,
                                    "context": f"Found {len(companies_data)} companies matching your criteria"
                                }
                                
                                tool_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": json.dumps(result, ensure_ascii=False)
                                })
                                
                                print(f"✅ Search completed: {len(companies_data)} companies found")
                                
                            except Exception as e:
                                print(f"❌ Error in search_companies: {str(e)}")
                                error_msg = f"Error searching companies: {str(e)}. Please try with different search criteria."
                                tool_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": error_msg
                                })
                        
                        # Handle company details
                        elif function_name == "get_company_details":
                            try:
                                # Create company service with database session
                                company_service = CompanyService(db)
                                
                                company_id = function_args.get("company_id")
                                company_dict = await company_service.get_company_by_id(company_id)
                                
                                if company_dict:
                                    company_details = {
                                        "id": company_dict.get("id"),
                                        "name": company_dict.get("Company"),
                                        "bin": company_dict.get("BIN"),
                                        "activity": company_dict.get("Activity"),
                                        "location": company_dict.get("Locality"),
                                        "oked": company_dict.get("OKED"),
                                        "kato": company_dict.get("KATO"),
                                        "krp": company_dict.get("KRP"),
                                        "size": company_dict.get("Size"),
                                        "context": "Detailed company information retrieved"
                                    }
                                    
                                    companies_found.append(company_details)  # Track for context
                                    
                                    tool_outputs.append({
                                        "tool_call_id": tool_call.id,
                                        "output": json.dumps(company_details, ensure_ascii=False)
                                    })
                                    
                                    print(f"✅ Company details retrieved for: {company_details.get('name')}")
                                else:
                                    tool_outputs.append({
                                        "tool_call_id": tool_call.id,
                                        "output": "Company not found. Please check the company ID and try again."
                                    })
                                    
                            except Exception as e:
                                print(f"❌ Error in get_company_details: {str(e)}")
                                error_msg = f"Error getting company details: {str(e)}. Please verify the company ID."
                                tool_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": error_msg
                                })
                    
                    # Submit tool outputs
                    run = await self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )
            
            # Get the assistant's response
            messages = await self.client.beta.threads.messages.list(thread_id=thread_id)
            latest_message = messages.data[0]
            
            assistant_response = latest_message.content[0].text.value if latest_message.content else ""
            
            print(f"🤖 Assistant completed with status: {run.status}")
            print(f"📊 Companies processed in this turn: {len(companies_found)}")
            
            return {
                "status": run.status,
                "message": assistant_response,
                "companies_data": companies_found,  # Include companies data
                "run_id": run.id,
                "companies_found": len(companies_found)
            }
            
        except Exception as e:
            print(f"❌ Error running assistant: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "status": "error",
                "message": f"Извините, произошла ошибка при обработке запроса: {str(e)}",
                "companies_data": companies_found,  # Preserve any companies found before error
                "run_id": None,
                "companies_found": len(companies_found)
            }

    async def get_conversation_history(self, thread_id: str) -> List[Dict[str, str]]:
        """
        Retrieve the conversation history from a thread.
        Returns a list of messages with role and content.
        """
        try:
            messages = await self.client.beta.threads.messages.list(
                thread_id=thread_id,
                order="asc"
            )
            
            history = []
            for message in messages.data:
                role = message.role
                content = message.content[0].text.value if message.content else ""
                history.append({"role": role, "content": content})
            
            print(f"📚 Retrieved {len(history)} messages from thread {thread_id}")
            return history
            
        except Exception as e:
            print(f"❌ Error getting conversation history: {str(e)}")
            return []

    async def sync_history_with_thread(self, thread_id: str, external_history: List[Dict[str, str]]) -> str:
        """
        Synchronize external conversation history with the OpenAI thread.
        This ensures context is preserved when switching between systems.
        
        Args:
            thread_id: The OpenAI thread ID
            external_history: History from the external system
            
        Returns:
            Updated thread ID (same as input)
        """
        try:
            # Get current thread history
            current_history = await self.get_conversation_history(thread_id)
            
            # Find messages that exist in external_history but not in thread
            missing_messages = []
            for ext_msg in external_history:
                # Check if this message exists in current thread history
                found = False
                for curr_msg in current_history:
                    if (curr_msg.get("role") == ext_msg.get("role") and 
                        curr_msg.get("content") == ext_msg.get("content")):
                        found = True
                        break
                
                if not found:
                    missing_messages.append(ext_msg)
            
            # Add missing messages to thread
            for msg in missing_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role and content:
                    await self.add_message_to_thread(thread_id, content, role)
                    print(f"🔄 Added missing message to thread: {role} - {content[:50]}...")
            
            print(f"✅ Synchronized {len(missing_messages)} missing messages with thread")
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
            "status": response["status"]
        }
        
    except Exception as e:
        print(f"❌ Error starting conversation: {str(e)}")
        return {
            "thread_id": None,
            "response": f"Error starting conversation: {str(e)}",
            "status": "error"
        }


async def continue_conversation(
    assistant_id: str, 
    thread_id: str, 
    message: str, 
    db: Session,
    external_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Continue an existing conversation with the charity fund assistant.
    Now supports syncing with external conversation history.
    
    Args:
        assistant_id: The OpenAI assistant ID
        thread_id: The conversation thread ID
        message: New user message
        db: Database session
        external_history: Optional external conversation history to sync
    
    Returns:
        Dictionary with response, status, and updated history
    """
    try:
        # Sync with external history if provided
        if external_history:
            await charity_assistant.sync_history_with_thread(thread_id, external_history)
        
        # Add user message to thread
        await charity_assistant.add_message_to_thread(thread_id, message)
        
        # Run assistant
        response = await charity_assistant.run_assistant_with_tools(
            assistant_id=assistant_id,
            thread_id=thread_id,
            db=db
        )
        
        # Get updated conversation history
        updated_history = await charity_assistant.get_conversation_history(thread_id)
        
        return {
            "response": response["message"],
            "status": response["status"],
            "updated_history": updated_history,
            "thread_id": thread_id
        }
        
    except Exception as e:
        print(f"❌ Error continuing conversation: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback: preserve context even on error
        fallback_history = external_history.copy() if external_history else []
        fallback_history.append({"role": "user", "content": message})
        fallback_history.append({"role": "assistant", "content": f"Извините, произошла ошибка: {str(e)}"})
        
        return {
            "response": f"Извините, произошла ошибка при обработке запроса: {str(e)}",
            "status": "error",
            "updated_history": fallback_history,
            "thread_id": thread_id
        }


async def handle_conversation_with_context(
    user_input: str,
    conversation_history: List[Dict[str, str]],
    db: Session,
    assistant_id: Optional[str] = None,
    thread_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle a conversation turn with full context preservation.
    This is the main entry point for context-aware conversations.
    
    Args:
        user_input: The user's message
        conversation_history: Previous conversation history
        db: Database session
        assistant_id: Optional existing assistant ID
        thread_id: Optional existing thread ID
    
    Returns:
        Complete conversation response with preserved context
    """
    try:
        print(f"🎯 Starting context-aware conversation with {len(conversation_history)} history items")
        
        # Create assistant if not provided
        if not assistant_id:
            print("📝 Creating new assistant...")
            assistant_id = await charity_assistant.create_assistant()
        
        # Create or use existing thread
        if not thread_id:
            print("🧵 Creating new conversation thread...")
            thread_id = await charity_assistant.create_conversation_thread()
            
            # Add all history to the new thread
            if conversation_history:
                print(f"📚 Adding {len(conversation_history)} history items to thread...")
                for msg in conversation_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role and content:
                        await charity_assistant.add_message_to_thread(thread_id, content, role)
        else:
            # Sync existing thread with provided history
            print(f"🔄 Syncing existing thread with {len(conversation_history)} history items...")
            await charity_assistant.sync_history_with_thread(thread_id, conversation_history)
        
        # Add new user message and run assistant
        print("💬 Processing new user message...")
        await charity_assistant.add_message_to_thread(thread_id, user_input, "user")
        
        response = await charity_assistant.run_assistant_with_tools(
            assistant_id=assistant_id,
            thread_id=thread_id,
            db=db,
            instructions=f"Previous conversation context: {len(conversation_history)} messages. Continue the conversation naturally."
        )
        
        # Get complete updated history
        updated_history = await charity_assistant.get_conversation_history(thread_id)
        
        # Extract companies data from the response if any
        companies_data = []
        if "companies" in response.get("message", "").lower():
            # This could be enhanced to parse actual company data from function calls
            pass
        
        print(f"✅ Context-aware conversation completed with {len(updated_history)} total history items")
        
        return {
            "message": response["message"],
            "updated_history": updated_history,
            "companies_data": companies_data,
            "intent": "find_companies" if "companies" in response["message"].lower() else "general_question",
            "assistant_id": assistant_id,
            "thread_id": thread_id,
            "status": response["status"],
            "companies_found": len(companies_data),
            "has_more_companies": False
        }
        
    except Exception as e:
        print(f"❌ Error in context-aware conversation: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Preserve context even on error
        error_history = conversation_history.copy()
        error_history.append({"role": "user", "content": user_input})
        error_history.append({
            "role": "assistant", 
            "content": "Извините, произошла техническая ошибка. Ваш контекст разговора сохранен, попробуйте переформулировать вопрос."
        })
        
        return {
            "message": "Извините, произошла техническая ошибка. Ваш контекст разговора сохранен, попробуйте переформулировать вопрос.",
            "updated_history": error_history,
            "companies_data": [],
            "intent": "error",
            "assistant_id": assistant_id,
            "thread_id": thread_id,
            "status": "error",
            "companies_found": 0,
            "has_more_companies": False
        }

