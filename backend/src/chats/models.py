import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from ..core.database import Base # Assuming your Base is in core.database

class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # This is the crucial link to your existing Users table.
    # Make sure 'users.id' matches the primary key of your User model.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Локальная система контекста - не зависит от API
    thread_id = Column(String, nullable=True, index=True, unique=True)  # ✅ Локальная сессия
    assistant_id = Column(String, nullable=True, index=True)            # ✅ ID модели (gemini-1.5-pro)
    
    title = Column(String(255), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # This creates the link so you can access messages from a chat object
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan", lazy="joined")
    user = relationship("User", back_populates="chats")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # This links a message to a specific chat session
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 'user' or 'assistant'
    role = Column(String(16), nullable=False) 
    content = Column(Text, nullable=False)
    
    # This will store structured data, like the list of companies for this message.
    # It has no size limit like OpenAI's metadata.
    data = Column(JSONB, nullable=True) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # This creates the link back to the Chat object
    chat = relationship("Chat", back_populates="messages") 