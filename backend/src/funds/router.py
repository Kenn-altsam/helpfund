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
from ..ai_conversation.assistant_creator import handle_conversation_with_context


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
    
    # The new `handle_conversation_with_context` will manage its own state.
    # We no longer need to manually load or save the history here.
    
    response_data = handle_conversation_with_context(
        user_input=request.user_input,
        db=db,
        user=current_user,
        chat_id=request.chat_id,
        assistant_id=request.assistant_id
    )
    
    # The new function returns a dictionary that is already compatible
    # with the ChatResponse model.
    return ChatResponse(**response_data)


@router.get("/chat/history", response_model=List[Dict[str, Any]])
async def get_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve the chat history for the authenticated user.
    """
    try:
        fund_profile = db.query(FundProfile).filter(
            FundProfile.user_id == current_user.id
        ).first()

        if fund_profile and fund_profile.conversation_state:
            # Extract chat summaries (sidebar items)
            summaries = fund_profile.conversation_state.get('chat_summaries', [])
            return summaries
        
        # If no profile or history, return an empty list
        return []
    except Exception as e:
        print(f"Error fetching chat history for user {current_user.id}: {e}")
        # In case of error, return empty list to avoid breaking frontend
        return []


@router.post("/chat/reset")
async def reset_conversation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset/clear conversation history for the current user"""
    fund_profile = db.query(FundProfile).filter(
        FundProfile.user_id == current_user.id
    ).first()
    
    if fund_profile:
        state = fund_profile.conversation_state or {}
        state['history'] = []  # clear only detailed log
        # Preserve existing chat_summaries if any
        if 'chat_summaries' not in state:
            state['chat_summaries'] = []

        fund_profile.conversation_state = state
        db.commit()
        print(f"🔄 Reset conversation history for user: {current_user.email}")
        return {"message": "Conversation history reset successfully"}
    else:
        return {"message": "No conversation history found to reset"}


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
    # This functionality might be deprecated if Gemini doesn't use threads.
    # For now, we raise a NotImplementedError.
    raise HTTPException(status_code=501, detail="Thread history is not available with the current AI service.") 