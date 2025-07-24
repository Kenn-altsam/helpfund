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
        
        # Один комплексный запрос с контекстом (русский + английский)
        search_queries = [
            f'"{company_name}" ("{context}" OR "благотворительность" OR "благотворительный фонд" OR "социальная ответственность" OR "КСО" OR "помощь" OR "финансирует" OR "поддерживает" OR "спонсирует" OR "программа" OR "проект" OR "инициатива" OR "charitable foundation" OR "charity program" OR "CSR" OR "corporate social responsibility" OR "donates" OR "sponsors" OR "supports")'
        ]
        print(f"📝 [CHARITY_RESEARCH] Создан 1 оптимизированный запрос с контекстом")
    else:
        # Два оптимизированных запроса: русский + английский
        search_queries = [
            # Запрос 1: Русские термины благотворительности
            f'"{company_name}" ("благотворительный фонд" OR "социальная ответственность" OR "КСО" OR "помощь" OR "финансирует" OR "поддерживает" OR "спонсирует" OR "программа" OR "проект" OR "инициатива")',
            
            # Запрос 2: Английские термины благотворительности  
            f'"{company_name}" ("charitable foundation" OR "charity program" OR "CSR" OR "corporate social responsibility" OR "donates" OR "sponsors" OR "supports" OR "initiative")'
        ]
        print(f"📝 [CHARITY_RESEARCH] Созданы 2 оптимизированных запроса (русский + английский)")

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
    async with httpx.AsyncClient(timeout=10.0) as client:
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
                        
                        # Проверяем релевантность результата
                        is_charity_relevant = any(keyword in title or keyword in snippet for keyword in charity_keywords)
                        has_exclude_keywords = any(exclude in title or exclude in snippet for exclude in exclude_keywords)
                        
                        # Добавляем только релевантные результаты без исключающих слов
                        if is_charity_relevant and not has_exclude_keywords:
                            all_search_results.append(GoogleSearchResult(
                                title=item.get('title', 'Нет заголовка'),
                                link=link,
                                snippet=item.get('snippet', 'Нет описания')
                            ))
                            found_relevant += 1
                            print(f"✅ [CHARITY_RESEARCH] Релевантный результат: {item.get('title', '')[:50]}...")
                        else:
                            print(f"🚫 [CHARITY_RESEARCH] Отфильтрован: {item.get('title', '')[:50]}...")
                
                print(f"📊 [CHARITY_RESEARCH] Запрос {i+1}: найдено {total_found}, релевантных {found_relevant}")
                
                # Задержка между запросами (теперь максимум 2 запроса)
                if i < len(search_queries) - 1:  # Не ждем после последнего запроса
                    await asyncio.sleep(1.0)  # Немного увеличиваем задержку для стабильности
                
            except httpx.RequestError as e:
                print(f"❌ [CHARITY_RESEARCH] Ошибка HTTP для запроса '{query[:50]}...': {e}")
            except Exception as e:
                print(f"❌ [CHARITY_RESEARCH] Неизвестная ошибка для запроса '{query[:50]}...': {e}")
                traceback.print_exc()

    # Генерируем улучшенную сводку на основе найденных результатов
    if not all_search_results:
        final_summary_for_response = (
            f"По результатам целенаправленного поиска не найдено публичной информации о "
            f"благотворительной деятельности компании '{company_name}'. "
            f"Это может означать:\n"
            f"• Компания не ведет активную благотворительную деятельность\n"
            f"• Информация о социальных проектах не публикуется в открытых источниках\n"
            f"• Благотворительная деятельность ведется под другими названиями или через дочерние структуры\n\n"
            f"Рекомендация: обратитесь напрямую к представителям компании для уточнения возможностей спонсорской поддержки."
        )
    else:
        # Анализируем найденные результаты для создания сводки
        charity_areas = set()
        for result in all_search_results:
            text = (result.title + " " + result.snippet).lower()
            
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
        
        areas_text = ", ".join(charity_areas) if charity_areas else "различные социальные сферы"
        
        final_summary_for_response = (
            f"Найдена информация о благотворительной и социальной деятельности компании '{company_name}'. "
            f"Обнаружено {len(all_search_results)} релевантных источников, указывающих на активность в области: {areas_text}.\n\n"
            f"Компания проявляет заинтересованность в корпоративной социальной ответственности. "
            f"Для получения актуальной информации о возможностях спонсорской поддержки рекомендуется "
            f"изучить официальные источники компании и обратиться в отдел по связям с общественностью."
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