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

from .models import ChatRequest, ChatResponse, CompanyCharityRequest, CompanyCharityResponse
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
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    print("⚠️ [CHARITY_RESEARCH] Warning: GOOGLE_API_KEY not found in environment variables")
if not GOOGLE_SEARCH_ENGINE_ID:
    print("⚠️ [CHARITY_RESEARCH] Warning: GOOGLE_SEARCH_ENGINE_ID not found in environment variables")
if not GEMINI_API_KEY:
    print("⚠️ [CHARITY_RESEARCH] Warning: GEMINI_API_KEY not found in environment variables")


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
# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ GOOGLE SEARCH ===
# ==============================================================================
async def search_google(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Выполняет поиск в Google Custom Search API
    
    Args:
        query: Поисковый запрос
        num_results: Количество результатов (максимум 10)
    
    Returns:
        Список результатов поиска
    """
    if not GOOGLE_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        print("❌ [GOOGLE_SEARCH] Google API credentials not configured")
        return []
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_SEARCH_ENGINE_ID,
            "q": query,
            "num": min(num_results, 10),  # Google API максимум 10 результатов за запрос
            "lr": "lang_ru",  # Предпочтение русскому языку
            "gl": "kz"  # Географическое ограничение - Казахстан
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
            
            results = []
            for item in items:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "displayLink": item.get("displayLink", "")
                })
            
            print(f"✅ [GOOGLE_SEARCH] Found {len(results)} results for query: '{query}'")
            return results
            
    except httpx.HTTPError as e:
        print(f"❌ [GOOGLE_SEARCH] HTTP error: {e}")
        return []
    except Exception as e:
        print(f"❌ [GOOGLE_SEARCH] Unexpected error: {e}")
        return []


def extract_charity_info_from_results(results: List[Dict[str, Any]], company_name: str) -> Dict[str, Any]:
    """
    Извлекает информацию о благотворительности из результатов поиска
    
    Args:
        results: Результаты поиска Google
        company_name: Название компании
    
    Returns:
        Структурированная информация о благотворительности
    """
    # Ключевые слова для поиска благотворительной деятельности
    charity_keywords = [
        "благотворительность", "charity", "спонсорство", "sponsorship", 
        "социальная ответственность", "csr", "помощь", "поддержка",
        "фонд", "foundation", "образование", "education", "здравоохранение",
        "healthcare", "культура", "culture", "спорт", "sport", "экология"
    ]
    
    # Собираем релевантную информацию
    relevant_snippets = []
    sources = []
    charity_areas = set()
    
    for result in results:
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        link = result.get("link", "")
        
        # Проверяем релевантность результата
        is_relevant = False
        for keyword in charity_keywords:
            if keyword in title or keyword in snippet:
                is_relevant = True
                # Определяем область благотворительности
                if keyword in ["образование", "education"]:
                    charity_areas.add("Образование")
                elif keyword in ["здравоохранение", "healthcare"]:
                    charity_areas.add("Здравоохранение")
                elif keyword in ["культура", "culture"]:
                    charity_areas.add("Культура")
                elif keyword in ["спорт", "sport"]:
                    charity_areas.add("Спорт")
                elif keyword in ["экология"]:
                    charity_areas.add("Экология")
                else:
                    charity_areas.add("Социальная помощь")
                
                break
        
        if is_relevant:
            relevant_snippets.append(result.get("snippet", ""))
            sources.append(link)
    
    # Вычисляем оценку достоверности
    confidence_score = min(len(relevant_snippets) / 5.0, 1.0)  # Максимум 1.0 при 5+ релевантных результатах
    
    return {
        "relevant_snippets": relevant_snippets,
        "sources": sources[:5],  # Максимум 5 источников
        "charity_areas": list(charity_areas),
        "confidence_score": confidence_score,
        "total_results": len(results),
        "relevant_results": len(relevant_snippets)
    }


# ЗАКОММЕНТИРОВАННАЯ ИНТЕГРАЦИЯ С GEMINI (для будущего использования)
"""
async def analyze_with_gemini(company_name: str, search_results: Dict[str, Any], additional_context: str = None) -> str:
    \"\"\"
    Анализирует результаты поиска с помощью Gemini API
    
    Args:
        company_name: Название компании
        search_results: Результаты поиска и извлеченная информация
        additional_context: Дополнительный контекст от пользователя
    
    Returns:
        Анализ благотворительной деятельности компании
    \"\"\"
    if not GEMINI_API_KEY:
        return "Gemini API не настроен для анализа."
    
    try:
        # Формируем промпт для Gemini
        snippets_text = "\\n".join(search_results.get("relevant_snippets", []))
        charity_areas = ", ".join(search_results.get("charity_areas", []))
        
        prompt = f\"\"\"
        Проанализируй благотворительную деятельность компании "{company_name}" на основе найденной информации.
        
        Найденная информация:
        {snippets_text}
        
        Выявленные области благотворительности: {charity_areas}
        
        {"Дополнительный контекст: " + additional_context if additional_context else ""}
        
        Предоставь структурированный анализ:
        1. Основные направления благотворительности
        2. Конкретные проекты и инициативы
        3. Объем и масштаб деятельности
        4. Рекомендации для обращения за спонсорской поддержкой
        
        Ответ должен быть на русском языке, структурированным и информативным.
        \"\"\"
        
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(gemini_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            analysis = data["candidates"][0]["content"]["parts"][0]["text"]
            
            print(f"✅ [GEMINI_ANALYSIS] Successfully analyzed charity info for {company_name}")
            return analysis
            
    except Exception as e:
        print(f"❌ [GEMINI_ANALYSIS] Error analyzing with Gemini: {e}")
        return f"Ошибка при анализе через Gemini: {str(e)}"
"""


# ============================================================================== 
# === ЭНДПОИНТ ДЛЯ АНАЛИЗА БЛАГОТВОРИТЕЛЬНОСТИ ===
# ==============================================================================
@router.post("/charity-research", response_model=CompanyCharityResponse)
async def get_company_charity_info(
    request: CompanyCharityRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Исследует благотворительную деятельность компании с помощью Google Search
    и предоставляет структурированный анализ.
    """
    print(f"\U0001F50D [CHARITY_RESEARCH] Starting research for company: '{request.company_name}'")
    
    try:
        # 1. Формируем поисковые запросы
        base_queries = [
            f"{request.company_name} благотворительность",
            f"{request.company_name} социальная ответственность",
            f"{request.company_name} спонсорство"
        ]
        
        # Добавляем специфический запрос если есть дополнительный контекст
        if request.additional_context:
            base_queries.append(f"{request.company_name} {request.additional_context}")
        
        # 2. Выполняем поиск по всем запросам
        all_results = []
        search_queries_used = []
        
        for query in base_queries:
            print(f"🔍 [CHARITY_RESEARCH] Searching: '{query}'")
            search_queries_used.append(query)
            results = await search_google(query, num_results=3)
            all_results.extend(results)
            
            # Небольшая пауза между запросами
            await asyncio.sleep(0.5)
        
        # 3. Обрабатываем и анализируем результаты
        charity_info = extract_charity_info_from_results(all_results, request.company_name)
        
        # 4. Формируем базовый анализ
        if charity_info["relevant_results"] == 0:
            analysis = f"""
            По результатам поиска не найдено публичной информации о благотворительной деятельности компании "{request.company_name}".
            
            Это может означать:
            • Компания не ведет активную благотворительную деятельность
            • Информация о благотворительности не публикуется в открытых источниках
            • Деятельность ведется, но под другими названиями или через дочерние структуры
            
            Рекомендации:
            • Обратитесь напрямую к представителям компании
            • Уточните возможность спонсорской поддержки конкретных проектов
            • Рассмотрите возможность предложения взаимовыгодного партнерства
            """
            status = "warning"
        else:
            # Формируем анализ на основе найденной информации
            areas_text = ", ".join(charity_info["charity_areas"]) if charity_info["charity_areas"] else "различные области"
            
            analysis = f"""
            Компания "{request.company_name}" проявляет активность в сфере корпоративной социальной ответственности.
            
            🎯 Основные направления деятельности:
            {areas_text}
            
            📊 Найдено релевантной информации:
            • Источников с информацией о благотворительности: {charity_info["relevant_results"]}
            • Общий объем найденной информации: {charity_info["total_results"]} результатов
            
            💡 Рекомендации для обращения:
            • Изучите официальный сайт компании в разделе "Социальная ответственность"
            • Обратитесь в отдел по связям с общественностью или корпоративным коммуникациям
            • Подготовьте детальное предложение, показывающее взаимную выгоду сотрудничества
            • Укажите конкретные результаты и показатели эффективности проекта
            """
            status = "success"
        
        # 5. БУДУЩАЯ ИНТЕГРАЦИЯ С GEMINI (пока закомментировано)
        # Когда будет готово, раскомментируйте эти строки:
        # if GEMINI_API_KEY and charity_info["relevant_results"] > 0:
        #     try:
        #         analysis = await analyze_with_gemini(
        #             request.company_name, 
        #             charity_info, 
        #             request.additional_context
        #         )
        #     except Exception as e:
        #         print(f"⚠️ [CHARITY_RESEARCH] Gemini analysis failed, using fallback: {e}")
        
        # 6. Формируем финальный ответ
        response = CompanyCharityResponse(
            status=status,
            answer=analysis.strip(),
            search_query=" | ".join(search_queries_used),
            sources=charity_info["sources"],
            confidence_score=charity_info["confidence_score"],
            charity_areas=charity_info["charity_areas"] if charity_info["charity_areas"] else None,
            recommendations="""
            Для успешного обращения за спонсорской поддержкой:
            1. Изучите корпоративную стратегию и ценности компании
            2. Подготовьте профессиональную презентацию проекта
            3. Укажите конкретную пользу для бренда компании
            4. Предложите различные уровни партнерства
            5. Обеспечьте прозрачную отчетность о результатах
            """ if charity_info["relevant_results"] > 0 else None
        )
        
        print(f"✅ [CHARITY_RESEARCH] Research completed for '{request.company_name}'. Status: {status}")
        return response
        
    except Exception as e:
        print(f"❌ [CHARITY_RESEARCH] Critical error during research: {e}")
        traceback.print_exc()
        
        return CompanyCharityResponse(
            status="error",
            answer=f"Произошла ошибка при исследовании компании '{request.company_name}'. Пожалуйста, попробуйте позже или обратитесь к администратору.",
            search_query=request.company_name,
            sources=[],
            confidence_score=0.0,
            charity_areas=None,
            recommendations=None
        ) 