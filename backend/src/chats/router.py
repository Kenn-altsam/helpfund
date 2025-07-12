# backend/src/chats/router.py

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..core.database import get_db
from ..auth.models import User
from ..auth.dependencies import get_current_user # Our security dependency
from . import service, schemas

router = APIRouter(prefix="/chats", tags=["Chats"])

@router.get("/", response_model=List[schemas.ChatListItemSchema])
def get_user_chats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all chat sessions for the logged-in user (for the sidebar)."""
    return service.get_chats_for_user(db=db, user=current_user)

@router.get("/{chat_id}", response_model=schemas.ChatHistoryResponseSchema)
def get_single_chat_history(
    chat_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the full message history for a specific chat."""
    chat = service.get_chat_history(db=db, chat_id=chat_id, user=current_user)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found or you don't have permission.")
    return chat 