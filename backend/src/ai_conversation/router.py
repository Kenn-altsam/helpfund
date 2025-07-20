from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import traceback
import uuid
import httpx
import os
import asyncio
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

from .models import ChatRequest, ChatResponse, CompanyCharityRequest, CompanyCharityResponse
from .assistant_creator import handle_conversation_with_context
from ..core.database import get_db
from ..auth.models import User
from ..auth.dependencies import get_current_user
from ..chats import service as chat_service

router = APIRouter(prefix="/ai", tags=["AI Conversation"])


async def filter_valid_links(links: List[str], timeout: float = 5.0) -> List[str]:
    """
    Проверяет доступность ссылок с помощью HEAD-запросов.
    Возвращает только те ссылки, которые отвечают успешно.
    
    Args:
        links: Список URL для проверки
        timeout: Таймаут для каждого запроса в секундах
        
    Returns:
        Список доступных ссылок
    """
    if not links:
        return []
    
    print(f"🔍 [LINK_VALIDATION] Checking {len(links)} links for availability...")
    
    async def check_link(url: str) -> tuple[str, bool]:
        """Проверяет одну ссылку и возвращает (url, is_valid)"""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Используем HEAD запрос для экономии трафика
                response = await client.head(url, follow_redirects=True)
                is_valid = response.status_code < 400  # 2xx и 3xx считаем валидными
                if is_valid:
                    print(f"✅ [LINK_VALIDATION] {url} - Status: {response.status_code}")
                else:
                    print(f"❌ [LINK_VALIDATION] {url} - Status: {response.status_code}")
                return url, is_valid
        except httpx.TimeoutException:
            print(f"⏰ [LINK_VALIDATION] {url} - Timeout after {timeout}s")
            return url, False
        except httpx.RequestError as e:
            print(f"🌐 [LINK_VALIDATION] {url} - Request error: {str(e)}")
            return url, False
        except Exception as e:
            print(f"⚠️ [LINK_VALIDATION] {url} - Unexpected error: {str(e)}")
            return url, False
    
    try:
        # Проверяем все ссылки параллельно
        tasks = [check_link(url) for url in links]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Фильтруем валидные ссылки
        valid_links = []
        for result in results:
            if isinstance(result, tuple):
                url, is_valid = result
                if is_valid:
                    valid_links.append(url)
            elif isinstance(result, Exception):
                print(f"⚠️ [LINK_VALIDATION] Task failed with exception: {str(result)}")
        
        print(f"✅ [LINK_VALIDATION] Found {len(valid_links)} valid links out of {len(links)}")
        if valid_links:
            print(f"🔗 [LINK_VALIDATION] Valid domains: {', '.join([link.split('/')[2] if '/' in link else link for link in valid_links[:3]])}")
        
        return valid_links
        
    except Exception as e:
        print(f"❌ [LINK_VALIDATION] Critical error during link validation: {str(e)}")
        # В случае критической ошибки возвращаем все ссылки как валидные
        print(f"🔄 [LINK_VALIDATION] Falling back to using all links without validation")
        return links


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

    print(f"🚀 [CHAT_ASSISTANT] Starting conversation processing for user {current_user.id}")

    try:
        response_data = handle_conversation_with_context(
            user_input=request.user_input,
            db=db,
            user=current_user,
            chat_id=db_chat_id,
            assistant_id=request.assistant_id,
        )

        if "error" in response_data:
            print(f"❌ [CHAT_ASSISTANT] AI handler returned error: {response_data.get('details', 'Unknown error')}")
            raise HTTPException(status_code=500, detail=response_data.get("details", "An unknown error occurred in the AI handler."))

        companies_count = len(response_data.get("companies_found", []))
        total_duration = time.time() - start_time
        
        print(f"✅ [CHAT_ASSISTANT] Successfully processed chat in {total_duration:.2f}s")
        print(f"🏢 [CHAT_ASSISTANT] Found {companies_count} companies in response")
        print(f"💭 [CHAT_ASSISTANT] Chat ID: {response_data.get('chat_id')}, Thread ID: {response_data.get('thread_id')}")

        return ChatResponse(
            message=response_data.get("response"),
            companies=response_data.get("companies_found", []),
            assistant_id=response_data.get('assistant_id'),
            chat_id=response_data.get('chat_id'),
            openai_thread_id=response_data.get("thread_id")
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

        # Validate links before sending to Gemini
        valid_links = await filter_valid_links(links)
        print(f"🔗 [CHARITY_RESEARCH] Using {len(valid_links)} valid links out of {len(links)} total links for Gemini analysis")
        
        # Create summary text for Gemini
        text_summary = "\n".join(snippets)
        summary_length = len(text_summary)
        print(f"📝 [CHARITY_RESEARCH] Created summary text with {summary_length} characters for Gemini analysis")
        
        # Create search links for sources using only valid links
        search_links = "\n".join(f"- {url}" for url in valid_links)
        
        # Check if we have valid links for Gemini
        if not valid_links:
            print(f"⚠️ [CHARITY_RESEARCH] No valid links found after validation - proceeding with snippets only")
            search_links = "ВАЖНО: Доступные источники не найдены. Отвечай ТОЛЬКО на основе описаний выше."
        
        # Create prompt for Gemini
        prompt = f"""
        Компания: {request.company_name}

        ВАЖНО: Отвечай ТОЛЬКО на основе достоверной информации из предоставленных ссылок и описаний.
        
        Задача: Найди информацию об участии этой компании в благотворительности, спонсорстве или пожертвованиях.

        Описание из результатов поиска:
        {text_summary}

        Ссылки на источники:
        {search_links}

        ПРАВИЛА ОТВЕТА:
        1. Отвечай ТОЛЬКО на основе информации из ссылок и описаний выше
        2. Если ни в одной из ссылок не упоминается благотворительность — напиши, что такой информации не найдено
        3. НЕ ВЫДУМЫВАЙ информацию, которой нет в источниках
        4. Если информация есть — обязательно процитируй источник с URL
        5. Будь кратким и точным
        6. Если информации недостаточно для однозначного ответа — так и скажи

        Ответь строго по этим правилам.
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
                    answer=f"Информации о благотворительной деятельности компании '{request.company_name}' в открытых источниках не найдено."
                )
            
            # Additional validation to ensure answer doesn't contain fabricated information
            answer_lower = answer.lower()
            if "не найдено" in answer_lower or "не найдена" in answer_lower or "информации нет" in answer_lower:
                print(f"✅ [CHARITY_RESEARCH] Gemini correctly reported no information found")
            elif "http" in answer_lower and any(domain in answer_lower for domain in [link.split('/')[2] if '/' in link else link for link in valid_links]):
                print(f"✅ [CHARITY_RESEARCH] Gemini provided response with source citations")
            else:
                print(f"⚠️ [CHARITY_RESEARCH] Gemini response may lack proper source citations")
                
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