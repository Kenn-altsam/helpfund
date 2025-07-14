# backend/src/chats/service.py

import uuid
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

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

def save_chat_summary_to_db(
    db: Session,
    user_id: uuid.UUID,
    thread_id: str,
    assistant_id: str,
    user_prompt: str,
    raw_ai_response: List[Any],
    created_at: str, # ISO 8601 string
    chat_id: Optional[uuid.UUID] = None,
) -> models.Chat:
    """
    Saves or updates a chat summary. It finds a chat by thread_id and user_id.
    If it exists, it updates the title. If not, it creates a new chat.
    It also stores the raw_ai_response in a placeholder message.
    """
    # Try to find an existing chat by thread_id for this user
    chat = db.query(models.Chat).filter(
        models.Chat.openai_thread_id == thread_id,
        models.Chat.user_id == user_id
    ).first()

    if chat:
        # Update existing chat's title
        chat.title = user_prompt
        # Optionally, clear old placeholder AI responses if needed
        # (for now, we just add a new one)
    else:
        # Create a new chat if it doesn't exist
        chat = models.Chat(
            id=chat_id or uuid.uuid4(),
            user_id=user_id,
            openai_thread_id=thread_id,
            openai_assistant_id=assistant_id,
            title=user_prompt,
            # The 'created_at' from the request is a string, we parse it.
            # The database will set its own created_at, but we can set updated_at.
            updated_at=datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        )
        db.add(chat)
        db.flush() # We need the chat.id for the message

    # Create a placeholder message to store the raw AI response,
    # as there's no direct column for it on the Chat model.
    # This keeps the data associated with the turn.
    placeholder_message = models.Message(
        chat_id=chat.id,
        role="assistant_summary", # A special role to distinguish it
        content="Placeholder for raw AI response from this turn.",
        data={"companies_found": raw_ai_response}
    )
    db.add(placeholder_message)

    db.commit()
    db.refresh(chat)
    return chat

def delete_chat_from_db(db: Session, chat_id: uuid.UUID, user_id: uuid.UUID):
    """
    Deletes a chat session from the database, ensuring the user owns it.
    """
    chat_to_delete = db.query(models.Chat).filter(
        models.Chat.id == chat_id,
        models.Chat.user_id == user_id
    ).first()

    if not chat_to_delete:
        # We can raise an error that will be caught in the router
        raise ValueError("Chat not found or permission denied.")

    db.delete(chat_to_delete)
    db.commit()


# --- Functions needed by assistant_creator.py ---

def get_chat_by_id(db: Session, chat_id: uuid.UUID, user_id: uuid.UUID) -> Optional[models.Chat]:
    """
    Retrieves a chat session by its ID and ensures it belongs to the given user.
    """
    return db.query(models.Chat).filter(models.Chat.id == chat_id, models.Chat.user_id == user_id).first()

def create_chat(
    db: Session,
    user_id: uuid.UUID,
    name: str, # `assistant_creator.py` passes 'name', which should map to 'title' in your Chat model
    openai_assistant_id: Optional[str] = None,
    openai_thread_id: Optional[str] = None
) -> models.Chat:
    """
    Creates a new chat session in the database.
    """
    db_chat = models.Chat(
        user_id=user_id,
        title=name, # Map the 'name' parameter to the 'title' field of your Chat model
        openai_assistant_id=openai_assistant_id,
        openai_thread_id=openai_thread_id
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    print(f"✅ Created new chat in DB: {db_chat.id} with title: '{db_chat.title}'")
    return db_chat

def update_chat_openai_ids(
    db: Session,
    chat_id: uuid.UUID,
    new_assistant_id: str,
    new_thread_id: str
) -> Optional[models.Chat]:
    """
    Updates the OpenAI assistant and thread IDs for an existing chat.
    """
    db_chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if db_chat:
        db_chat.openai_assistant_id = new_assistant_id
        db_chat.openai_thread_id = new_thread_id
        db_chat.updated_at = datetime.now() # Ensure updated_at is updated, use datetime.now() for timezone-aware
        db.commit()
        db.refresh(db_chat)
        print(f"✅ Updated chat {chat_id} with new OpenAI IDs")
    return db_chat

def create_message(
    db: Session,
    chat_id: uuid.UUID,
    content: str,
    role: str,
    metadata: Optional[Dict[str, Any]] = None # `assistant_creator.py` passes 'metadata'
) -> models.Message:
    """
    Creates a new message record in the database for a given chat.
    """
    db_message = models.Message(
        chat_id=chat_id,
        content=content,
        role=role,
        data=metadata # Map the 'metadata' parameter to the 'data' field of your Message model
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    print(f"✅ Created new message in DB for chat {chat_id} (role: {role})")
    return db_message

# --- Existing function (can coexist or be refactored) ---
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
    
    NOTE: This function handles both messages in one go.
    The `create_chat` and `create_message` functions above are more granular
    and match the `assistant_creator.py`'s current logic.
    You might consider refactoring `assistant_creator.py` to use `save_conversation_turn`
    if it fits your desired flow better.
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
            title=user_message_content[:40] + "..." # Auto-generate title for new chat
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