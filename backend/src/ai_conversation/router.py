from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import traceback
import uuid
from typing import Optional

from .models import ChatRequest, ChatResponse, APIResponse, ConversationInput, ConversationResponse
from .assistant_creator import handle_conversation_with_context
from ..core.database import get_db
from ..auth.models import User
from ..auth.dependencies import get_current_user
from ..chats import service as chat_service

router = APIRouter(prefix="/ai", tags=["AI Conversation"])


@router.post("/chat-assistant", response_model=ChatResponse)
async def handle_chat_with_assistant(
    request: ChatRequest, 
    db: Session = Depends(get_db),
    # Add the security dependency!
    current_user: User = Depends(get_current_user) 
):
    """
    Handle AI conversation with DATABASE PERSISTENCE.
    - Loads history from DB if thread_id (chat_id) is provided.
    - Saves the new conversation turn to the DB.
    """
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty")
    
    # Use thread_id as our persistent chat_id. Let's make it a UUID.
    chat_id: Optional[uuid.UUID] = None
    if request.thread_id:
        try:
            chat_id = uuid.UUID(request.thread_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid thread_id format. Must be a UUID.")

    # 1. LOAD HISTORY FROM DATABASE
    db_history = []
    if chat_id:
        chat = chat_service.get_chat_history(db, chat_id=chat_id, user=current_user)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat thread not found or permission denied.")
        # Convert DB models to the dict format your AI service expects
        db_history = [{"role": msg.role, "content": msg.content} for msg in chat.messages]

    print(f"✅ [PERSISTENT-ROUTER] Loaded {len(db_history)} messages from DB for chat_id: {chat_id}")

    try:
        # 2. CALL YOUR EXISTING AI LOGIC
        # Your AI logic already knows how to handle a history list. We just provide
        # the one we loaded from the database instead of the one from the request.
        response_data = await handle_conversation_with_context(
            user_input=request.user_input,
            conversation_history=db_history, # Use DB history here!
            db=db,
            assistant_id=request.assistant_id,
            # We pass the thread_id so it can be returned, but our persistence
            # doesn't depend on the OpenAI thread object anymore.
            thread_id=request.thread_id 
        )

        # 3. SAVE THE NEW TURN TO THE DATABASE
        ai_response_message = response_data.get('message', 'Error: No message content from AI.')
        
        updated_chat = chat_service.save_conversation_turn(
            db=db,
            user=current_user,
            user_message_content=request.user_input,
            ai_message_content=ai_response_message,
            chat_id=chat_id
        )

        # 4. PREPARE THE RESPONSE
        # The AI response (`response_data`) is good, but we need to inject the
        # correct, persistent `thread_id` (our chat_id) and the full history.
        final_history = [{"role": msg.role, "content": msg.content} for msg in updated_chat.messages]
        
        return ChatResponse(
            message=ai_response_message,
            companies=response_data.get('companies', []),
            updated_history=final_history,
            assistant_id=response_data.get('assistant_id'),
            # Return the persistent chat ID so the frontend can continue the conversation
            thread_id=str(updated_chat.id) 
        )
        
    except Exception as e:
        print(f"❌ [PERSISTENT-ROUTER] Error in chat endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) 