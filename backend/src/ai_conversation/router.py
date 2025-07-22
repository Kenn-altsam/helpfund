from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import traceback
import uuid

from .models import ChatRequest, ChatResponse, CompanyCharityRequest, CompanyCharityResponse
# !!! ИМПОРТИРУЕМ НАШ ГЛАВНЫЙ СЕРВИС !!!
from .service import ai_service
from ..core.database import get_db
from ..auth.models import User
from ..auth.dependencies import get_current_user
from ..chats import service as chat_service  # Сервис для сохранения истории чатов

router = APIRouter(prefix="/ai", tags=["AI Conversation"])


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
        # Эта функция парсит намерение, ищет в БД и возвращает результат
        response_data = await ai_service.handle_conversation_turn(
            user_input=request.user_input,
            history=request.history,
            db=db,
            conversation_id=str(db_chat_id)
        )
        
        # 3. Сохраняем сообщения в базу данных, используя историю из ответа сервиса
        # Это важно, так как сервис добавляет в историю и запрос, и ответ
        last_user_message = next((msg for msg in reversed(response_data['updated_history']) if msg['role'] == 'user'), None)
        last_assistant_message = next((msg for msg in reversed(response_data['updated_history']) if msg['role'] == 'assistant'), None)

        if last_user_message:
            # Для сообщения пользователя метаданные не нужны
            chat_service.create_message(
                db=db,
                chat_id=db_chat_id,
                content=last_user_message['content'],
                role='user',
                metadata=None # Явно указываем, что их нет
            )

        if last_assistant_message:
            # Для сообщения ассистента извлекаем компании и передаем как metadata
            companies_data = response_data.get('companies', [])
            chat_service.create_message(
                db=db,
                chat_id=db_chat_id,
                content=last_assistant_message['content'],
                role='assistant',
                metadata={"companies": companies_data}
            )

        # 4. Формируем и возвращаем финальный ответ для фронтенда
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


# ============================================================================== 
# === ЭНДПОИНТ ДЛЯ АНАЛИЗА БЛАГОТВОРИТЕЛЬНОСТИ (ОСТАВЛЯЕМ КАК ЕСТЬ) ===
# ==============================================================================
@router.post("/charity-research", response_model=CompanyCharityResponse)
async def get_company_charity_info(
    request: CompanyCharityRequest,
    current_user: User = Depends(get_current_user)
):
    # ... ваш код для /charity-research остается без изменений ...
    # Я его убрал для краткости, но у вас он должен остаться
    import os
    import httpx
    # ... и так далее
    # Просто скопируйте сюда всю вашу функцию get_company_charity_info

    # Placeholder for the original code
    print(f"\U0001F50D [CHARITY_RESEARCH] Starting research for company: '{request.company_name}'")
    # ... (здесь весь ваш код из get_company_charity_info)
    # Этот эндпоинт работает правильно для своей задачи и использует Google/Gemini.
    # Он не связан с поиском по вашей БД.
    
    # Чтобы не вызывать ошибку, вернем заглушку. У ВАС ДОЛЖЕН БЫТЬ ВАШ ОРИГИНАЛЬНЫЙ КОД.
    return CompanyCharityResponse(
        status="success",
        answer="Эта функция осталась для анализа благотворительности."
    ) 