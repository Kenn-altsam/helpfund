from sqlalchemy.orm import Session
from . import models, schemas
from .router import get_password_hash  # Reuse the password hashing utility

def get_user_by_username(db: Session, username: str):
    """Get user by username - placeholder implementation"""
    # TODO: Implement actual user lookup from database
    return None

def create_user(db: Session, user: schemas.UserCreate):
    """Create a new user and persist it to the database."""
    # Hash the incoming password
    hashed_password = get_password_hash(user.password)

    # Build the SQLAlchemy model instance
    db_user = models.User(
        email=user.email.lower(),  # Normalize email for consistency
        hashed_password=hashed_password,
        full_name=getattr(user, "full_name", ""),  # Ensure full_name is provided
        is_active=True,
        is_verified=False,
    )

    db.add(db_user)  # Add the user to the current session

    db.commit()         # Persist changes
    db.refresh(db_user) # Load generated fields (e.g., id)

    return db_user
