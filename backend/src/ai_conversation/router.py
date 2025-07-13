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

        if "error" in response_data:
             raise HTTPException(status_code=500, detail=response_data.get("details", "An unknown error occurred in the AI handler."))

        # 2. PREPARE THE RESPONSE
        return ChatResponse(
            message=response_data.get("response"),
            companies=response_data.get("companies_found", []),
            assistant_id=response_data.get('assistant_id'),
            thread_id=response_data.get("thread_id")
        )
        
    except Exception as e:
        print(f"❌ [ROUTER] Error in chat endpoint: {str(e)}")
        traceback.print_exc()
        # Check if it's an HTTPException and re-raise, otherwise, return a generic 500
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") 