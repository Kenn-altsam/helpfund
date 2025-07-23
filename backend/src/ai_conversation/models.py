"""
Pydantic models for AI conversation functionality

Data models for AI conversation requests and responses.
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from pydantic import validator
import uuid


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
    """Request model for chat conversation - history is loaded from database"""
    
    user_input: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="User's message or query"
    )
    assistant_id: Optional[str] = Field(
        None,
        description="Optional OpenAI Assistant ID for persistent conversations"
    )
    chat_id: Optional[str] = Field(
        None,
        description="Optional Database Chat ID (UUID) for persistent conversations. If not provided, a new chat will be created."
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_input": "Can you help me find tech companies?",
                "chat_id": str(uuid.uuid4())
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


class MessageDTO(BaseModel):
    """DTO for a single message in conversation history, including optional metadata"""

    role: str = Field(..., description="Sender role: user, assistant, system, etc.")
    content: str = Field(..., description="Message content")
    companies: Optional[List['CompanyData']] = Field(
        None,
        description="List of companies associated with this message (if any)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Arbitrary metadata associated with the message"
    )

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "role": "assistant",
                "content": "Отлично, я нашёл 3 компании по вашему запросу.",
                "companies": [
                    {
                        "bin": "123456789012",
                        "name": "Tech Solutions LLP",
                        "activity": "Software development",
                        "address": "Almaty, Kazakhstan"
                    }
                ],
                "metadata": {
                    "companies": [
                        {
                            "id": "123",
                            "name": "Tech Solutions LLP"
                        }
                    ]
                }
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
    updated_history: List[MessageDTO] = Field(
        default_factory=list,
        description="Full updated conversation history after this turn"
    )
    assistant_id: Optional[str] = Field(
        None,
        description="OpenAI Assistant ID used for this response"
    )
    chat_id: Optional[str] = Field(
        None,
        description="Database Chat ID (UUID) for this conversation"
    )
    openai_thread_id: Optional[str] = Field(
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
                "updated_history": [
                    {
                        "role": "assistant",
                        "content": "Отлично, я нашёл 3 компании по вашему запросу.",
                        "companies": [
                            {
                                "bin": "123456789012",
                                "name": "Tech Solutions LLP",
                                "activity": "Software development",
                                "address": "Almaty, Kazakhstan"
                            }
                        ],
                        "metadata": {
                            "companies": [
                                {
                                    "id": "123",
                                    "name": "Tech Solutions LLP"
                                }
                            ]
                        }
                    }
                ],
                "assistant_id": "asst_abc123",
                "chat_id": str(uuid.uuid4()),
                "openai_thread_id": "thread_xyz789"
            }
        }


class CompanyData(BaseModel):
    """Model for company data in chat responses"""
    
    bin: str = Field(..., description="Business Identification Number (BIN)")
    name: Optional[str] = Field(None, description="Company name")
    oked: Optional[str] = Field(None, description="OKED code")
    activity: Optional[str] = Field(None, description="Business activity")
    kato: Optional[str] = Field(None, description="KATO code")
    locality: Optional[str] = Field(None, description="Locality or region")
    krp: Optional[str] = Field(None, description="KRP code")
    size: Optional[str] = Field(None, description="Company size category")

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "bin": "123456789012",
                "name": "Tech Solutions LLP",
                "oked": "62011",
                "activity": "Computer programming activities",
                "kato": "751110000",
                "locality": "Almaty",
                "krp": "2",
                "size": "Medium",
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
                    "updated_history": [],
                    "assistant_id": "asst_abc123",
                    "chat_id": "some-uuid-string-here",
                    "openai_thread_id": "thread_xyz789"
                },
                "message": "Request processed successfully"
            }
        }


class CompanyCharityRequest(BaseModel):
    """Request model for company charity research"""
    
    company_name: str = Field(
        ..., 
        min_length=1, 
        max_length=200,
        description="Name of the company to research charity involvement"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "КазМунайГаз"
            }
        }


class CompanyCharityResponse(BaseModel):
    """Response model for company charity research"""
    
    status: str = Field(
        description="Status of the request (success/error/warning)"
    )
    answer: str = Field(description="AI analysis of company's charity involvement")
    
    @validator('status', pre=True, always=True)
    def validate_status(cls, v):
        """Ensure status is one of the allowed values"""
        allowed_statuses = ['success', 'error', 'warning']
        if v not in allowed_statuses:
            print(f"⚠️ [MODELS] Invalid status '{v}', using 'error'")
            return 'error'
        return v
    
    @validator('answer', pre=True, always=True)
    def validate_answer(cls, v):
        """Ensure answer is always a non-empty string"""
        if not v or not isinstance(v, str):
            print("⚠️ [MODELS] Invalid answer, using fallback")
            return "Произошла ошибка при обработке запроса."
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "answer": "Компания КазМунайГаз активно участвует в благотворительной деятельности..."
            }
        }


# ---------------------------------------------------------------------------
# Resolve forward references
# ---------------------------------------------------------------------------
MessageDTO.update_forward_refs()
ChatResponse.update_forward_refs() 