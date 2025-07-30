from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import traceback
import uuid
import os
import httpx
import json
import re
import asyncio
import time
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

from .models import ChatRequest, ChatResponse, CompanyCharityRequest, CompanyCharityResponse, GoogleSearchResult
# !!! ИМПОРТИРУЕМ НАШ ГЛАВНЫЙ СЕРВИС !!!
from .service import ai_service
from ..core.database import get_db
from ..auth.models import User
from ..auth.dependencies import get_current_user
from ..chats import service as chat_service  # Сервис для сохранения истории чатов
from ..chats.models import Chat  # Модель чата для проверки принадлежности
from ..core.config import get_settings

router = APIRouter(prefix="/ai", tags=["AI Conversation"])

# Rate limiting for individual users
user_rate_limits = defaultdict(lambda: {"requests": [], "last_reset": datetime.now()})

def check_user_rate_limit(user_id: str, max_requests: int = 20, window_seconds: int = 60) -> bool:
    """
    Check if user has exceeded rate limit
    """
    now = datetime.now()
    user_data = user_rate_limits[user_id]
    
    # Reset if window has passed
    if (now - user_data["last_reset"]).total_seconds() > window_seconds:
        user_data["requests"] = []
        user_data["last_reset"] = now
    
    # Check if limit exceeded
    if len(user_data["requests"]) >= max_requests:
        return False
    
    # Add current request
    user_data["requests"].append(now)
    return True

def get_user_wait_time(user_id: str, window_seconds: int = 60) -> float:
    """
    Get wait time for user rate limit
    """
    user_data = user_rate_limits[user_id]
    if not user_data["requests"]:
        return 0
    
    oldest_request = min(user_data["requests"])
    return max(0, window_seconds - (datetime.now() - oldest_request).total_seconds())

# ============================================================================== 
# === ИНИЦИАЛИЗАЦИЯ API КЛЮЧЕЙ ДЛЯ GOOGLE SEARCH ===
# ==============================================================================
# Загружаем .env файл из корня проекта (на два уровня вверх от текущего файла)
import pathlib
env_path = pathlib.Path(__file__).parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get settings for API keys
settings = get_settings()
GOOGLE_API_KEY = settings.GOOGLE_API_KEY
GOOGLE_SEARCH_ENGINE_ID = settings.GOOGLE_SEARCH_ENGINE_ID
GEMINI_API_KEY = settings.GEMINI_API_KEY

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY не установлен в переменных окружения. Проверьте ваш .env файл.")
if not GOOGLE_SEARCH_ENGINE_ID:
    raise RuntimeError("GOOGLE_SEARCH_ENGINE_ID не установлен в переменных окружения. Проверьте ваш .env файл.")
if not GEMINI_API_KEY:
    print("⚠️  Warning: GEMINI_API_KEY is not set. The API key rotator will not work properly.")


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

    # Check user rate limit
    if not check_user_rate_limit(str(current_user.id), max_requests=20, window_seconds=60):
        wait_time = get_user_wait_time(str(current_user.id), window_seconds=60)
        print(f"⚠️ [USER_RATE_LIMIT] User {current_user.id} exceeded rate limit. Wait {wait_time:.1f} seconds")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please wait {wait_time:.1f} seconds before trying again."
        )

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

    except HTTPException:
        # Re-raise HTTP exceptions (like rate limits)
        raise
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
    current_user: User = Depends(get_current_user)  # Защищаем эндпоинт аутентификацией
):
    """
    Выполняет поиск в Google по благотворительной деятельности указанной компании
    и возвращает найденные ссылки и сниппеты.
    """
    company_name = request.company_name

    print(f"\U0001F50D [CHARITY_RESEARCH] Starting research for company: '{company_name}' by user {current_user.id}")

    if not company_name.strip():
        raise HTTPException(status_code=400, detail="Название компании не может быть пустым.")

    # 🚀 ОПТИМИЗИРОВАННЫЕ ЗАПРОСЫ: ВСЕГО 1-2 ЗАПРОСА ВМЕСТО 8+
    # Объединяем все ключевые термины в комплексные запросы с логическими операторами
    
    if request.additional_context and request.additional_context.strip():
        context = request.additional_context.strip()
        print(f"🎯 [CHARITY_RESEARCH] Дополнительный контекст: '{context}'")
        
        # Строгий запрос с контекстом - используем AROUND для близости слов
        search_queries = [
            f'"{company_name}" AROUND(15) ("{context}" OR "благотворительность" OR "благотворительный фонд" OR "социальная ответственность" OR "КСО" OR "charitable foundation" OR "charity" OR "CSR")'
        ]
        print(f"📝 [CHARITY_RESEARCH] Создан 1 строгий запрос с контекстом (AROUND)")
    else:
        # Два строгих запроса с операторами близости AROUND
        search_queries = [
            # Запрос 1: Строгий поиск русских терминов (название компании в пределах 15 слов от ключевых терминов)
            f'"{company_name}" AROUND(15) ("благотворительный фонд" OR "социальная ответственность" OR "КСО" OR "благотворительность" OR "спонсирует" OR "финансирует" OR "поддерживает")',
            
            # Запрос 2: Строгий поиск английских терминов
            f'"{company_name}" AROUND(15) ("charitable foundation" OR "charity program" OR "CSR" OR "corporate social responsibility" OR "donates" OR "sponsors" OR "charity")'
        ]
        print(f"📝 [CHARITY_RESEARCH] Созданы 2 строгих запроса с AROUND (русский + английский)")

    all_search_results: List[GoogleSearchResult] = []
    
    # Ключевые слова для определения релевантности благотворительности
    charity_keywords = [
        'благотворительность', 'благотворительный', 'фонд', 'помощь', 'поддержка',
        'финансирует', 'спонсирует', 'программа', 'проект', 'инициатива',
        'социальная ответственность', 'КСО', 'CSR', 'образование', 'здравоохранение',
        'charity', 'charitable', 'foundation', 'donates', 'sponsors', 'supports',
        'initiative', 'program', 'social responsibility'
    ]
    
    # Исключающие ключевые слова (чтобы отфильтровать нерелевантные результаты)
    exclude_keywords = [
        'вакансия', 'работа', 'новости', 'реклама', 'продажа', 'услуги',
        'vacancy', 'job', 'news', 'advertisement', 'sale', 'services',
        'купить', 'цена', 'стоимость', 'прайс'
    ]
    
    # Использование httpx.AsyncClient для асинхронных запросов
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for i, query in enumerate(search_queries):
            print(f"🔍 [CHARITY_RESEARCH] Выполняю запрос {i+1}/{len(search_queries)}: '{query[:80]}...'")
            
            search_url = (
                f"https://www.googleapis.com/customsearch/v1?"
                f"key={GOOGLE_API_KEY}&"
                f"cx={GOOGLE_SEARCH_ENGINE_ID}&"
                f"q={query}&"
                f"num=10&"  # Увеличиваем результаты на запрос (компенсируем меньшее кол-во запросов)
                f"lr=lang_ru&"  # Предпочтение русскому языку
                f"gl=kz"  # Географическое ограничение - Казахстан
            )

            try:
                response = await client.get(search_url)
                response.raise_for_status()
                search_data = response.json()
                
                found_relevant = 0
                total_found = len(search_data.get('items', []))

                if 'items' in search_data:
                    for item in search_data['items']:
                        title = item.get('title', '').lower()
                        snippet = item.get('snippet', '').lower()
                        link = item.get('link', '')
                        full_text = f"{title} {snippet}"
                        
                        # 🎯 СТРОГАЯ ФИЛЬТРАЦИЯ: Проверяем что есть и название компании, и ключевые слова
                        company_name_variants = [
                            company_name.lower(),
                            company_name.lower().replace('"', ''),  # без кавычек
                            company_name.lower().replace('ао ', '').replace('тоо ', '').replace('оао ', ''),  # без правовых форм
                        ]
                        
                        # Проверяем наличие названия компании в результате
                        has_company_name = any(variant in full_text for variant in company_name_variants)
                        
                        # Проверяем релевантность результата (наличие благотворительных ключевых слов)
                        is_charity_relevant = any(keyword in full_text for keyword in charity_keywords)
                        
                        # Проверяем отсутствие исключающих слов (шум)
                        has_exclude_keywords = any(exclude in full_text for exclude in exclude_keywords)
                        
                        # 🔍 СТРОГИЕ КРИТЕРИИ: результат принимается только если:
                        # 1. Есть название компании 2. Есть ключевые слова благотворительности 3. Нет исключающих слов
                        if has_company_name and is_charity_relevant and not has_exclude_keywords:
                            all_search_results.append(GoogleSearchResult(
                                title=item.get('title', 'Нет заголовка'),
                                link=link,
                                snippet=item.get('snippet', 'Нет описания')
                            ))
                            found_relevant += 1
                            print(f"✅ [CHARITY_RESEARCH] Строгий фильтр ПРОЙДЕН: {item.get('title', '')[:50]}...")
                        else:
                            # Детальное логирование причин отклонения
                            reasons = []
                            if not has_company_name:
                                reasons.append("нет названия компании")
                            if not is_charity_relevant:
                                reasons.append("нет ключевых слов")
                            if has_exclude_keywords:
                                reasons.append("есть исключающие слова")
                            print(f"🚫 [CHARITY_RESEARCH] Строгий фильтр НЕ ПРОЙДЕН ({', '.join(reasons)}): {item.get('title', '')[:50]}...")
                
                print(f"📊 [CHARITY_RESEARCH] Запрос {i+1}: найдено {total_found}, релевантных {found_relevant}")
                
                # Задержка между запросами (теперь максимум 2 запроса)
                if i < len(search_queries) - 1:  # Не ждем после последнего запроса
                    await asyncio.sleep(1.0)  # Немного увеличиваем задержку для стабильности
                
            except httpx.RequestError as e:
                print(f"❌ [CHARITY_RESEARCH] Ошибка HTTP для запроса '{query[:50]}...': {e}")
            except Exception as e:
                print(f"❌ [CHARITY_RESEARCH] Неизвестная ошибка для запроса '{query[:50]}...': {e}")
                traceback.print_exc()

    # 🎯 СТРОГАЯ ГЕНЕРАЦИЯ СВОДКИ: анализируем только прямые доказательства
    if not all_search_results:
        final_summary_for_response = (
            f"Прямых доказательств благотворительной деятельности компании '{company_name}' "
            f"в открытых источниках НЕ НАЙДЕНО.\n\n"
            f"Возможные причины:\n"
            f"• Компания не ведет публичную благотворительную деятельность\n"
            f"• Социальные проекты не освещаются в интернете\n"
            f"• Благотворительность ведется через дочерние структуры\n\n"
            f"Рекомендация: обратитесь напрямую к представителям компании для уточнения возможностей спонсорской поддержки."
        )
    else:
        # 🔍 СТРОГИЙ АНАЛИЗ: ищем конкретные доказательства благотворительности
        direct_evidence_count = 0
        charity_areas = set()
        specific_activities = []
        
        # Ключевые слова для определения ПРЯМЫХ действий благотворительности
        direct_action_keywords = [
            'выделил', 'профинансировал', 'пожертвовал', 'передал', 'спонсировал',
            'donated', 'funded', 'sponsored', 'allocated', 'contributed'
        ]
        
        for result in all_search_results:
            text = (result.title + " " + result.snippet).lower()
            
            # Проверяем наличие прямых действий
            has_direct_action = any(action in text for action in direct_action_keywords)
            if has_direct_action:
                direct_evidence_count += 1
                
                # Ищем суммы или конкретные проекты
                if any(word in text for word in ['млн', 'млрд', 'тенге', 'миллион', 'billion', 'million']):
                    specific_activities.append('финансовые пожертвования')
                if any(word in text for word in ['фонд', 'foundation']):
                    specific_activities.append('благотворительные фонды')
            
            # Анализ областей деятельности (только при наличии прямых действий)
            if has_direct_action:
                if any(word in text for word in ['образование', 'education', 'школа', 'университет', 'обучение']):
                    charity_areas.add('образование')
                if any(word in text for word in ['здравоохранение', 'health', 'медицина', 'больница', 'лечение']):
                    charity_areas.add('здравоохранение')
                if any(word in text for word in ['спорт', 'sport', 'команда', 'соревнование', 'турнир']):
                    charity_areas.add('спорт')
                if any(word in text for word in ['культура', 'culture', 'искусство', 'театр', 'музей']):
                    charity_areas.add('культура')
                if any(word in text for word in ['экология', 'environment', 'природа', 'окружающая среда']):
                    charity_areas.add('экология')
                if any(word in text for word in ['дети', 'children', 'детский', 'молодежь']):
                    charity_areas.add('поддержка детей и молодежи')
        
        # 🎯 СТРОГИЕ КРИТЕРИИ для сводки
        if direct_evidence_count > 0:
            areas_text = ", ".join(charity_areas) if charity_areas else "социальная деятельность"
            activities_text = ", ".join(set(specific_activities)) if specific_activities else "благотворительные инициативы"
            
            final_summary_for_response = (
                f"НАЙДЕНЫ ПРЯМЫЕ ДОКАЗАТЕЛЬСТВА благотворительной деятельности компании '{company_name}'.\n\n"
                f"Обнаружено {direct_evidence_count} источников с конкретными фактами благотворительности "
                f"(из {len(all_search_results)} проверенных материалов).\n\n"
                f"Подтвержденная активность: {activities_text}\n"
                f"Области деятельности: {areas_text}\n\n"
                f"Компания ДЕЙСТВИТЕЛЬНО занимается благотворительностью. "
                f"Рекомендуется изучить приложенные источники и обратиться в отдел КСО компании."
            )
        else:
            final_summary_for_response = (
                f"Найдено {len(all_search_results)} упоминаний компании '{company_name}' в контексте благотворительности, "
                f"НО НЕТ ПРЯМЫХ ДОКАЗАТЕЛЬСТВ конкретных благотворительных действий.\n\n"
                f"Обнаруженная информация носит общий характер (упоминания в списках, новости без подробностей, "
                f"декларации о социальной ответственности без конкретных проектов).\n\n"
                f"Рекомендация: требуется дополнительная проверка через официальные каналы компании."
            )

    # Финальное логирование результатов (ОПТИМИЗИРОВАННАЯ ВЕРСИЯ)
    total_queries = len(search_queries)
    total_results = len(all_search_results)
    
    if not all_search_results:
        print(f"🔍 [CHARITY_RESEARCH] Завершено исследование компании '{company_name}': 0 релевантных результатов из {total_queries} оптимизированных запросов")
        print(f"📊 [CHARITY_RESEARCH] Экономия API квот: использовано {total_queries} запросов вместо 8-12")
        return CompanyCharityResponse(
            status="success",
            company_name=company_name,
            charity_info=[],
            summary=final_summary_for_response
        )

    print(f"✅ [CHARITY_RESEARCH] Исследование завершено для '{company_name}': найдено {total_results} релевантных результатов из {total_queries} оптимизированных запросов")
    print(f"📊 [CHARITY_RESEARCH] Экономия API квот: использовано {total_queries} запросов вместо 8-12 (экономия ~{8-total_queries} запросов)")
    
    # Логируем найденные области благотворительности
    areas = set()
    for result in all_search_results:
        text = (result.title + " " + result.snippet).lower()
        if any(word in text for word in ['образование', 'education']): areas.add('образование')
        if any(word in text for word in ['здравоохранение', 'health']): areas.add('здравоохранение')
        if any(word in text for word in ['спорт', 'sport']): areas.add('спорт')
        if any(word in text for word in ['культура', 'culture']): areas.add('культура')
        if any(word in text for word in ['экология', 'environment']): areas.add('экология')
    
    if areas:
        print(f"📋 [CHARITY_RESEARCH] Выявленные области деятельности: {', '.join(areas)}")

    return CompanyCharityResponse(
        status="success",
        company_name=company_name,
        charity_info=all_search_results,
        summary=final_summary_for_response
    ) 