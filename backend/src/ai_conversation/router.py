from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import traceback
import uuid
import os
import httpx
import json
import re
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv

from .models import ChatRequest, ChatResponse, CompanyCharityRequest, CompanyCharityResponse, GoogleSearchResult
# !!! ИМПОРТИРУЕМ НАШ ГЛАВНЫЙ СЕРВИС !!!
from .service import ai_service
from ..core.database import get_db
from ..auth.models import User
from ..auth.dependencies import get_current_user
from ..chats import service as chat_service  # Сервис для сохранения истории чатов
from ..chats.models import Chat  # Модель чата для проверки принадлежности

router = APIRouter(prefix="/ai", tags=["AI Conversation"])

# ============================================================================== 
# === ИНИЦИАЛИЗАЦИЯ API КЛЮЧЕЙ ДЛЯ GOOGLE SEARCH ===
# ==============================================================================
# Загружаем .env файл из корня проекта (на два уровня вверх от текущего файла)
import pathlib
env_path = pathlib.Path(__file__).parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY не установлен в переменных окружения. Проверьте ваш .env файл.")
if not GOOGLE_SEARCH_ENGINE_ID:
    raise RuntimeError("GOOGLE_SEARCH_ENGINE_ID не установлен в переменных окружения. Проверьте ваш .env файл.")


# ============================================================================== 
# === НОВЫЙ, ПРАВИЛЬНЫЙ ЭНДПОИНТ ДЛЯ ПОИСКА КОМПАНИЙ ЧЕРЕЗ БД ===
# ==============================================================================
@router.post("/chat", response_model=ChatResponse)
async def handle_chat_with_database_search(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handles a conversation turn by parsing user intent, searching the database for companies,
    and generating a response. This is the main endpoint for company search.
    """
    print(f"\U0001F4AC [CHAT_DB] New request from user {current_user.id}: '{request.user_input[:100]}...'")

    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty")

    try:
        # 1. Определяем ID чата для сохранения истории
        db_chat_id = None
        if request.chat_id:
            try:
                db_chat_id = uuid.UUID(request.chat_id)
                print(f"🔄 [CHAT_DB] Using existing chat session: {db_chat_id}")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid chat_id format. Must be a UUID.")
        else:
            # Если ID чата не предоставлен, создаем новый чат в БД
            chat_name = request.user_input[:100]
            new_chat = chat_service.create_chat(
                db=db,
                user_id=current_user.id,
                name=chat_name
            )
            db_chat_id = new_chat.id
            print(f"🆕 [CHAT_DB] Created new chat session '{chat_name}' with ID: {db_chat_id}")

        # 2. Вызываем основную логику из ai_service.py
        # Сервис теперь сам загружает историю из БД и сохраняет новые сообщения
        response_data = await ai_service.handle_conversation_turn(
            user_input=request.user_input,
            history=[],  # Больше не используется, сервис загружает из БД
            db=db,
            conversation_id=str(db_chat_id)
        )
        
        # 3. Формируем и возвращаем финальный ответ для фронтенда
        # Сообщения уже сохранены в сервисе, дублирования нет
        final_response = ChatResponse(
            message=response_data.get('message'),
            companies=response_data.get('companies', []),
            updated_history=response_data.get('updated_history', []),
            assistant_id=None, # У вас нет OpenAI Assistant ID в этой логике
            chat_id=str(db_chat_id),
            openai_thread_id=None
        )

        print(f"✅ [CHAT_DB] Successfully processed request. Found {len(final_response.companies)} companies.")
        return final_response

    except Exception as e:
        print(f"❌ [CHAT_DB] Critical error in chat endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Произошла непредвиденная ошибка на сервере.")


@router.get("/chat/{chat_id}/history")
async def get_chat_history_for_ai(
    chat_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получает историю чата в формате, оптимизированном для AI диалогов.
    Возвращает историю в том же формате, что используется в updated_history.
    """
    try:
        # Проверяем формат UUID
        chat_uuid = uuid.UUID(chat_id)
        
        # Загружаем историю используя AI service
        history = ai_service._load_chat_history_from_db(db, chat_uuid)
        
        # Проверяем, что чат принадлежит пользователю
        chat = db.query(Chat).filter(
            Chat.id == chat_uuid,
            Chat.user_id == current_user.id
        ).first()
        
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found or access denied")
        
        return {
            "chat_id": str(chat_uuid),
            "title": chat.title,
            "history": history,
            "total_messages": len(history)
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format. Must be a UUID.")
    except Exception as e:
        print(f"❌ [AI_HISTORY] Error getting chat history: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history.")





# ============================================================================== 
# === НОВЫЙ ЭНДПОИНТ ДЛЯ АНАЛИЗА БЛАГОТВОРИТЕЛЬНОСТИ (ОБНОВЛЕННЫЙ КОД) ===
# ==============================================================================
@router.post("/charity-research", response_model=CompanyCharityResponse)
async def get_company_charity_info(
    request: CompanyCharityRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Performs a multi-vector Google search for a company's charity and social activities.
    """
    company_name = request.company_name
    print(f"🌟 [ADVANCED_RESEARCH] Starting multi-vector research for: '{company_name}'")

    if not company_name.strip():
        raise HTTPException(status_code=400, detail="Название компании не может быть пустым.")

    # --- Вектор 1: Очистка названия ---
    clean_company_name = re.sub(r'^(ТОО|АО|ИП|A\.O\.|TOO|LLP|JSC|)\s*|"|«|»', '', company_name, flags=re.IGNORECASE).strip()
    print(f"   -> Cleaned name: '{clean_company_name}'")

    # --- Вектор 2: Формирование поисковых запросов ---
    # Мы будем использовать три разных типа запросов
    
    # Тип А: Прямой поиск благотворительности (как и раньше, но улучшенный)
    charity_keywords = " OR ".join(['"благотворительность"', '"пожертвования"', '"спонсорство"', '"социальная ответственность"', '"помощь фонду"'])
    query_direct_charity = f'"{clean_company_name}" AND ({charity_keywords}) AND ("Казахстан" OR "Kazakhstan" OR site:kz)'

    # Тип Б: Поиск по HR-бренду и корпоративной культуре (НОВЫЙ ВЕКТОР!)
    # Здесь мы ищем страницы "О нас", "Карьера", "Наши ценности" и соцсети
    hr_keywords = " OR ".join(['"наша команда"', '"корпоративная жизнь"', '"наши ценности"', '"тимбилдинг"', '"мероприятия компании"'])
    query_hr_brand = f'"{clean_company_name}" AND ({hr_keywords}) AND ("Казахстан" OR "Kazakhstan" OR site:kz)'
    
    # Тип В: Поиск по социальным сетям (НОВЫЙ ВЕКТОР!)
    # Мы явно просим Google поискать на конкретных сайтах
    social_media_sites = "site:instagram.com OR site:facebook.com OR site:linkedin.com"
    query_social_media = f'"{clean_company_name}" AND ({social_media_sites}) AND ("Казахстан" OR "Kazakhstan")'

    search_queries = [query_direct_charity, query_hr_brand, query_social_media]
    
    # --- Вектор 3: Выполнение и фильтрация ---
    all_search_results: List[GoogleSearchResult] = []
    unique_links = set()

    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, query in enumerate(search_queries):
            print(f"🔍 [ADVANCED_RESEARCH] Sending Query {i+1}/{len(search_queries)}: '{query[:90]}...'")
            
            search_url = (
                f"https://www.googleapis.com/customsearch/v1?"
                f"key={GOOGLE_API_KEY}&"
                f"cx={GOOGLE_SEARCH_ENGINE_ID}&"
                f"q={query}&"
                f"num=5&"  # Меньше результатов на запрос, но больше запросов
                f"lr=lang_ru&"  # Предпочтение русскому языку
                f"gl=kz&"  # Географическое ограничение - Казахстан
                f"cr=countryKZ&"  # Дополнительное ограничение по стране - Казахстан
                f"hl=ru"  # Язык интерфейса - русский
            )

            try:
                response = await client.get(search_url)
                if response.status_code == 429:
                    print("❌ Rate limit hit! Aborting.")
                    break
                response.raise_for_status()
                search_data = response.json()

                if 'items' in search_data:
                    for item in search_data['items']:
                        link = item.get('link')
                        if link and link not in unique_links:
                            # Для HR и соцсетей мы не применяем строгую фильтрацию по словам
                            # Нам важна сама ссылка, чтобы аналитик мог ее посмотреть
                            unique_links.add(link)
                            all_search_results.append(GoogleSearchResult(
                                title=item.get('title', 'Нет заголовка'),
                                link=link,
                                snippet=item.get('snippet', 'Нет описания')
                            ))
                            print(f"✅ [ADVANCED_RESEARCH] Добавлен результат: {item.get('title', '')[:50]}...")
                
                # Небольшая задержка между запросами
                if i < len(search_queries) - 1:
                    await asyncio.sleep(1.0)
                    
            except Exception as e:
                print(f"⚠️ Error on query '{query[:50]}...': {e}")

    # --- Вектор 4: Анализ и генерация сводки ---
    if not all_search_results:
        summary = (
            f"Поиск в интернете по Казахстану (включая социальные сети) не дал результатов, которые могли бы указать "
            f"на благотворительную или активную социальную жизнь компании '{company_name}'.\n\n"
            f"Рекомендация: Компания, вероятно, не ведет публичную социальную деятельность в Казахстане или ее сложно найти. Требуется прямой контакт."
        )
    else:
        # Теперь мы отправляем в Gemini не только текст, но и просим его проанализировать сами ссылки
        # Это дает гораздо более качественный результат
        
        # Собираем информацию для промпта
        search_results_text = ""
        for result in all_search_results:
            search_results_text += f"- Заголовок: {result.title}\n  Ссылка: {result.link}\n  Фрагмент: {result.snippet}\n\n"
        
        # --- УЛУЧШЕННЫЙ ПРОМПТ ДЛЯ AI-АНАЛИТИКА ---
        summary_prompt = f"""
        Ты — опытный аналитик, исследующий корпоративную социальную ответственность (КСО) в Казахстане.
        Твоя задача — проанализировать результаты поиска по компании "{company_name}" и сделать вывод о ее потенциальной заинтересованности в благотворительности.

        Вот данные поиска по казахстанским источникам:
        {search_results_text}

        Проанализируй эти данные по шагам:
        1.  **Прямые доказательства:** Есть ли прямые упоминания слов "благотворительность", "спонсорство", "помощь фонду", "пожертвования"? Если да, выдели это как главный факт.
        2.  **Косвенные доказательства:** Посмотри на ссылки из Instagram, Facebook, LinkedIn или страниц "Карьера". Если компания активно показывает свою корпоративную жизнь (мероприятия, тимбилдинги, праздники), это сильный косвенный признак. Такая компания, скорее всего, открыта к социальным проектам. Отметь это.
        3.  **Казахстанский контекст:** Убедись, что найденная информация действительно касается деятельности в Казахстане, а не других стран.
        4.  **Отсутствие информации:** Если найдены только официальные страницы или реестры без какой-либо "живой" информации, это плохой знак. Укажи на это.

        Сформируй итоговую сводку на русском языке для благотворительного фонда в Казахстане. Твой ответ должен быть структурирован и давать четкую рекомендацию для фандрайзера о перспективности обращения к этой компании за спонсорской поддержкой.
        """
        
        # Вызываем Gemini для генерации сводки
        payload = {"contents": [{"parts": [{"text": summary_prompt}]}]}
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}", 
                    json=payload
                )
                response.raise_for_status()
                g_data = response.json()
                summary = g_data["candidates"][0]["content"]["parts"][0]["text"]
                print(f"✅ [AI_ANALYST] Summary generated successfully.")
        except Exception as e:
            print(f"❌ [AI_ANALYST] Failed to generate summary: {e}")
            summary = "Не удалось сгенерировать аналитическую сводку по найденным материалам."

    print(f"✅ [ADVANCED_RESEARCH] Research complete for '{company_name}'. Found {len(all_search_results)} potential links.")
    return CompanyCharityResponse(
        status="success",
        company_name=company_name,
        charity_info=all_search_results,
        summary=summary
    ) 