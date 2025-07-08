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
    
    # Get or create fund profile for conversation state persistence
    fund_profile = db.query(FundProfile).filter(
        FundProfile.user_id == current_user.id
    ).first()
    
    # Load conversation history from database if available
    conversation_history = []
    if fund_profile and fund_profile.conversation_state:
        conversation_history = fund_profile.conversation_state.get('history', [])
        print(f"📚 Loaded {len(conversation_history)} messages from database")
    
    # Merge with history from request (request history takes precedence)
    if request.history:
        print(f"📝 Using {len(request.history)} messages from request")
        conversation_history = request.history
    else:
        print(f"📝 Using {len(conversation_history)} messages from database")
    
    # Handle the conversation
    response_data = await ai_service.handle_conversation_turn(
        user_input=request.user_input,
        history=conversation_history,
        db=db,
        conversation_id=str(fund_profile.id) if fund_profile else None
    )
    
    # Save updated conversation history to database
    if fund_profile:
        # Update the conversation state in the database
        updated_history = response_data.get('updated_history', [])
        fund_profile.conversation_state = {
            'history': updated_history,
            'last_intent': response_data.get('intent'),
            'last_location': response_data.get('location_detected'),
            'last_activity_keywords': response_data.get('activity_keywords')
        }
        db.commit()
        print(f"💾 Saved {len(updated_history)} messages to database")
    else:
        # Create fund profile if it doesn't exist
        new_profile = FundProfile(
            user_id=current_user.id,
            fund_name=f"{current_user.full_name}'s Fund",
            fund_description="Auto-created fund profile",
            fund_email=current_user.email,
            conversation_state={
                'history': response_data.get('updated_history', []),
                'last_intent': response_data.get('intent'),
                'last_location': response_data.get('location_detected'),
                'last_activity_keywords': response_data.get('activity_keywords')
            }
        )
        db.add(new_profile)
        db.commit()
        print(f"✨ Created new fund profile with conversation state")
    
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


# -------------------------------
# 📌 New endpoint: Save chat history
# -------------------------------


# -----------------------------
# 🗂 Chat summary data models  
# -----------------------------


class ChatHistoryItem(BaseModel):
    """Persistent chat summary for sidebar history"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_input: str
    companies_data: List[Dict[str, Any]]
    created_at: str  # ISO timestamp
    thread_id: Optional[str] = None
    assistant_id: Optional[str] = None

    class Config:
        extra = "allow"


# -----------------------------
# 🚚 Incoming save request model
# -----------------------------


class ChatHistorySaveRequest(BaseModel):
    """Incoming payload from the frontend when a new turn is made."""

    user_input: str
    companies_data: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str
    thread_id: Optional[str] = None
    assistant_id: Optional[str] = None
    id: Optional[str] = None  # Frontend-generated ID, if provided

    class Config:
        extra = "allow"


@router.post("/chat/history/save")
async def save_chat_history_item(
    request: ChatHistorySaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save a single chat history item for the authenticated user."""
    try:
        fund_profile = db.query(FundProfile).filter(FundProfile.user_id == current_user.id).first()

        # If profile doesn't exist, create a minimal one
        if not fund_profile:
            fund_profile = FundProfile(
                user_id=current_user.id,
                fund_name=f"{current_user.full_name}'s Fund",
                conversation_state={'history': [], 'chat_summaries': []}
            )
            db.add(fund_profile)
            db.flush()  # Retrieve ID before commit

        # Ensure conversation_state is initialized
        if not fund_profile.conversation_state:
            fund_profile.conversation_state = {'history': [], 'chat_summaries': []}

        state = fund_profile.conversation_state or {}

        # ---------------------------------
        # 1️⃣  Update sidebar chat summaries
        # ---------------------------------
        # NOTE: We do NOT modify the detailed 'history' log here.
        #       That log is managed exclusively by /chat.
        summaries: List[Dict[str, Any]] = state.get('chat_summaries', [])

        # Try to find existing summary by thread_id
        summary = None
        if request.thread_id:
            for s in summaries:
                if s.get('thread_id') == request.thread_id:
                    summary = s
                    break

        if summary:
            # Update in place
            summary['user_input'] = request.user_input
            summary['companies_data'] = request.companies_data
            summary['created_at'] = request.created_at
        else:
            # Create new summary
            new_summary = ChatHistoryItem(
                user_input=request.user_input,
                companies_data=request.companies_data,
                created_at=request.created_at,
                thread_id=request.thread_id,
                assistant_id=request.assistant_id
            ).dict()

            # If frontend supplied its own ID, preserve it
            if request.id:
                new_summary['id'] = request.id
            summaries.insert(0, new_summary)  # newest first

        # Persist updated state WITHOUT touching 'history'
        fund_profile.conversation_state = {
            **state,
            'chat_summaries': summaries
        }
        db.commit()

        return {"status": "success", "message": "History item saved."}

    except Exception as e:
        db.rollback()
        print(f"Error saving chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to save chat history.")


# -------------------------------
# 🗑️  Delete chat history item
# -------------------------------


@router.delete("/chat/history/{history_id}")
async def delete_chat_history_item(
    history_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a single chat summary by its id for the authenticated user."""
    try:
        fund_profile = db.query(FundProfile).filter(FundProfile.user_id == current_user.id).first()

        if not fund_profile or not fund_profile.conversation_state:
            raise HTTPException(status_code=404, detail="No conversation history found")

        state = fund_profile.conversation_state
        summaries: List[Dict[str, Any]] = state.get('chat_summaries', [])

        # Filter out the summary with the specified id
        new_summaries = [s for s in summaries if str(s.get('id')) != history_id]

        if len(new_summaries) == len(summaries):
            raise HTTPException(status_code=404, detail="History item not found")

        # Persist updated state
        state['chat_summaries'] = new_summaries
        fund_profile.conversation_state = state
        db.commit()

        return {"status": "success", "message": "History item deleted."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting chat history item: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete chat history item.")


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