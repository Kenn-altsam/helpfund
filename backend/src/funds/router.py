"""
API Router for fund profile endpoints

Provides endpoints for charity fund profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import uuid4

from .models import FundProfile
from .schemas import FundProfileCreate, FundProfileResponse
# Import correct models from ai_conversation
from ..ai_conversation.models import ChatRequest, ChatResponse
from ..auth.router import get_current_user
from ..auth.models import User
from ..core.database import get_db
from src.ai_conversation.service import ai_service
# --- 💡 NEW: Import charity_assistant for thread interactions ---
from ..ai_conversation.assistant_creator import charity_assistant


# Create router
router = APIRouter(
    prefix="/funds",
    tags=["Fund Profiles"],
    responses={
        404: {"description": "Not found"},
        401: {"description": "Authentication required"}
    }
)


@router.post("/chat", response_model=ChatResponse)
async def handle_chat(
    request: ChatRequest, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Handle stateful AI conversation with history tracking and database persistence.
    This endpoint manages conversation state per user and maintains history in the database.
    """
    print(f"Request made by user: {current_user.email}")

    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty")
    
    # Use the new chat system instead of FundProfile.conversation_state
    # The conversation history is now managed by the chat service
    conversation_history = request.history or []
    
    # Handle the conversation using the new chat system
    response_data = await ai_service.handle_conversation_turn(
        user_input=request.user_input,
        history=conversation_history,
        db=db,
        conversation_id=request.chat_id  # Use chat_id from request
    )
    
    return ChatResponse(**response_data)


@router.get("/chat/history", response_model=List[Dict[str, Any]])
async def get_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve the chat history for the authenticated user.
    Now uses the new chat system instead of FundProfile.conversation_state.
    """
    try:
        # Use the new chat service to get user's chats
        from ..chats import service as chat_service
        chats = chat_service.get_chats_for_user(db=db, user=current_user)
        
        # Convert to the expected format
        chat_summaries = []
        for chat in chats:
            chat_summaries.append({
                'id': str(chat.id),
                'title': chat.title,
                'created_at': chat.created_at.isoformat(),
                'updated_at': chat.updated_at.isoformat(),
                'thread_id': chat.openai_thread_id,
                'assistant_id': chat.openai_assistant_id
            })
        
        return chat_summaries
    except Exception as e:
        print(f"Error fetching chat history for user {current_user.id}: {e}")
        # In case of error, return empty list to avoid breaking frontend
        return []


@router.post("/chat/reset")
async def reset_conversation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset/clear conversation history for the current user.
    Now uses the new chat system instead of FundProfile.conversation_state.
    """
    try:
        # Use the new chat service to delete user's chats
        from ..chats import service as chat_service
        chats = chat_service.get_chats_for_user(db=db, user=current_user)
        
        # Delete all user's chats
        for chat in chats:
            chat_service.delete_chat_from_db(db=db, chat_id=chat.id, user_id=current_user.id)
        
        print(f"Reset conversation history for user {current_user.id}")
        return {"message": "Conversation history reset successfully"}
    except Exception as e:
        print(f"Error resetting conversation history for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset conversation history")


@router.post("/profile", response_model=FundProfileResponse)
async def create_fund_profile(
    profile_data: FundProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create or update fund profile"""
    # Check if profile already exists
    existing_profile = db.query(FundProfile).filter(
        FundProfile.user_id == current_user.id
    ).first()
    
    if existing_profile:
        # Update existing profile
        existing_profile.fund_name = profile_data.fund_name
        existing_profile.fund_description = profile_data.fund_description
        existing_profile.fund_email = profile_data.fund_email
        db.commit()
        db.refresh(existing_profile)
        profile = existing_profile
    else:
        # Create new profile
        profile = FundProfile(
            user_id=current_user.id,
            fund_name=profile_data.fund_name,
            fund_description=profile_data.fund_description,
            fund_email=profile_data.fund_email
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    
    return FundProfileResponse(
        id=str(profile.id),
        fund_name=profile.fund_name,
        fund_description=profile.fund_description,
        fund_email=profile.fund_email,
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat()
    )


@router.get("/profile", response_model=FundProfileResponse)
async def get_fund_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's fund profile"""
    profile = db.query(FundProfile).filter(
        FundProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fund profile not found"
        )
    
    return FundProfileResponse(
        id=str(profile.id),
        fund_name=profile.fund_name,
        fund_description=profile.fund_description,
        fund_email=profile.fund_email,
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat()
    )


@router.delete("/profile")
async def delete_fund_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete current user's fund profile"""
    profile = db.query(FundProfile).filter(
        FundProfile.user_id == current_user.id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fund profile not found"
        )
    
    db.delete(profile)
    db.commit()
    
    return {"message": "Fund profile deleted successfully"}

# The chat history save and delete endpoints have been moved to the chats router.
# The related Pydantic models (ChatHistoryItem, ChatHistorySaveRequest)
# and the endpoints save_chat_history_item and delete_chat_history_item
# have been removed from this file.


# --- 💡 NEW ENDPOINT: Retrieve full OpenAI thread history ---
@router.get("/chat/thread/{thread_id}/history", response_model=List[Dict[str, Any]])
async def get_thread_history(
    thread_id: str,
    current_user: User = Depends(get_current_user)
):
    """Retrieve the full conversation history from an OpenAI thread."""
    try:
        history = await charity_assistant.get_conversation_history(thread_id)
        return history
    except Exception as e:
        print(f"Error fetching thread history for user {current_user.id}: {e}")
        raise HTTPException(status_code=404, detail="Thread history not found or an error occurred.") 