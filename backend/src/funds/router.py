"""
API Router for fund profile endpoints

Provides endpoints for charity fund profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from .models import FundProfile
from .schemas import FundProfileCreate, FundProfileResponse
# Import correct models from ai_conversation
from ..ai_conversation.models import ChatRequest, ChatResponse
from ..auth.router import get_current_user
from ..auth.models import User
from ..core.database import get_db
from src.ai_conversation.service import ai_service


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
        fund_profile.conversation_state = {'history': []}
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