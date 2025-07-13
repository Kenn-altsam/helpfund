from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import traceback
import uuid
from typing import Optional

from .models import ChatRequest, ChatResponse
from .assistant_creator import handle_conversation_with_context
from ..core.database import get_db
from ..auth.models import User
from ..auth.dependencies import get_current_user
from ..chats import service as chat_service

router = APIRouter(prefix="/ai", tags=["AI Conversation"])


@router.post("/chat-assistant", response_model=ChatResponse)
def handle_chat_with_assistant(
    request: ChatRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) 
):
    """
    Handle an AI conversation turn with database persistence.
    - Manages chat history and OpenAI thread context via the database.
    - Saves the new conversation turn to the database.
    """
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty")
    
    chat_id: Optional[uuid.UUID] = None
    if request.thread_id:
        try:
            chat_id = uuid.UUID(request.thread_id)
        except ValueError:
            # For this endpoint, we treat the thread_id as our database chat_id
            raise HTTPException(status_code=400, detail="Invalid thread_id format. Must be a UUID.")

    print(f"✅ [ROUTER] Starting chat for user {current_user.id} with chat_id: {chat_id}")

    try:
        # 1. CALL THE REFACTORED AI LOGIC
        # This function now handles all the OpenAI-side complexity.
        response_data = handle_conversation_with_context(
            user_input=request.user_input,
            db=db,
            user=current_user,
            chat_id=chat_id,
            assistant_id=request.assistant_id,
        )

        if response_data["status"] == "error":
             raise HTTPException(status_code=500, detail=response_data["message"])

        # 2. SAVE THE NEW TURN TO THE DATABASE
        ai_response_message = response_data.get('message', 'Error: No message content from AI.')
        ai_message_data = response_data.get('companies', []) # Get the companies data
        
        # Use the chat_id returned by the context handler, as it might be new
        persistent_chat_id = response_data.get("chat_id")
        
        updated_chat = chat_service.save_conversation_turn(
            db=db,
            user=current_user,
            user_message_content=request.user_input,
            ai_message_content=ai_response_message,
            chat_id=persistent_chat_id,
            ai_message_data={"companies": ai_message_data} # Pass it here
        )

        # 3. PREPARE THE RESPONSE
        final_history = [{
            "role": msg.role, 
            "content": msg.content, 
            "metadata": msg.data,
            "companies": msg.data.get("companies") if msg.data else []
        } for msg in updated_chat.messages]
        
        return ChatResponse(
            message=ai_response_message,
            companies=ai_message_data,
            updated_history=final_history,
            assistant_id=response_data.get('assistant_id'),
            # Return the persistent database chat ID so the frontend can continue.
            thread_id=str(updated_chat.id) 
        )
        
    except Exception as e:
        print(f"❌ [ROUTER] Error in chat endpoint: {str(e)}")
        traceback.print_exc()
        # Check if it's an HTTPException and re-raise, otherwise, return a generic 500
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") 