import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Any

# Schema for a single message in a chat history
class MessageSchema(BaseModel):
    role: str
    content: str
    created_at: datetime
    data: Optional[Any] = None

    class Config:
        from_attributes = True

# Schema for displaying a chat in the sidebar list
class ChatListItemSchema(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime
    thread_id: Optional[str] = Field(None, alias="thread_id")  # ✅ Мапится из thread_id
    assistant_id: Optional[str] = Field(None, alias="assistant_id")  # ✅ Мапится из assistant_id

    class Config:
        from_attributes = True
        # Маппинг полей из модели в схему
        alias_generator = None  # Отключаем автоматический camelCase
        populate_by_name = True  # Позволяет использовать snake_case

# Schema for returning the full history of a selected chat
class ChatHistoryResponseSchema(BaseModel):
    id: uuid.UUID
    title: str
    messages: List[MessageSchema]

    class Config:
        from_attributes = True 