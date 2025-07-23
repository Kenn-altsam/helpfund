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

    search_queries = [
        f"{company_name} благотворительность",
        f"{company_name} социальная ответственность",
        f"{company_name} КСО",  # Корпоративная Социальная Ответственность
        f"{company_name} спонсорство",
        f"{company_name} charitable activities",  # Англоязычный запрос
        f"{company_name} CSR activities"  # Еще один англоязычный запрос
    ]

    all_search_results: List[GoogleSearchResult] = []
    
    # Использование httpx.AsyncClient для асинхронных запросов
    async with httpx.AsyncClient() as client:
        for query in search_queries:
            search_url = (
                f"https://www.googleapis.com/customsearch/v1?"
                f"key={GOOGLE_API_KEY}&"
                f"cx={GOOGLE_SEARCH_ENGINE_ID}&"
                f"q={query}"
            )

            try:
                response = await client.get(search_url)  # Используем await для асинхронного запроса
                response.raise_for_status()  # Вызывает исключение для HTTP ошибок (4xx или 5xx)
                search_data = response.json()

                if 'items' in search_data:
                    for item in search_data['items']:
                        all_search_results.append(GoogleSearchResult(
                            title=item.get('title', 'Нет заголовка'),
                            link=item.get('link', '#'),
                            snippet=item.get('snippet', 'Нет описания')
                        ))
                
            except httpx.RequestError as e:
                print(f"❌ [CHARITY_RESEARCH] Ошибка при запросе к Google Search API по запросу '{query}': {e}")
                # Продолжаем, чтобы попробовать другие запросы, не выбрасывая HTTPException сразу
            except Exception as e:
                print(f"❌ [CHARITY_RESEARCH] Неизвестная ошибка при обработке запроса '{query}': {e}")
                traceback.print_exc()

    summary_text = None
    # Опционально: Используйте Gemini для суммаризации, если он настроен
    # if all_search_results and GEMINI_API_KEY:
    #     try:
    #         if 'gemini_model' in globals(): # Проверяем, что gemini_model инициализирован
    #             prompt_parts = [
    #                 "Проанализируй следующие результаты поиска и кратко изложи информацию о благотворительности компании, указывая ключевые инициативы или направления деятельности, если они упоминаются. Сформулируй ответ на русском языке:\n\n"
    #             ]
    #             # Ограничиваем количество результатов для промпта, чтобы не превысить контекст
    #             for i, result in enumerate(all_search_results[:5]): # Можно ограничить, например, первыми 5-10 результатами
    #                 prompt_parts.append(f"Результат {i+1}:\n")
    #                 prompt_parts.append(f"Заголовок: {result.title}\n")
    #                 prompt_parts.append(f"Сниппет: {result.snippet}\n\n")
                
    #             # Временно оставим синхронный вызов для примера, но лучше использовать run_in_threadpool
    #             # или async-совместимый Gemini API
    #             # gemini_response = gemini_model.generate_content("".join(prompt_parts)) 
    #             # summary_text = gemini_response.text
    #             summary_text = "Пример сводки от Gemini, если бы он был активен." # Заглушка
    #         else:
    #             summary_text = "Функционал Gemini не инициализирован."
    #     except Exception as e:
    #         print(f"❌ [CHARITY_RESEARCH] Ошибка при генерации сводки с Gemini: {e}")
    #         traceback.print_exc()
    #         summary_text = "Не удалось сгенерировать сводку по благотворительности."
    # elif not all_search_results:
    #     summary_text = "Информация о благотворительности не найдена по предоставленным запросам."

    final_summary_for_response = summary_text if summary_text is not None else (
        "Информация о благотворительности не найдена." if not all_search_results else "Сводка не сгенерирована."
    )

    if not all_search_results:
        print(f"INFO: No charity information found for '{company_name}'.")
        return CompanyCharityResponse(
            status="success",
            company_name=company_name,
            charity_info=[],
            summary=final_summary_for_response
        )

    print(f"✅ [CHARITY_RESEARCH] Successfully completed research for company: '{company_name}'. Found {len(all_search_results)} results.")
    return CompanyCharityResponse(
        status="success",
        company_name=company_name,
        charity_info=all_search_results,
        summary=final_summary_for_response
    ) 