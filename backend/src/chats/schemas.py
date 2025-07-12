import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List

# Schema for a single message in a chat history
class MessageSchema(BaseModel):
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

# Schema for displaying a chat in the sidebar list
class ChatListItemSchema(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime

    class Config:
        from_attributes = True

# Schema for returning the full history of a selected chat
class ChatHistoryResponseSchema(BaseModel):
    id: uuid.UUID
    title: str
    messages: List[MessageSchema]

    class Config:
        from_attributes = True 