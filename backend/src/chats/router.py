# backend/src/chats/router.py

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from ..core.database import get_db
from ..auth.dependencies import get_current_user
from ..auth.models import User
from . import service as chat_service, schemas

# Pydantic model for the incoming request to save/update a chat summary
class ChatHistorySaveRequest(BaseModel):
    id: Optional[str] = None
    user_prompt: str = Field(..., description="The last user prompt.")
    raw_ai_response: List[Any] = Field(default_factory=list, description="The raw AI response data (e.g., companies).")
    created_at: str = Field(..., description="ISO timestamp of the interaction.")
    chat_id: Optional[str] = Field(None, description="Database Chat ID (UUID).")
    thread_id: str = Field(..., description="Thread ID for this conversation.")
    assistant_id: str = Field(..., description="Assistant ID for this conversation.")


router = APIRouter(prefix="/chats", tags=["Chats"])

@router.get("/", response_model=List[schemas.ChatListItemSchema])
def get_user_chats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all chat sessions for the logged-in user (for the sidebar)."""
    chats = chat_service.get_chats_for_user(db=db, user=current_user)
    for chat in chats:
        print(f"[get_user_chats] Chat ID: {chat.id}, thread_id: {getattr(chat, 'openai_thread_id', None)}, assistant_id: {getattr(chat, 'openai_assistant_id', None)}")
    return chats

@router.post("/history", status_code=200)
def save_chat_history_summary(
    request: ChatHistorySaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Saves or updates a chat history summary."""
    try:
        # Use chat_id from request if provided, otherwise use id
        chat_id_str = request.chat_id or request.id
        chat_id_uuid: Optional[uuid.UUID] = uuid.UUID(chat_id_str) if chat_id_str else None
        
        chat_service.save_chat_summary_to_db(
            db=db,
            user_id=current_user.id,
            chat_id=chat_id_uuid,
            user_prompt=request.user_prompt,
            raw_ai_response=request.raw_ai_response,
            created_at=request.created_at,
            thread_id=request.thread_id,
            assistant_id=request.assistant_id
        )
        return {"message": "Chat summary saved successfully."}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Chat ID format. Must be a UUID.")
    except Exception as e:
        # Log the exception for debugging
        print(f"Error saving chat summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save chat summary: {str(e)}")


@router.get("/{chat_id}", response_model=schemas.ChatHistoryResponseSchema)
def get_single_chat_history(
    chat_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the full message history for a specific chat."""
    chat = chat_service.get_chat_history(db=db, chat_id=chat_id, user=current_user)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found or you don't have permission.")
    return chat

@router.delete("/{chat_id}", status_code=204)
def delete_chat(
    chat_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes a chat history record by its ID."""
    try:
        chat_id_uuid = uuid.UUID(chat_id)
        chat_service.delete_chat_from_db(db=db, chat_id=chat_id_uuid, user_id=current_user.id)
        return {} # Returns 204 No Content
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Chat ID format. Must be a UUID.")
    except Exception as e:
        # Catch potential errors from the service layer, like the ValueError for not found
        raise HTTPException(status_code=500, detail=f"Failed to delete chat: {str(e)}") 