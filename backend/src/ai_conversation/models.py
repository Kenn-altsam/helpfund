"""
Pydantic models for AI conversation functionality

Data models for AI conversation requests and responses.
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from pydantic import validator


class ConversationInput(BaseModel):
    """Legacy conversation input model for backwards compatibility"""
    
    user_input: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="User's message or query"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_input": "Can you help me find tech companies?"
            }
        }


class ChatRequest(BaseModel):
    """Request model for chat conversation with history"""
    
    user_input: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="User's message or query"
    )
    history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Conversation history with role and content"
    )
    assistant_id: Optional[str] = Field(
        None,
        description="Optional OpenAI Assistant ID for persistent conversations"
    )
    thread_id: Optional[str] = Field(
        None,
        description="Optional OpenAI Thread ID for persistent conversations"
    )
    
    @validator('history', pre=True, always=True)
    def validate_request_history(cls, v):
        """Validate and clean incoming history"""
        if not v:
            return []
        
        if not isinstance(v, list):
            print(f"⚠️ [MODELS] Request history is not a list: {type(v)}, converting to empty list")
            return []
        
        validated_history = []
        for i, item in enumerate(v):
            if isinstance(item, dict):
                # Be more flexible with the validation - just require some content
                role = item.get('role', '').strip()
                content = item.get('content', '').strip()
                
                if role and content:
                    validated_history.append({
                        'role': role,
                        'content': content
                    })
                else:
                    print(f"⚠️ [MODELS] Skipping history item {i} with missing role/content: {item}")
            else:
                print(f"⚠️ [MODELS] Skipping non-dict history item {i}: {type(item)}")
        
        print(f"✅ [MODELS] Request history validated: {len(v)} -> {len(validated_history)} items")
        return validated_history
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_input": "Can you help me find tech companies?",
                "history": [
                    {"role": "user", "content": "Hi there!"},
                    {"role": "assistant", "content": "Hello! I'm here to help you find potential corporate sponsors in Kazakhstan. How can I assist you today?"}
                ],
                "assistant_id": "asst_abc123",
                "thread_id": "thread_xyz789"
            }
        }


class ConversationResponse(BaseModel):
    """Legacy conversation response model for backwards compatibility"""
    
    message: str = Field(
        ..., 
        description="AI-generated response message"
    )
    required_fields: Optional[Dict[str, Optional[str]]] = Field(
        None,
        description="Required fields for completing the request"
    )
    is_complete: Optional[bool] = Field(
        None,
        description="Whether the conversation request is complete"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "I'd be happy to help you find tech companies! Could you tell me which region you're interested in?",
                "required_fields": {"region": None},
                "is_complete": False
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat conversation with history"""
    
    message: str = Field(
        ..., 
        description="AI-generated response message"
    )
    companies: List['CompanyData'] = Field(
        default_factory=list,
        description="List of company data found"
    )
    assistant_id: Optional[str] = Field(
        None,
        description="OpenAI Assistant ID used for this response"
    )
    thread_id: Optional[str] = Field(
        None,
        description="OpenAI Thread ID used for this response"
    )
    
    @validator('message', pre=True, always=True)
    def validate_message(cls, v):
        """Ensure message is always a non-empty string"""
        if not v or not isinstance(v, str):
            print("⚠️ [MODELS] Invalid message, using fallback")
            return "Произошла ошибка при обработке запроса."
        return v.strip()
    
    @validator('companies', pre=True, always=True)
    def validate_companies(cls, v):
        """Ensure companies is always a list"""
        if not isinstance(v, list):
            print(f"⚠️ [MODELS] companies is not a list: {type(v)}, converting to empty list")
            return []
        return v
    
    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "message": "Great! I found 5 companies in Almaty that might be interested in tech sponsorship...",
                "companies": [
                    {
                        "id": "123",
                        "name": "Tech Company LLP",
                        "activity": "Software development",
                        "locality": "Almaty",
                        "size": "Medium"
                    }
                ],
                "assistant_id": "asst_abc123",
                "thread_id": "thread_xyz789"
            }
        }


class CompanyData(BaseModel):
    """Model for company data in chat responses"""
    
    bin: str = Field(..., description="Business Identification Number")
    name: str = Field(..., description="Company name")
    registration_date: Optional[str] = Field(None, description="Registration date")
    address: Optional[str] = Field(None, description="Company address")
    activity: Optional[str] = Field(None, description="Business activity")
    annual_tax: Optional[float] = Field(None, description="Annual tax payment")
    website: Optional[str] = Field(None, description="Company website")
    contacts: Optional[Dict[str, str]] = Field(None, description="Contact information")

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "bin": "123456789012",
                "name": "Tech Solutions LLP",
                "registration_date": "2020-01-01",
                "address": "Almaty, Kazakhstan",
                "activity": "Software development",
                "annual_tax": 1000000.0,
                "website": "https://example.com",
                "contacts": {
                    "phone": "+7 777 123 4567",
                    "email": "contact@example.com"
                }
            }
        }


class APIResponse(BaseModel):
    """Standard API response wrapper"""
    
    status: str = Field(
        ..., 
        description="Response status (success/error)"
    )
    data: Union[
        ChatResponse,
        List[CompanyData], 
        List[Dict[str, Any]], 
        Dict[str, Any]
    ] = Field(
        ..., 
        description="Response data"
    )
    message: str = Field(
        ..., 
        description="Response message"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "data": {
                    "message": "I found some great companies for you!",
                    "companies": [],
                    "assistant_id": "asst_abc123",
                    "thread_id": "thread_xyz789"
                },
                "message": "Request processed successfully"
            }
        } 