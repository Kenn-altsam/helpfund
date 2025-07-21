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
from .service import ai_service
from ..core.database import get_db
from ..auth.models import User
from ..auth.dependencies import get_current_user
from ..chats import service as chat_service
from ..gemini_client import get_gemini_response

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
    import time
    start_time = time.time()
    
    print(f"💬 [CHAT_ASSISTANT] New chat request from user {current_user.id}")
    print(f"📝 [CHAT_ASSISTANT] Input length: {len(request.user_input)} characters")
    
    if not request.user_input.strip():
        print(f"❌ [CHAT_ASSISTANT] Empty input rejected")
        raise HTTPException(status_code=400, detail="User input cannot be empty")

    print(f"🚀 [CHAT_ASSISTANT] Starting conversation processing for user {current_user.id}")
    print(f"🔗 [CHAT_ASSISTANT] Chat ID from request: {request.chat_id}")

    try:
        result = ai_service.handle_conversation_turn(
            user_input=request.user_input,
            history=request.history,
            db=db,
            conversation_id=request.chat_id, # Используем chat_id из запроса
            current_user=current_user
        )

        companies_count = len(result.get("companies", []))
        total_duration = time.time() - start_time
        
        print(f"✅ [CHAT_ASSISTANT] Successfully processed chat in {total_duration:.2f}s")
        print(f"🏢 [CHAT_ASSISTANT] Found {companies_count} companies in response")

        return ChatResponse(
            message=result["message"],
            companies=result["companies"],
            updated_history=result["updated_history"],
            intent=result["intent"],
            location=result["location_detected"],
            activity_keywords=result["activity_keywords_detected"],
            quantity=result["quantity_detected"],
            page_number=result["page_number"],
            companies_found=result["companies_found"],
            has_more_companies=result["has_more_companies"],
            reasoning=result["reasoning"],
            chat_id=result.get("chat_id"),
            assistant_id=result.get("assistant_id"),  # Для совместимости
            thread_id=result.get("thread_id"),        # Для совместимости
            openai_thread_id=result.get("thread_id")  # Для совместимости
        )
        
    except Exception as e:
        total_duration = time.time() - start_time
        print(f"❌ [CHAT_ASSISTANT] Error in chat endpoint after {total_duration:.2f}s: {str(e)}")
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500, 
            detail="Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."
        )


@router.post("/charity-research", response_model=CompanyCharityResponse)
async def get_company_charity_info(
    request: CompanyCharityRequest,
    current_user = Depends(get_current_user)
):
    """
    Research company's charity involvement using Google Search and Gemini AI.
    Searches for information about company's charitable activities without storing in database.
    """
    import time
    start_time = time.time()
    
    print(f"🔍 [CHARITY_RESEARCH] Starting research for company: '{request.company_name}'")
    print(f"👤 [CHARITY_RESEARCH] Requested by user ID: {current_user.id}")
    
    try:
        # Get API keys from environment
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        
        print(f"🔑 [CHARITY_RESEARCH] API keys status - Google: {'✓' if GOOGLE_API_KEY else '✗'}, Search Engine: {'✓' if SEARCH_ENGINE_ID else '✗'}, Gemini: {'✓' if GEMINI_API_KEY else '✗'}")
        
        if not all([GOOGLE_API_KEY, SEARCH_ENGINE_ID, GEMINI_API_KEY]):
            print(f"❌ [CHARITY_RESEARCH] Missing API keys - cannot proceed")
            return CompanyCharityResponse(
                status="error",
                answer="Сервис временно недоступен. Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
        
        # Search for charity information about the company
        query = f"{request.company_name} благотворительность OR charity OR спонсорство OR donation"
        search_url = (
            f"https://www.googleapis.com/customsearch/v1?q={query}"
            f"&key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}"
        )
        
        print(f"🔍 [CHARITY_RESEARCH] Google search query: '{query}'")
        print(f"🌐 [CHARITY_RESEARCH] Sending request to Google Custom Search API...")

        async with httpx.AsyncClient() as client:
            try:
                google_start_time = time.time()
                g_res = await client.get(search_url)
                g_res.raise_for_status()
                search_data = g_res.json()
                items = search_data.get("items", [])[:5]
                google_duration = time.time() - google_start_time
                print(f"✅ [CHARITY_RESEARCH] Google Search completed in {google_duration:.2f}s - found {len(items)} results")
            except httpx.RequestError as e:
                print(f"❌ [CHARITY_RESEARCH] Google Search API error: {str(e)}")
                return CompanyCharityResponse(
                    status="error",
                    answer="Не удалось найти информацию о компании в интернете. Возможно, проблема с подключением к поисковой системе."
                )
            except httpx.HTTPStatusError as e:
                print(f"❌ [CHARITY_RESEARCH] Google Search HTTP error {e.response.status_code}: {str(e)}")
                return CompanyCharityResponse(
                    status="error",
                    answer="Поисковая система временно недоступна. Пожалуйста, попробуйте позже."
                )

        # Extract links and snippets
        links = [item.get("link", "") for item in items]
        snippets = [item.get("snippet", "") for item in items]
        
        print(f"📋 [CHARITY_RESEARCH] Extracted {len(links)} links and {len(snippets)} snippets")
        if links:
            print(f"🔗 [CHARITY_RESEARCH] Top search results domains: {', '.join([link.split('/')[2] if '/' in link else link for link in links[:3]])}")

        # Check if we have enough data to proceed
        if not snippets or not any(snippets):
            print(f"⚠️ [CHARITY_RESEARCH] No search results found for company '{request.company_name}'")
            return CompanyCharityResponse(
                status="warning",
                answer=f"Данных о благотворительной деятельности компании '{request.company_name}' не найдено в открытых источниках."
            )

        # Create summary text for Gemini
        text_summary = "\n".join(snippets)
        summary_length = len(text_summary)
        print(f"📝 [CHARITY_RESEARCH] Created summary text with {summary_length} characters for Gemini analysis")
        
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

        ВАЖНО: Если в найденных результатах поиска нет конкретной информации о благотворительной деятельности компании, используй один из следующих fallback ответов:

        - "Данных о благотворительной деятельности компании '{request.company_name}' не найдено в открытых источниках."
        - "Компания '{request.company_name}' могла участвовать в благотворительности, но достоверных источников не найдено."
        - "Информация о благотворительной активности компании '{request.company_name}' отсутствует в найденных источниках."

        Ответь кратко, четко и на русском языке. Если информации недостаточно, используй fallback ответ.
        """

        # Send request to Gemini API
        gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

        gemini_payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        print(f"🤖 [CHARITY_RESEARCH] Sending analysis request to Gemini 2.0 Flash API...")
        print(f"📊 [CHARITY_RESEARCH] Prompt length: {len(prompt)} characters")

        async with httpx.AsyncClient() as client:
            try:
                gemini_start_time = time.time()
                gemini_res = await client.post(gemini_url, json=gemini_payload)
                gemini_res.raise_for_status()
                g_data = gemini_res.json()
                gemini_duration = time.time() - gemini_start_time
                print(f"✅ [CHARITY_RESEARCH] Gemini API response received in {gemini_duration:.2f}s")
            except httpx.RequestError as e:
                print(f"❌ [CHARITY_RESEARCH] Gemini API error: {str(e)}")
                return CompanyCharityResponse(
                    status="error",
                    answer="Не удалось проанализировать найденную информацию. Проблема с подключением к AI сервису."
                )
            except httpx.HTTPStatusError as e:
                print(f"❌ [CHARITY_RESEARCH] Gemini API HTTP error {e.response.status_code}: {str(e)}")
                return CompanyCharityResponse(
                    status="error",
                    answer="AI сервис временно недоступен. Пожалуйста, попробуйте позже."
                )

        # Extract answer from Gemini response
        try:
            answer = g_data["candidates"][0]["content"]["parts"][0]["text"]
            answer_length = len(answer)
            print(f"📝 [CHARITY_RESEARCH] Gemini analysis extracted - length: {answer_length} characters")
            
            # Validate that we got a meaningful response
            if not answer or len(answer.strip()) < 10:
                print(f"⚠️ [CHARITY_RESEARCH] Gemini returned empty or too short response")
                return CompanyCharityResponse(
                    status="warning",
                    answer=f"Компания '{request.company_name}' могла участвовать в благотворительности, но достоверных источников не найдено."
                )
                
        except (KeyError, IndexError) as e:
            print(f"⚠️ [CHARITY_RESEARCH] Failed to extract answer from Gemini response: {str(e)}")
            return CompanyCharityResponse(
                status="error",
                answer="Не удалось обработать ответ от AI. Пожалуйста, попробуйте позже."
            )

        total_duration = time.time() - start_time
        print(f"✅ [CHARITY_RESEARCH] Successfully completed analysis for '{request.company_name}' in {total_duration:.2f}s")
        print(f"📊 [CHARITY_RESEARCH] Final response size: {len(answer)} characters")
        
        return CompanyCharityResponse(
            status="success",
            answer=answer
        )

    except Exception as e:
        total_duration = time.time() - start_time
        print(f"❌ [CHARITY_RESEARCH] Unexpected error analyzing charity info for '{request.company_name}' after {total_duration:.2f}s: {str(e)}")
        traceback.print_exc()
        return CompanyCharityResponse(
            status="error",
            answer="Произошла непредвиденная ошибка при анализе. Пожалуйста, попробуйте позже или обратитесь к администратору."
        ) 