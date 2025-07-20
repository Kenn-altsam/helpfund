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
        
        # Проверка API ключей
        if not all([GOOGLE_API_KEY, SEARCH_ENGINE_ID, GEMINI_API_KEY]):
            print(f"❌ [CHARITY_RESEARCH] Missing API keys - cannot proceed")
            return CompanyCharityResponse(
                status="error",
                answer="Сервис временно недоступен. Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
        
        # Дополнительная проверка Gemini API ключа
        if not GEMINI_API_KEY or len(GEMINI_API_KEY.strip()) < 10:
            print(f"❌ [CHARITY_RESEARCH] Invalid Gemini API key format")
            return CompanyCharityResponse(
                status="error",
                answer="Проблема с конфигурацией AI сервиса. Обратитесь к администратору."
            )
        
        # Search for charity information about the company
        query = f"{request.company_name} благотворительность OR charity OR спонсорство OR donation site:facebook.com OR site:instagram.com OR site:x.com"
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
        
        # Clean text and links before creating prompt
        import re

        # Очистка текста от лишних символов (например, emoji, HTML, спецзнаков)
        def clean_text(text):
            if text is None:
                return ""
            text = str(text)
            text = re.sub(r"<[^>]+>", "", text)  # удаление HTML-тегов
            text = re.sub(r"[^\x00-\x7Fа-яА-ЯёЁ\s.,:;!?()/-]", "", text)  # только допустимые символы
            return text.replace('\r', '').replace('\u200b', '').strip()

        text_summary_clean = clean_text(text_summary)
        links_clean = [link.strip() for link in links]
        
        # Ограничиваем длину summary
        if len(text_summary_clean) > 1000:
            text_summary_clean = text_summary_clean[:1000] + "..."
        
        print(f"🧹 [CHARITY_RESEARCH] Cleaned text summary: {len(text_summary_clean)} characters (was {len(text_summary)})")
        
        # Дополнительная очистка и валидация данных
        if not text_summary_clean or len(text_summary_clean.strip()) < 10:
            print(f"⚠️ [CHARITY_RESEARCH] Cleaned text summary is too short or empty")
            return CompanyCharityResponse(
                status="warning",
                answer=f"Недостаточно данных для анализа благотворительной деятельности компании '{request.company_name}'."
            )
        
        # Проверяем, что у нас есть хотя бы одна ссылка
        valid_links = [link for link in links_clean if link and link.startswith('http')]
        if not valid_links:
            print(f"⚠️ [CHARITY_RESEARCH] No valid links found")
            return CompanyCharityResponse(
                status="warning",
                answer=f"Не найдено достоверных источников информации о компании '{request.company_name}'."
            )
        
        # Дополнительная очистка данных для payload
        def clean_for_payload(text):
            if text is None:
                return ""
            # Убираем лишние пробелы, переносы строк и спецсимволы
            text = str(text).strip()
            text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Убираем множественные переносы
            text = re.sub(r'\s+', ' ', text)  # Заменяем множественные пробелы на один
            text = re.sub(r'None|NaN|undefined', '', text)  # Убираем служебные значения
            return text.strip()

        # Очищаем все данные для payload
        company_name_clean = clean_for_payload(request.company_name)
        text_summary_clean = clean_for_payload(text_summary_clean)
        links_clean = [clean_for_payload(link) for link in links_clean if link and link.strip()]
        
        # Проверяем, что данные не пустые после очистки
        if not company_name_clean or not text_summary_clean or not links_clean:
            print(f"❌ [CHARITY_RESEARCH] Data validation failed after cleaning")
            return CompanyCharityResponse(
                status="error",
                answer="Ошибка подготовки данных для анализа."
            )
        
        # Create prompt for Gemini
        prompt = f"""Проанализируй участие компании «{company_name_clean}» в благотворительности на основе данных ниже.

🔹 Описание:
{text_summary_clean}

🔹 Ссылки:
{chr(10).join(links_clean)}

Если среди ссылок есть соцсети (Facebook, Instagram и т.д.) — учти содержание.

Дай структурированный вывод:

1. Участвует ли в благотворительности (да / нет / неизвестно)
2. Какие инициативы были найдены
3. Регулярность (постоянно / периодически / разово)
4. Основные направления помощи (например: образование, дети, здравоохранение и т.д.)
5. Упоминания в соцсетях:
   – Платформа (например, Instagram)
   – Краткое описание, только если есть по ссылке

⚠️ Не придумывай. Используй только факты из текста и ссылок. Если информации недостаточно — выбери один из вариантов:

- «Информация о благотворительной деятельности компании «{company_name_clean}» не найдена.»
- «Компания могла участвовать, но подтверждений не обнаружено.»
- «Достоверных сведений о благотворительности не найдено.»

Заверши блоком:

Источники:
- [домен или название] – [ссылка]

Пример:
Источники:
- Facebook – https://facebook.com/...
- Официальный сайт – https://company.com/...

Ответь кратко и по делу, на русском языке."""
        
        # Финальная очистка промпта
        prompt = clean_for_payload(prompt)
        
        print(f"🧹 [CHARITY_RESEARCH] Final prompt length: {len(prompt)} characters")
        print(f"🔍 [CHARITY_RESEARCH] Prompt preview: {prompt[:200]}...")

        # Send request to Gemini API
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={GEMINI_API_KEY}"

        # Формируем корректный payload
        gemini_payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt  # строка, очищенная от None и спецсимволов
                        }
                    ]
                }
            ]
        }
        
        # Валидация payload структуры
        if not isinstance(prompt, str) or not prompt.strip():
            print(f"❌ [CHARITY_RESEARCH] Invalid prompt type or empty: {type(prompt)}")
            return CompanyCharityResponse(
                status="error",
                answer="Ошибка подготовки запроса к AI сервису."
            )
        
        print(f"📦 [CHARITY_RESEARCH] Payload structure validated")
        print(f"📝 [CHARITY_RESEARCH] Payload text type: {type(prompt)}")
        print(f"📏 [CHARITY_RESEARCH] Payload text length: {len(prompt)}")
        
        # Валидация payload перед отправкой
        if not prompt or len(prompt.strip()) < 50:
            print(f"❌ [CHARITY_RESEARCH] Invalid prompt - too short or empty")
            return CompanyCharityResponse(
                status="error",
                answer="Ошибка подготовки запроса к AI сервису."
            )
        
        # Проверяем размер payload (Gemini имеет лимиты)
        payload_size = len(str(gemini_payload))
        if payload_size > 30000:  # Примерный лимит для Gemini
            print(f"⚠️ [CHARITY_RESEARCH] Payload too large: {payload_size} characters")
            # Обрезаем промпт если он слишком большой
            prompt = prompt[:2000] + "..."
            gemini_payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            print(f"📝 [CHARITY_RESEARCH] Truncated prompt to {len(prompt)} characters")
        
        print(f"🤖 [CHARITY_RESEARCH] Sending analysis request to Gemini 2.5 Pro API...")
        print(f"📊 [CHARITY_RESEARCH] Prompt length: {len(prompt)} characters")
        print(f"📦 [CHARITY_RESEARCH] Payload size: {payload_size} characters")

        async with httpx.AsyncClient() as client:
            try:
                gemini_start_time = time.time()
                gemini_res = await client.post(gemini_url, json=gemini_payload)
                gemini_duration = time.time() - gemini_start_time
                
                if not gemini_res.is_success:
                    status_code = gemini_res.status_code
                    error_text = gemini_res.text
                    
                    print(f"❌ [CHARITY_RESEARCH] Gemini API error: {status_code}")
                    print(f"📄 [CHARITY_RESEARCH] Gemini error body: {error_text}")
                    
                    # Попытка получить детали ошибки из JSON ответа
                    try:
                        error_json = gemini_res.json()
                        print(f"🔍 [CHARITY_RESEARCH] Gemini error details: {error_json}")
                    except:
                        print(f"🔍 [CHARITY_RESEARCH] Could not parse error response as JSON")
                    
                    # Обработка конкретных ошибок Gemini API
                    if status_code == 400:
                        print(f"🔍 [CHARITY_RESEARCH] Bad request - возможно, слишком длинный промпт или некорректные токены")
                        return CompanyCharityResponse(
                            status="error",
                            answer="Ошибка в запросе к AI сервису. Возможно, слишком много данных для анализа."
                        )
                    elif status_code == 403:
                        print(f"🔑 [CHARITY_RESEARCH] Forbidden - неверный или истёкший API-ключ")
                        return CompanyCharityResponse(
                            status="error",
                            answer="Проблема с доступом к AI сервису. Обратитесь к администратору."
                        )
                    elif status_code == 429:
                        print(f"⏱️ [CHARITY_RESEARCH] Rate limit exceeded - превышен лимит запросов")
                        return CompanyCharityResponse(
                            status="error",
                            answer="Превышен лимит запросов к AI сервису. Попробуйте позже."
                        )
                    elif status_code >= 500:
                        print(f"🚨 [CHARITY_RESEARCH] Server error - ошибка на стороне Gemini")
                        return CompanyCharityResponse(
                            status="error",
                            answer="Временная ошибка AI сервиса. Попробуйте позже."
                        )
                    else:
                        return CompanyCharityResponse(
                            status="error",
                            answer="AI сервис временно недоступен. Пожалуйста, попробуйте позже."
                        )
                
                g_data = gemini_res.json()
                print(f"✅ [CHARITY_RESEARCH] Gemini API response received in {gemini_duration:.2f}s")
                print(f"📊 [CHARITY_RESEARCH] Response status: {gemini_res.status_code}")
                print(f"📄 [CHARITY_RESEARCH] Response size: {len(gemini_res.text)} characters")
                
                # Логируем структуру ответа для отладки
                if "candidates" in g_data:
                    print(f"✅ [CHARITY_RESEARCH] Response contains {len(g_data['candidates'])} candidates")
                else:
                    print(f"⚠️ [CHARITY_RESEARCH] Response structure: {list(g_data.keys())}")
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
            
            # Добавляем список ссылок в конец ответа
            final_answer = answer.strip()
            if valid_links:
                final_answer += "\n\nИсточники:\n"
                for i, link in enumerate(valid_links):
                    final_answer += f"{i+1}. {link}\n"
                print(f"🔗 [CHARITY_RESEARCH] Added {len(valid_links)} source links to response")
            else:
                final_answer = answer.strip()
                print(f"⚠️ [CHARITY_RESEARCH] No valid links to add to response")
                
        except (KeyError, IndexError) as e:
            print(f"⚠️ [CHARITY_RESEARCH] Failed to extract answer from Gemini response: {str(e)}")
            return CompanyCharityResponse(
                status="error",
                answer="Не удалось обработать ответ от AI. Пожалуйста, попробуйте позже."
            )

        total_duration = time.time() - start_time
        print(f"✅ [CHARITY_RESEARCH] Successfully completed analysis for '{request.company_name}' in {total_duration:.2f}s")
        print(f"📊 [CHARITY_RESEARCH] Final response size: {len(final_answer)} characters")
        
        return CompanyCharityResponse(
            status="success",
            answer=final_answer
        )

    except Exception as e:
        total_duration = time.time() - start_time
        print(f"❌ [CHARITY_RESEARCH] Unexpected error analyzing charity info for '{request.company_name}' after {total_duration:.2f}s: {str(e)}")
        traceback.print_exc()
        return CompanyCharityResponse(
            status="error",
            answer="Произошла непредвиденная ошибка при анализе. Пожалуйста, попробуйте позже или обратитесь к администратору."
        ) 