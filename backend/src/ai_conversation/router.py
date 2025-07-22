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
async def handle_chat_with_assistant(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle an AI conversation turn using Gemini API.
    - Uses Gemini for text generation.
    - Persists chat history in the database.
    """
    import time
    start_time = time.time()
    import uuid
    import os
    from ..chats import service as chat_service

    print(f"💬 [CHAT_ASSISTANT] New chat request from user {current_user.id}")
    print(f"📝 [CHAT_ASSISTANT] Input length: {len(request.user_input)} characters")

    if not request.user_input.strip():
        print(f"❌ [CHAT_ASSISTANT] Empty input rejected")
        raise HTTPException(status_code=400, detail="User input cannot be empty")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key is not configured.")

    db_chat_id: Optional[uuid.UUID] = None
    if request.chat_id:
        try:
            db_chat_id = uuid.UUID(request.chat_id)
            print(f"🔗 [CHAT_ASSISTANT] Using existing chat ID: {db_chat_id}")
        except ValueError:
            print(f"❌ [CHAT_ASSISTANT] Invalid chat_id format: {request.chat_id}")
            raise HTTPException(status_code=400, detail="Invalid chat_id format. Must be a UUID.")
    else:
        print(f"🆕 [CHAT_ASSISTANT] Creating new chat session")

    # Формируем историю для prompt
    history = request.history or []
    prompt_parts = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            prompt_parts.append(f"Пользователь: {content}")
        elif role == "assistant":
            prompt_parts.append(f"Ассистент: {content}")
    prompt_parts.append(f"Пользователь: {request.user_input}")
    prompt = "\n".join(prompt_parts)

    gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    gemini_payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    print(f"🤖 [CHAT_ASSISTANT] Sending request to Gemini API...")
    print(f"📊 [CHAT_ASSISTANT] Prompt length: {len(prompt)} characters")

    import httpx
    try:
        async with httpx.AsyncClient() as client:
            gemini_start_time = time.time()
            gemini_res = await client.post(gemini_url, json=gemini_payload)
            gemini_res.raise_for_status()
            g_data = gemini_res.json()
            gemini_duration = time.time() - gemini_start_time
            print(f"✅ [CHAT_ASSISTANT] Gemini API response received in {gemini_duration:.2f}s")
    except httpx.RequestError as e:
        print(f"❌ [CHAT_ASSISTANT] Gemini API error: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка подключения к Gemini API.")
    except httpx.HTTPStatusError as e:
        print(f"❌ [CHAT_ASSISTANT] Gemini API HTTP error {e.response.status_code}: {str(e)}")
        raise HTTPException(status_code=500, detail="Gemini API временно недоступен.")

    # Извлекаем ответ
    try:
        answer = g_data["candidates"][0]["content"]["parts"][0]["text"]
        answer_length = len(answer)
        print(f"📝 [CHAT_ASSISTANT] Gemini answer extracted - length: {answer_length} characters")
    except (KeyError, IndexError) as e:
        print(f"⚠️ [CHAT_ASSISTANT] Failed to extract answer from Gemini response: {str(e)}")
        raise HTTPException(status_code=500, detail="Не удалось обработать ответ от Gemini.")

    # Сохраняем сообщения в базу (если есть chat_id)
    updated_history = history + [{"role": "user", "content": request.user_input}, {"role": "assistant", "content": answer}]
    if db_chat_id:
        chat_service.create_message(db, chat_id=db_chat_id, content=request.user_input, role="user")
        chat_service.create_message(db, chat_id=db_chat_id, content=answer, role="assistant")
    # Если нет chat_id, можно создать новый чат (опционально)

    total_duration = time.time() - start_time
    print(f"✅ [CHAT_ASSISTANT] Successfully processed chat in {total_duration:.2f}s")

    return ChatResponse(
        message=answer,
        companies=[],
        updated_history=updated_history,
        assistant_id=None,
        chat_id=str(db_chat_id) if db_chat_id else None,
        openai_thread_id=None
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
        
        # Create search links for sources
        search_links = "\n".join(f"- {url}" for url in links)
        
        # Create prompt for Gemini
        prompt = f"""
        Компания: {request.company_name}

        Найди информацию об участии этой компании в благотворительности, спонсорстве или пожертвованиях. Используй описания и ссылки ниже.

        Описание из результатов поиска:
        {text_summary}

        Ссылки на источники:
        {search_links}

        Ответь кратко. Укажи, участвовала ли компания в благотворительности, и обязательно процитируй хотя бы один источник с URL в ответе.
        Если информации недостаточно — так и скажи.
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