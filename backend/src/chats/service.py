# backend/src/chats/service.py

import uuid
from sqlalchemy.orm import Session
from typing import List, Optional

from . import models
from ..auth.models import User # Your User model

def get_chats_for_user(db: Session, user: User) -> List[models.Chat]:
    """Fetches all chat sessions for a specific user, ordered by most recent."""
    return db.query(models.Chat).filter(models.Chat.user_id == user.id).order_by(models.Chat.updated_at.desc()).all()

def get_chat_history(db: Session, chat_id: uuid.UUID, user: User) -> Optional[models.Chat]:
    """
    Fetches a single chat with its messages, ensuring the user owns it.
    The `lazy="joined"` in the model ensures messages are loaded efficiently.
    """
    return db.query(models.Chat).filter(models.Chat.id == chat_id, models.Chat.user_id == user.id).first()

def save_conversation_turn(
    db: Session,
    user: User,
    user_message_content: str,
    ai_message_content: str,
    chat_id: Optional[uuid.UUID] = None,
    ai_message_data: Optional[dict] = None  # Add this parameter
) -> models.Chat:
    """
    Saves a user message and an AI response to the database.
    Creates a new chat if chat_id is not provided.
    """
    if chat_id:
        # Find existing chat and verify ownership
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id, models.Chat.user_id == user.id).first()
        if not chat:
            raise ValueError("Chat not found or permission denied.")
    else:
        # Create a new chat
        chat = models.Chat(
            user_id=user.id,
            title=user_message_content[:40] + "..." # Auto-generate title
        )
        db.add(chat)
        db.flush() # Flush to get the new chat.id

    # Create the user message
    user_message = models.Message(
        chat_id=chat.id,
        role="user",
        content=user_message_content
    )
    # Create the assistant message
    ai_message = models.Message(
        chat_id=chat.id,
        role="assistant",
        content=ai_message_content,
        data=ai_message_data  # Save the data here
    )
    
    db.add_all([user_message, ai_message])
    db.commit()
    db.refresh(chat)
    
    return chat 