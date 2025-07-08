from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import traceback
from .models import ChatRequest, ChatResponse, APIResponse, ConversationInput, ConversationResponse
from .service import ai_service
from .assistant_creator import (
    handle_conversation_with_context,
    create_charity_fund_assistant,
    charity_assistant
)
from ..core.database import get_db
from typing import Optional

router = APIRouter(prefix="/ai", tags=["AI Conversation"])


@router.post("/chat-assistant", response_model=ChatResponse)
async def handle_chat_with_assistant(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Handle AI conversation using the enhanced OpenAI Assistant with full context preservation.
    
    This endpoint provides:
    - OpenAI Assistants API with function calling
    - Full conversation history preservation
    - Database function tools integration
    - Enhanced context awareness
    - Persistent conversation threads
    """
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty")
    
    # Validate and log history for debugging
    history = request.history if request.history else []
    print(f"🎯 [ASSISTANT-ROUTER] Received request with history length: {len(history)}")
    print(f"📝 [ASSISTANT-ROUTER] User input: {request.user_input[:100]}...")
    
    # Validate history format
    validated_history = []
    for i, item in enumerate(history):
        if isinstance(item, dict) and 'role' in item and 'content' in item:
            validated_history.append(item)
        else:
            print(f"⚠️ [ASSISTANT-ROUTER] Invalid history item at index {i}: {item}")
    
    print(f"✅ [ASSISTANT-ROUTER] Validated history length: {len(validated_history)}")

    try:
        # Use the enhanced context-aware assistant
        print(f"🤖 [ASSISTANT-ROUTER] Calling enhanced assistant...")
        
        response_data = await handle_conversation_with_context(
            user_input=request.user_input,
            conversation_history=validated_history,
            db=db,
            assistant_id=request.assistant_id,
            thread_id=request.thread_id
        )
        
        # Validate response data structure
        if not isinstance(response_data, dict):
            print(f"❌ [ASSISTANT-ROUTER] Invalid response_data type: {type(response_data)}")
            raise ValueError("Invalid response format from assistant")
        
        # Ensure required fields exist
        required_fields = ['message', 'companies', 'updated_history', 'assistant_id', 'thread_id']
        for field in required_fields:
            if field not in response_data:
                print(f"❌ [ASSISTANT-ROUTER] Missing required field: {field}")
                if field in ('companies', 'companies_data') or field.endswith('_data') or field.endswith('_history'):
                    response_data[field] = []
                else:
                    response_data[field] = ""
        
        # Log response for debugging
        returned_history_length = len(response_data.get('updated_history', []))
        print(f"✅ [ASSISTANT-ROUTER] Assistant returned response with history length: {returned_history_length}")
        print(f"💬 [ASSISTANT-ROUTER] Response message: {response_data.get('message', '')[:100]}...")
        
        return ChatResponse(
            message=response_data['message'],
            companies=response_data.get('companies', []),
            updated_history=response_data.get('updated_history', []),
            assistant_id=response_data['assistant_id'],
            thread_id=response_data['thread_id']
        )
        
    except Exception as e:
        print(f"❌ [ASSISTANT-ROUTER] Error in chat endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat-hybrid", response_model=ChatResponse)
async def handle_chat_hybrid(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Handle AI conversation using hybrid approach: Enhanced assistant with fallback.
    
    This endpoint provides:
    - Primary: Enhanced OpenAI Assistant with function calling
    - Fallback: Traditional OpenAI service if assistant fails
    - Full conversation history preservation in both modes
    - Robust error handling and context preservation
    """
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty")
    
    # Validate and log history for debugging
    history = request.history if request.history else []
    print(f"🔗 [HYBRID-ROUTER] Received request with history length: {len(history)}")
    print(f"📝 [HYBRID-ROUTER] User input: {request.user_input[:100]}...")
    
    # Validate history format
    validated_history = []
    for i, item in enumerate(history):
        if isinstance(item, dict) and 'role' in item and 'content' in item:
            validated_history.append(item)
        else:
            print(f"⚠️ [HYBRID-ROUTER] Invalid history item at index {i}: {item}")
    
    print(f"✅ [HYBRID-ROUTER] Validated history length: {len(validated_history)}")

    try:
        # Use the hybrid service with fallback
        print(f"🔗 [HYBRID-ROUTER] Calling hybrid service...")
        response_data = await ai_service.handle_conversation_with_assistant_fallback(
            user_input=request.user_input,
            history=validated_history,
            db=db
        )
        
        # Validate response data structure
        if not isinstance(response_data, dict):
            print(f"❌ [HYBRID-ROUTER] Invalid response_data type: {type(response_data)}")
            raise ValueError("Invalid response format from hybrid service")
        
        # Ensure required fields exist
        required_fields = ['message', 'companies', 'updated_history']
        for field in required_fields:
            if field not in response_data:
                print(f"❌ [HYBRID-ROUTER] Missing required field: {field}")
                if field in ('companies', 'companies_data') or field.endswith('_data') or field.endswith('_history'):
                    response_data[field] = []
                else:
                    response_data[field] = ""
        
        # Log response for debugging
        returned_history_length = len(response_data.get('updated_history', []))
        print(f"✅ [HYBRID-ROUTER] Hybrid service returned response with history length: {returned_history_length}")
        print(f"💬 [HYBRID-ROUTER] Response message: {response_data.get('message', '')[:100]}...")
        
        # Create and return ChatResponse
        chat_response = ChatResponse(**response_data)
        print(f"✅ [HYBRID-ROUTER] Successfully created ChatResponse with {len(chat_response.updated_history)} history items")
        return chat_response
        
    except Exception as e:
        print(f"❌ [HYBRID-ROUTER] Error in hybrid endpoint: {str(e)}")
        print(f"🔍 [HYBRID-ROUTER] Exception type: {type(e)}")
        traceback.print_exc()
        
        # Return a safe response that preserves history
        print(f"🛡️ [HYBRID-ROUTER] Creating emergency fallback response...")
        fallback_history = validated_history + [
            {"role": "user", "content": request.user_input},
            {"role": "assistant", "content": "Извините, произошла критическая ошибка в системе. Ваша история разговора сохранена. Попробуйте позже."}
        ]
        
        print(f"🛡️ [HYBRID-ROUTER] Emergency fallback history length: {len(fallback_history)}")
        
        fallback_response = ChatResponse(
            message="Извините, произошла критическая ошибка в системе. Ваша история разговора сохранена. Попробуйте позже.",
            companies=[],
            updated_history=fallback_history,
            intent="error",
            companies_found=0,
            has_more_companies=False
        )
        
        print(f"✅ [HYBRID-ROUTER] Created emergency fallback response with {len(fallback_response.updated_history)} history items")
        return fallback_response


@router.post("/assistant/create")
async def create_assistant():
    """
    Create a new charity fund discovery assistant.
    Returns the assistant ID that can be used for future conversations.
    """
    try:
        assistant_id = await create_charity_fund_assistant()
        return {
            "status": "success",
            "data": {
                "assistant_id": assistant_id,
                "message": "Assistant created successfully"
            }
        }
    except Exception as e:
        print(f"❌ Error creating assistant: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create assistant: {str(e)}")


@router.get("/assistant/{assistant_id}/history/{thread_id}")
async def get_conversation_history(assistant_id: str, thread_id: str):
    """
    Get conversation history from an assistant thread.
    """
    try:
        history = await charity_assistant.get_conversation_history(thread_id)
        return {
            "status": "success",
            "data": {
                "assistant_id": assistant_id,
                "thread_id": thread_id,
                "history": history,
                "total_messages": len(history)
            }
        }
    except Exception as e:
        print(f"❌ Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")


@router.delete("/assistant/{assistant_id}")
async def cleanup_assistant(assistant_id: str):
    """
    Clean up an assistant when no longer needed.
    """
    try:
        await charity_assistant.cleanup_assistant(assistant_id)
        return {
            "status": "success",
            "data": {
                "assistant_id": assistant_id,
                "message": "Assistant cleaned up successfully"
            }
        }
    except Exception as e:
        print(f"❌ Error cleaning up assistant: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup assistant: {str(e)}")


@router.post("/conversation", response_model=APIResponse)
async def handle_conversation(request: ConversationInput, db: Session = Depends(get_db)):
    """
    Handle AI conversation endpoint (legacy support for frontend compatibility)
    
    This endpoint provides the same functionality as /chat but wraps the response
    in APIResponse format for frontend compatibility. Uses ConversationInput for
    backwards compatibility with existing frontend code.
    """
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty")
    
    print(f"📍 [ROUTER] Legacy conversation endpoint called with input: {request.user_input[:100]}...")
    
    try:
        # Handle conversation turn with empty history for legacy support
        response_data = await ai_service.handle_conversation_turn(
            user_input=request.user_input,
            history=[],
            db=db
        )
        
        # Convert to legacy ConversationResponse format
        conversation_response = ConversationResponse(
            message=response_data["message"],
            required_fields=None,
            is_complete=True
        )
        
        return APIResponse(
            status="success",
            data=conversation_response,
            message="Conversation processed successfully"
        )
        
    except Exception as e:
        print(f"❌ [ROUTER] Error in legacy conversation endpoint: {str(e)}")
        traceback.print_exc()
        
        # Return error response
        conversation_response = ConversationResponse(
            message="Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз.",
            required_fields=None,
            is_complete=True
        )
        
        return APIResponse(
            status="error",
            data=conversation_response,
            message="Error processing conversation"
        )


@router.post("/conversation-simple", response_model=APIResponse)
async def handle_simple_conversation(request: ConversationInput, db: Session = Depends(get_db)):
    """
    Handle simple AI conversation endpoint (legacy support for frontend compatibility)
    
    Simplified conversation endpoint that processes single messages without complex
    history management, suitable for basic chat interactions.
    """
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty")
    
    print(f"📍 [ROUTER] Simple conversation endpoint called with input: {request.user_input[:100]}...")
    
    try:
        # For simple conversation, use empty history
        simple_history = []
        
        # Handle conversation turn
        response_data = await ai_service.handle_conversation_turn(
            user_input=request.user_input,
            history=simple_history,
            db=db
        )
        
        # Convert to legacy ConversationResponse format
        conversation_response = ConversationResponse(
            message=response_data["message"],
            required_fields=None,
            is_complete=True
        )
        
        return APIResponse(
            status="success",
            data=conversation_response,
            message="Simple conversation processed successfully"
        )
        
    except Exception as e:
        print(f"❌ [ROUTER] Error in simple conversation endpoint: {str(e)}")
        traceback.print_exc()
        
        # Return error response
        conversation_response = ConversationResponse(
            message="Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз.",
            required_fields=None,
            is_complete=True
        )
        
        return APIResponse(
            status="error",
            data=conversation_response,
            message="Error processing simple conversation"
        )


@router.get("/chat/health")
async def ai_health_check():
    """Check if AI conversation service is available"""
    try:
        if ai_service.settings.openai_api_key:
            return APIResponse(
                status="success",
                data={"service": "ai-conversation", "available": True},
                message="AI conversation service is available"
            )
        else:
            raise HTTPException(status_code=503, detail="AI service configuration missing")
    except Exception as e:
        print(f"❌ [ROUTER] Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="AI service unavailable")


@router.get("/chat/test-pagination")
async def test_pagination(
    location: str = Query(..., description="Location to search"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Results per page"),
    activity_keywords: Optional[str] = Query(None, description="Comma-separated activity keywords"),
    db: Session = Depends(get_db)
):
    """
    Test pagination functionality directly without AI parsing
    This endpoint helps debug pagination issues by bypassing the OpenAI intent parsing
    """
    try:
        print(f"🧪 [TEST_PAGINATION] Testing pagination:")
        print(f"   location: {location}")
        print(f"   page: {page}")
        print(f"   limit: {limit}")
        print(f"   activity_keywords: {activity_keywords}")
        
        # Parse activity keywords
        parsed_keywords = None
        if activity_keywords:
            parsed_keywords = [kw.strip() for kw in activity_keywords.split(",") if kw.strip()]
        
        # Calculate offset
        offset = (page - 1) * limit
        print(f"   calculated offset: {offset}")
        
        # Search companies
        from ..companies.service import CompanyService
        company_service = CompanyService(db)
        
        companies = await company_service.search_companies(
            location=location,
            activity_keywords=parsed_keywords,
            limit=limit,
            offset=offset
        )
        
        # Check if there are more results
        next_page_companies = await company_service.search_companies(
            location=location,
            activity_keywords=parsed_keywords,
            limit=1,
            offset=offset + limit
        )
        has_more = len(next_page_companies) > 0
        
        return APIResponse(
            status="success",
            data={
                "companies": companies,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "offset": offset,
                    "companies_returned": len(companies),
                    "has_more": has_more
                },
                "debug_info": {
                    "location_used": location,
                    "activity_keywords_used": parsed_keywords,
                    "next_page_preview": len(next_page_companies) > 0
                }
            },
            message=f"Pagination test completed. Found {len(companies)} companies on page {page}"
        )
        
    except Exception as e:
        print(f"❌ [TEST_PAGINATION] Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Pagination test failed: {str(e)}"
        ) 