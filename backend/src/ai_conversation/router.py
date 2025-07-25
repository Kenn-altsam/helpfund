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

    # 🚀 УЛУЧШЕННЫЕ ПОИСКОВЫЕ ЗАПРОСЫ: Максимально релевантные для Казахстана
    # Исключаем шумные результаты и фокусируемся на конкретных благотворительных действиях
    
    # Ключевые термины для благотворительности
    core_charity_terms = [
        "благотворительность", "пожертвования", "спонсорство", 
        "социальная ответственность", "КСО", "помощь детям", "помощь нуждающимся"
    ]
    
    specific_charity_actions = [
        "детский дом", "образовательные программы", "здравоохранение",
        "помощь малообеспеченным", "социальные проекты", "экологические инициативы",
        "поддержка ветеранов", "благотворительный фонд"
    ]
    
    # Исключающие слова для поиска, чтобы отфильтровать шумные "фонды" и "помощь"
    exclude_search_terms = [
        "пенсионный фонд", "фонд оплаты труда", "основные фонды", "государственные закупки",
        "тендер", "вакансия", "работа", "услуги", "прайс", "каталог", "оптовая торговля",
        "информация", "помощь по услугам", "судебные дела", "отчет о состоянии основных фондов"
    ]
    exclude_search_string = " -" + " -".join([f'"{term}"' for term in exclude_search_terms])
    
    if request.additional_context and request.additional_context.strip():
        context = request.additional_context.strip()
        print(f"🎯 [CHARITY_RESEARCH] Дополнительный контекст: '{context}'")
        
        # Запросы с дополнительным контекстом
        search_queries = [
            f'"{company_name}" Казахстан "{context}" ("{" OR ".join(core_charity_terms)}") {exclude_search_string}',
            f'"{company_name}" Казахстан ("{" OR ".join(specific_charity_actions)}") {exclude_search_string}'
        ]
        print(f"📝 [CHARITY_RESEARCH] Созданы 2 запроса с контекстом")
    else:
        # Два стратегических запроса вместо множества
        # Запрос 1: Основные благотворительные термины + исключение шума
        query_1 = f'"{company_name}" Казахстан ("{" OR ".join(core_charity_terms)}") {exclude_search_string}'
        
        # Запрос 2: Конкретные благотворительные действия + исключение шума
        query_2 = f'"{company_name}" Казахстан ("{" OR ".join(specific_charity_actions)}") {exclude_search_string}'
        
        search_queries = [query_1, query_2]
        print(f"📝 [CHARITY_RESEARCH] Созданы 2 стратегических запроса")

    all_search_results: List[GoogleSearchResult] = []
    
    # УЛУЧШЕННЫЕ КЛЮЧЕВЫЕ СЛОВА для определения релевантности благотворительности
    charity_keywords = [
        'благотворительность', 'благотворительный', 'пожертвование', 'спонсорство', 
        'помощь', 'поддержка', 'финансирует', 'спонсирует', 'программа', 'проект', 
        'инициатива', 'социальная ответственность', 'КСО', 'CSR', 'образование', 
        'здравоохранение', 'детский дом', 'стипендия', 'волонтер', 'донор', 'меценат',
        'гранты', 'акция добра', 'социальный проект', 'благотворительная акция',
        'charity', 'charitable', 'foundation', 'donates', 'sponsors', 'supports',
        'initiative', 'program', 'social responsibility',
        # Ключевые слова для платформ и доноров
        'перечислил в фонд', 'предоставил платформу', 'собрал средства для', 
        'донор фонда', 'организовал сбор средств', 'платформа для пожертвований'
    ]
    
    # Расширенные исключающие ключевые слова для фильтрации шума
    exclude_keywords = [
        'купить', 'скидка', 'цена', 'товар', 'услуга', 'продажа', 'реклама', 
        'заказать', 'доставка', 'магазин', 'каталог', 'вакансия', 'работа', 
        'резюме', 'сотрудник', 'государственные закупки', 'тендер', 'поставщик', 
        'договор', 'контрагент', 'отчетность', 'финансовый отчет', 'налоги', 
        'аудит', 'бухгалтерия', 'пенсионный фонд', 'фонд оплаты труда', 
        'основные фонды', 'помощь по платным услугам', 'техническая поддержка',
        'новости', 'advertisement', 'vacancy', 'job', 'news', 'sale', 'services'
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
                        full_text = f"{title} {snippet}"
                        
                        # 🎯 УЛУЧШЕННАЯ СТРОГАЯ ФИЛЬТРАЦИЯ: Контекстный анализ
                        company_name_variants = [
                            company_name.lower(),
                            company_name.lower().replace('"', ''),  # без кавычек
                            company_name.lower().replace('ао ', '').replace('тоо ', '').replace('оао ', ''),  # без правовых форм
                        ]
                        
                        # Проверяем наличие названия компании в результате
                        has_company_name = any(variant in full_text for variant in company_name_variants)
                        
                        # УЛУЧШЕННАЯ ПРОВЕРКА РЕЛЕВАНТНОСТИ: более строгие критерии
                        # Позитивные индикаторы благотворительности
                        positive_indicators = [
                            "благотворительность", "пожертвование", "спонсорство", "помощь", 
                            "поддержка", "социальная ответственность", "КСО", "CSR",
                            "детский дом", "больница", "образование", "стипендия",
                            "волонтер", "донор", "меценат", "гранты",
                            "акция добра", "социальный проект", "благотворительная акция"
                        ]
                        
                        # Строгие позитивные фразы, наличие которых СИЛЬНО повышает релевантность
                        strong_positive_phrases = [
                            "благотворительный фонд", "проект помощи", "выделил средства", 
                            "профинансировал", "оказал помощь", "пожертвовал", "социальная программа"
                        ]
                        
                        # Подсчитываем релевантность
                        positive_score = sum(1 for indicator in positive_indicators if indicator in full_text)
                        negative_score = sum(1 for indicator in exclude_keywords if indicator in full_text)
                        
                        # Проверка на наличие строгих позитивных фраз
                        has_strong_positive_phrase = any(phrase in full_text for phrase in strong_positive_phrases)
                        
                        # Дополнительная проверка: если есть "фонд", но нет "благотворительный", то это подозрительно
                        if "фонд" in full_text and "благотворительный" not in full_text:
                            if any(term in full_text for term in ["пенсионный", "основные", "оплаты труда", "государственный"]):
                                negative_score += 5  # Сильно снижаем релевантность
                        
                        # Результат релевантен, если:
                        # 1. Есть сильная позитивная фраза (наилучший случай)
                        # ИЛИ (если нет сильной фразы, но есть другие позитивные индикаторы):
                        # 2. Есть позитивные индикаторы И количество негативных индикаторов значительно меньше позитивных
                        is_charity_relevant = has_strong_positive_phrase or (positive_score > 0 and negative_score < positive_score * 2)
                        
                        # 🔍 СТРОГИЕ КРИТЕРИИ: результат принимается только если:
                        # 1. Есть название компании 2. Есть релевантность благотворительности 3. Нет критических исключающих слов
                        if has_company_name and is_charity_relevant:
                            all_search_results.append(GoogleSearchResult(
                                title=item.get('title', 'Нет заголовка'),
                                link=link,
                                snippet=item.get('snippet', 'Нет описания')
                            ))
                            found_relevant += 1
                            print(f"✅ [CHARITY_RESEARCH] Строгий фильтр ПРОЙДЕН: {item.get('title', '')[:50]}... (Positive: {positive_score}, Negative: {negative_score}, Strong: {has_strong_positive_phrase})")
                        else:
                            # Детальное логирование причин отклонения
                            reasons = []
                            if not has_company_name:
                                reasons.append("нет названия компании")
                            if not is_charity_relevant:
                                reasons.append(f"недостаточно релевантности (Positive: {positive_score}, Negative: {negative_score}, Strong: {has_strong_positive_phrase})")
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
        
        # УЛУЧШЕННЫЕ ключевые слова для определения ПРЯМЫХ действий благотворительности
        direct_action_keywords = [
            'выделил', 'профинансировал', 'пожертвовал', 'передал', 'спонсировал',
            'donated', 'funded', 'sponsored', 'allocated', 'contributed',
            # Ключевые слова для платформ и доноров
            'перечислил в фонд', 'предоставил платформу', 'собрал средства для', 
            'донор фонда', 'организовал сбор средств', 'платформа для пожертвований',
            # Дополнительные конкретные действия
            'оказал помощь', 'выделил средства', 'поддержал проект', 'реализовал программу',
            'организовал акцию', 'провел мероприятие', 'создал фонд', 'учредил программу'
        ]
        
        for result in all_search_results:
            text = (result.title + " " + result.snippet).lower()
            
            # Проверяем наличие прямых действий
            has_direct_action = any(action in text for action in direct_action_keywords)
            is_platform = any(kw in text for kw in ['предоставил платформу', 'платформа для пожертвований'])
            is_major_donor = any(kw in text for kw in ['перечислил в фонд', 'донор фонда', 'собрал средства для', 'организовал сбор средств'])
            if has_direct_action or is_platform or is_major_donor:
                direct_evidence_count += 1
                
                # Ищем суммы или конкретные проекты
                if any(word in text for word in ['млн', 'млрд', 'тенге', 'миллион', 'billion', 'million']):
                    specific_activities.append('финансовые пожертвования')
                if any(word in text for word in ['фонд', 'foundation']):
                    specific_activities.append('благотворительные фонды')
                if is_platform:
                    specific_activities.append('платформа для сбора пожертвований')
                if is_major_donor:
                    specific_activities.append('крупный донор/организатор сбора средств')
            
            # УЛУЧШЕННЫЙ анализ областей деятельности (только при наличии прямых действий)
            if has_direct_action:
                # Более точные ключевые слова для каждой области
                education_keywords = ['образование', 'education', 'школа', 'университет', 'обучение', 'студент', 'стипендия', 'образовательная программа']
                health_keywords = ['здравоохранение', 'health', 'медицина', 'больница', 'лечение', 'медицинская помощь', 'здоровье']
                sport_keywords = ['спорт', 'sport', 'команда', 'соревнование', 'турнир', 'спортивная программа', 'физическая культура']
                culture_keywords = ['культура', 'culture', 'искусство', 'театр', 'музей', 'культурная программа', 'творчество']
                ecology_keywords = ['экология', 'environment', 'природа', 'окружающая среда', 'экологическая программа', 'зеленые технологии']
                children_keywords = ['дети', 'children', 'детский', 'молодежь', 'подросток', 'детский дом', 'поддержка детей']
                
                if any(word in text for word in education_keywords):
                    charity_areas.add('образование')
                if any(word in text for word in health_keywords):
                    charity_areas.add('здравоохранение')
                if any(word in text for word in sport_keywords):
                    charity_areas.add('спорт')
                if any(word in text for word in culture_keywords):
                    charity_areas.add('культура')
                if any(word in text for word in ecology_keywords):
                    charity_areas.add('экология')
                if any(word in text for word in children_keywords):
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

    # Финальное логирование результатов (УЛУЧШЕННАЯ ВЕРСИЯ)
    total_queries = len(search_queries)
    total_results = len(all_search_results)
    
    if not all_search_results:
        print(f"🔍 [CHARITY_RESEARCH] Завершено исследование компании '{company_name}': 0 релевантных результатов из {total_queries} улучшенных запросов")
        print(f"📊 [CHARITY_RESEARCH] Экономия API квот: использовано {total_queries} запросов вместо 8-12 (экономия ~{8-total_queries} запросов)")
        print(f"🎯 [CHARITY_RESEARCH] Применена строгая фильтрация для исключения шумных результатов")
        return CompanyCharityResponse(
            status="success",
            company_name=company_name,
            charity_info=[],
            summary=final_summary_for_response
        )

    print(f"✅ [CHARITY_RESEARCH] Исследование завершено для '{company_name}': найдено {total_results} релевантных результатов из {total_queries} улучшенных запросов")
    print(f"📊 [CHARITY_RESEARCH] Экономия API квот: использовано {total_queries} запросов вместо 8-12 (экономия ~{8-total_queries} запросов)")
    print(f"🎯 [CHARITY_RESEARCH] Применена строгая фильтрация для исключения шумных результатов")
    
    # Логируем найденные области благотворительности (улучшенная версия)
    areas = set()
    for result in all_search_results:
        text = (result.title + " " + result.snippet).lower()
        # Используем те же ключевые слова, что и в анализе
        education_keywords = ['образование', 'education', 'школа', 'университет', 'обучение', 'студент', 'стипендия']
        health_keywords = ['здравоохранение', 'health', 'медицина', 'больница', 'лечение', 'медицинская помощь']
        sport_keywords = ['спорт', 'sport', 'команда', 'соревнование', 'турнир', 'спортивная программа']
        culture_keywords = ['культура', 'culture', 'искусство', 'театр', 'музей', 'культурная программа']
        ecology_keywords = ['экология', 'environment', 'природа', 'окружающая среда', 'экологическая программа']
        children_keywords = ['дети', 'children', 'детский', 'молодежь', 'подросток', 'детский дом']
        
        if any(word in text for word in education_keywords): areas.add('образование')
        if any(word in text for word in health_keywords): areas.add('здравоохранение')
        if any(word in text for word in sport_keywords): areas.add('спорт')
        if any(word in text for word in culture_keywords): areas.add('культура')
        if any(word in text for word in ecology_keywords): areas.add('экология')
        if any(word in text for word in children_keywords): areas.add('поддержка детей')
    
    if areas:
        print(f"📋 [CHARITY_RESEARCH] Выявленные области деятельности: {', '.join(areas)}")
    else:
        print(f"📋 [CHARITY_RESEARCH] Конкретные области деятельности не выявлены")

    return CompanyCharityResponse(
        status="success",
        company_name=company_name,
        charity_info=all_search_results,
        summary=final_summary_for_response
    ) 