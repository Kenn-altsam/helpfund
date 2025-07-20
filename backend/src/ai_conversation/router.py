from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import traceback
import uuid
import httpx
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from .models import ChatRequest, ChatResponse, CompanyCharityRequest, CompanyCharityResponse
from .assistant_creator import handle_conversation_with_context
from ..core.database import get_db
from ..auth.models import User
from ..auth.dependencies import get_current_user
from ..chats import service as chat_service

router = APIRouter(prefix="/ai", tags=["AI Conversation"])


@router.post("/chat-assistant", response_model=ChatResponse)
def handle_chat_with_assistant(
    request: ChatRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) 
):
    """
    Handle an AI conversation turn with database persistence.
    - Manages chat history and OpenAI thread context via the database.
    - Saves the new conversation turn to the database.
    """
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty")
    
    db_chat_id: Optional[uuid.UUID] = None
    if request.chat_id:
        try:
            db_chat_id = uuid.UUID(request.chat_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid chat_id format. Must be a UUID.")

    print(f"✅ [ROUTER] Starting chat for user {current_user.id} with chat_id: {db_chat_id}")

    try:
        response_data = handle_conversation_with_context(
            user_input=request.user_input,
            db=db,
            user=current_user,
            chat_id=db_chat_id,
            assistant_id=request.assistant_id,
        )

        if "error" in response_data:
             raise HTTPException(status_code=500, detail=response_data.get("details", "An unknown error occurred in the AI handler."))

        return ChatResponse(
            message=response_data.get("response"),
            companies=response_data.get("companies_found", []),
            assistant_id=response_data.get('assistant_id'),
            chat_id=response_data.get('chat_id'),
            openai_thread_id=response_data.get("thread_id")
        )
        
    except Exception as e:
        print(f"❌ [ROUTER] Error in chat endpoint: {str(e)}")
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.post("/charity-research", response_model=CompanyCharityResponse)
async def get_company_charity_info(
    request: CompanyCharityRequest,
    current_user = Depends(get_current_user)
):
    """
    Research company's charity involvement using Google Search and Gemini AI.
    Searches for information about company's charitable activities without storing in database.
    """
    try:
        # Get API keys from environment
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        
        if not all([GOOGLE_API_KEY, SEARCH_ENGINE_ID, GEMINI_API_KEY]):
            raise HTTPException(
                status_code=500, 
                detail="API keys not configured. Please contact administrator."
            )
        
        # Search for charity information about the company
        query = f"{request.company_name} благотворительность OR charity OR спонсорство OR donation"
        search_url = (
            f"https://www.googleapis.com/customsearch/v1?q={query}"
            f"&key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}"
        )

        async with httpx.AsyncClient() as client:
            try:
                g_res = await client.get(search_url)
                g_res.raise_for_status()
                search_data = g_res.json()
                items = search_data.get("items", [])[:5]
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Google Search API error: {str(e)}")

        # Extract links and snippets
        links = [item.get("link", "") for item in items]
        snippets = [item.get("snippet", "") for item in items]

        # Create summary text for Gemini
        text_summary = "\n".join(snippets)
        
        # Create prompt for Gemini
        prompt = f"""
        Исходя из следующих результатов поиска, проанализируй участие компании '{request.company_name}' в благотворительной деятельности:

        {text_summary}

        Найденные ссылки:
        {chr(10).join(links)}

        Предоставь краткий и структурированный анализ:
        1. Участвует ли компания в благотворительности (да/нет/неизвестно)
        2. Какие конкретные благотворительные проекты или инициативы были найдены
        3. Регулярность участия (постоянно/периодически/разово)
        4. Сферы помощи (образование, здравоохранение, спорт, культура и т.д.)

        Ответь кратко, четко и на русском языке. Если информации недостаточно, так и укажи.
        """

        # Send request to Gemini API
        gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        gemini_payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        async with httpx.AsyncClient() as client:
            try:
                gemini_res = await client.post(gemini_url, json=gemini_payload)
                gemini_res.raise_for_status()
                g_data = gemini_res.json()
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")

        # Extract answer from Gemini response
        try:
            answer = g_data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            answer = "Не удалось получить анализ от AI. Попробуйте позже."

        print(f"✅ [CHARITY_RESEARCH] Successfully analyzed charity info for {request.company_name}")
        
        return CompanyCharityResponse(
            status="success",
            answer=answer
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [CHARITY_RESEARCH] Error analyzing charity info: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred during charity research.") 