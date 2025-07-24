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

    # 🚀 УЛУЧШЕННЫЕ ЗАПРОСЫ: ВСЕГО 1-2 ЗАПРОСА ВМЕСТО 8+
    # 🔍 УЛУЧШЕННАЯ ОБРАБОТКА НАЗВАНИЙ КОМПАНИЙ
    def generate_company_name_variants(original_name: str) -> List[str]:
        """Генерирует различные варианты названия компании для более гибкого поиска"""
        variants = [original_name]  # Исходное название
        
        # Очищенное название без правовых форм
        clean_name = re.sub(r'^(ТОО|АО|ИП|A\.O\.|TOO|LLP|JSC|)\s*|"|«|»', '', original_name, flags=re.IGNORECASE).strip()
        if clean_name != original_name:
            variants.append(clean_name)
        
        # Варианты без пробелов (для названий типа "Apple City" -> "AppleCity")
        no_spaces = clean_name.replace(' ', '')
        if len(no_spaces) > 3:  # Только если достаточно длинное
            variants.append(no_spaces)
        
        # Сокращенные варианты (первые слова)
        words = clean_name.split()
        if len(words) > 1:
            # Первые два слова
            variants.append(' '.join(words[:2]))
            # Только первое слово (если оно достаточно специфичное)
            if len(words[0]) > 4:
                variants.append(words[0])
        
        # Убираем дубликаты и пустые
        return list(set([v for v in variants if v.strip()]))

    company_variants = generate_company_name_variants(company_name)
    print(f"   -> Варианты названий для поиска: {company_variants}")

    # 🎯 РАСШИРЕННЫЕ КЛЮЧЕВЫЕ СЛОВА (включая активности в соцсетях)
    charity_keywords_ru = [
        "благотворительность", "пожертвования", "спонсорство", "социальная ответственность", 
        "помощь фонду", "поддержал проект", "подарки детям", "помог детскому дому", 
        "социальная помощь", "КСО", "финансирует", "поддерживает",
        # Дополнительные для соцсетей и событий
        "мероприятие", "событие", "подарил", "вручил", "наградил", "поздравил",
        "помощь", "поддержка", "спонсировал", "профинансировал", "организовал"
    ]
    charity_keywords_en = [
        "charity", "donation", "sponsorship", "social responsibility", "CSR", 
        "charitable foundation", "charity program", "donates", "sponsors", "supports",
        # Дополнительные для соцсетей
        "event", "awarded", "presented", "congratulated", "organized", "funded"
    ]
    
    # 🎯 СОЗДАНИЕ ГИБКИХ ЗАПРОСОВ С ВАРИАНТАМИ НАЗВАНИЙ
    company_names_query = " OR ".join([f'"{variant}"' for variant in company_variants])
    
    if request.additional_context and request.additional_context.strip():
        context = request.additional_context.strip()
        print(f"🎯 [CHARITY_RESEARCH] Дополнительный контекст: '{context}'")
        
        # Улучшенный запрос с контекстом + все варианты названий + социальные сети
        ru_keywords = " OR ".join([f'"{kw}"' for kw in charity_keywords_ru[:8]])
        en_keywords = " OR ".join([f'"{kw}"' for kw in charity_keywords_en[:6]])
        search_queries = [
            f'({company_names_query}) AND ("{context}" OR {ru_keywords} OR {en_keywords}) AND ("Казахстан" OR "Kazakhstan" OR site:kz OR site:instagram.com OR site:facebook.com)'
        ]
        print(f"📝 [CHARITY_RESEARCH] Создан 1 расширенный запрос с контекстом (включая соцсети)")
    else:
        # Два оптимизированных запроса: основной веб-поиск + социальные сети
        ru_main_keywords = " OR ".join([f'"{kw}"' for kw in charity_keywords_ru[:7]])
        en_main_keywords = " OR ".join([f'"{kw}"' for kw in charity_keywords_en[:5]])
        
        search_queries = [
            # Запрос 1: Расширенный поиск по основным источникам + все варианты названий
            f'({company_names_query}) AND ({ru_main_keywords} OR {en_main_keywords}) AND ("Казахстан" OR "Kazakhstan" OR site:kz)',
            
            # Запрос 2: СПЕЦИАЛЬНЫЙ поиск в социальных сетях (более мягкие критерии)
            f'({company_names_query}) AND ("мероприятие" OR "событие" OR "подарил" OR "поздравил" OR "помощь" OR "поддержка" OR "event" OR "charity" OR "спонсор") AND (site:instagram.com OR site:facebook.com OR site:linkedin.com) AND ("Казахстан" OR "Kazakhstan" OR "Алматы" OR "Астана")'
        ]
        print(f"📝 [CHARITY_RESEARCH] Созданы 2 оптимизированных запроса: веб-источники + социальные сети")

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
                f"gl=kz&"  # Географическое ограничение - Казахстан
                f"cr=countryKZ&"  # Дополнительное ограничение по стране - Казахстан
                f"hl=ru"  # Язык интерфейса - русский
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
                        
                        # 🎯 УЛУЧШЕННАЯ ФИЛЬТРАЦИЯ: Используем все варианты названий
                        company_name_variants_lower = [variant.lower().replace('"', '') for variant in company_variants]
                        
                        # Проверяем наличие названия компании в результате
                        has_company_name = any(variant in full_text for variant in company_name_variants_lower)
                        
                        # Проверяем релевантность результата (наличие благотворительных ключевых слов)
                        all_charity_keywords = charity_keywords_ru + charity_keywords_en
                        is_charity_relevant = any(keyword.lower() in full_text for keyword in all_charity_keywords)
                        
                        # Проверяем отсутствие исключающих слов (шум)
                        has_exclude_keywords = any(exclude in full_text for exclude in exclude_keywords)
                        
                        # 🇰🇿 ДОПОЛНИТЕЛЬНАЯ ФИЛЬТРАЦИЯ: Приоритет казахстанским источникам
                        kazakhstan_indicators = [
                            '.kz' in link,  # казахстанские домены
                            'казахстан' in full_text,
                            'kazakhstan' in full_text,
                            'алматы' in full_text,
                            'astana' in full_text,
                            'астана' in full_text,
                            'almaty' in full_text,
                            'тенге' in full_text,  # казахстанская валюта
                            'kzt' in full_text
                        ]
                        is_kazakhstan_relevant = any(kazakhstan_indicators)
                        
                        # Исключаем результаты из других стран (если явно указана другая страна)
                        other_countries = [
                            'россия', 'russia', 'москва', 'moscow', 'рубл',
                            'украина', 'ukraine', 'киев', 'kyiv', 'гривна',
                            'беларусь', 'belarus', 'минск', 'minsk',
                            'узбекистан', 'uzbekistan', 'ташкент', 'tashkent'
                        ]
                        is_other_country = any(country in full_text for country in other_countries)
                        
                        # 📱 ОПРЕДЕЛЯЕМ ТИП ИСТОЧНИКА (социальные сети vs обычные сайты)
                        is_social_media = any(social in link for social in ['instagram.com', 'facebook.com', 'linkedin.com', 'vk.com'])
                        
                        # 🔍 АДАПТИВНЫЕ КРИТЕРИИ ФИЛЬТРАЦИИ:
                        if is_social_media:
                            # Более мягкие критерии для соцсетей (достаточно названия компании + казахстанская релевантность)
                            is_acceptable = (has_company_name and 
                                           is_kazakhstan_relevant and 
                                           not is_other_country and
                                           not has_exclude_keywords)
                        else:
                            # Строгие критерии для обычных веб-ресурсов
                            is_acceptable = (has_company_name and 
                                           is_charity_relevant and 
                                           not has_exclude_keywords and
                                           is_kazakhstan_relevant and 
                                           not is_other_country)
                        
                        if is_acceptable:
                            all_search_results.append(GoogleSearchResult(
                                title=item.get('title', 'Нет заголовка'),
                                link=link,
                                snippet=item.get('snippet', 'Нет описания')
                            ))
                            found_relevant += 1
                            source_type = "📱 СОЦСЕТЬ" if is_social_media else "🌐 ВЕБ"
                            print(f"✅ [CHARITY_RESEARCH] {source_type} фильтр ПРОЙДЕН: {item.get('title', '')[:50]}...")
                        else:
                            # Детальное логирование причин отклонения
                            reasons = []
                            if not has_company_name:
                                reasons.append("нет названия компании")
                            if not is_social_media and not is_charity_relevant:  # Для обычных сайтов проверяем ключевые слова
                                reasons.append("нет ключевых слов")
                            if has_exclude_keywords:
                                reasons.append("есть исключающие слова")
                            if not is_kazakhstan_relevant:
                                reasons.append("не касается Казахстана")
                            if is_other_country:
                                reasons.append("из другой страны")
                            source_type = "📱 СОЦСЕТЬ" if is_social_media else "🌐 ВЕБ"
                            print(f"🚫 [CHARITY_RESEARCH] {source_type} фильтр НЕ ПРОЙДЕН ({', '.join(reasons)}): {item.get('title', '')[:50]}...")
                
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
            f"Информации о благотворительной деятельности компании '{company_name}' "
            f"в КАЗАХСТАНСКИХ источниках НЕ НАЙДЕНО.\n\n"
            f"🔍 **Охват поиска:**\n"
            f"• Казахстанские веб-ресурсы (.kz домены)\n"
            f"• Социальные сети (Instagram, Facebook, LinkedIn)\n"
            f"• Варианты названий: {', '.join(company_variants)}\n"
            f"• Расширенные ключевые слова (включая события, мероприятия, поздравления)\n\n"
            f"Возможные причины:\n"
            f"• Компания не ведет публичную благотворительную деятельность в Казахстане\n"
            f"• Активность не освещается в публичных источниках\n"
            f"• Благотворительность ведется конфиденциально или через партнеров\n\n"
            f"💡 **Рекомендация:** Обратитесь напрямую к казахстанским представителям компании или проверьте их официальные социальные сети."
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
                f"✅ **НАЙДЕНЫ ДОКАЗАТЕЛЬСТВА** благотворительной деятельности компании '{company_name}' В КАЗАХСТАНЕ.\n\n"
                f"📊 **Статистика поиска:**\n"
                f"• Обнаружено {direct_evidence_count} источников с конкретными фактами\n"
                f"• Проверено {len(all_search_results)} материалов (веб-сайты + социальные сети)\n"
                f"• Варианты названий: {', '.join(company_variants)}\n\n"
                f"🎯 **Подтвержденная активность в Казахстане:** {activities_text}\n"
                f"📋 **Области деятельности:** {areas_text}\n\n"
                f"✅ **Вывод:** Компания ДЕЙСТВИТЕЛЬНО занимается благотворительностью в Казахстане.\n"
                f"💡 **Рекомендация:** Изучите приложенные источники и обратитесь в местный отдел КСО компании."
            )
        else:
            final_summary_for_response = (
                f"⚠️ **НАЙДЕНЫ УПОМИНАНИЯ**, но нет прямых доказательств благотворительной деятельности компании '{company_name}' в Казахстане.\n\n"
                f"📊 **Статистика поиска:**\n"
                f"• Найдено {len(all_search_results)} упоминаний в казахстанских источниках\n"
                f"• Охват: веб-ресурсы + социальные сети\n"
                f"• Варианты названий: {', '.join(company_variants)}\n\n"
                f"📝 **Характер найденной информации:**\n"
                f"• Упоминания в списках или каталогах\n"
                f"• Новости без конкретных подробностей\n"
                f"• Декларации о социальной ответственности без проектов\n\n"
                f"💡 **Рекомендация:** Требуется дополнительная проверка через официальные казахстанские каналы компании или их социальные сети."
            )

    # Финальное логирование результатов (ОПТИМИЗИРОВАННАЯ ВЕРСИЯ)
    total_queries = len(search_queries)
    total_results = len(all_search_results)
    
    if not all_search_results:
        print(f"🇰🇿📱 [CHARITY_RESEARCH] Завершено расширенное исследование компании '{company_name}' в КАЗАХСТАНЕ: 0 релевантных результатов из {total_queries} оптимизированных запросов")
        print(f"📊 [CHARITY_RESEARCH] Охват: веб-ресурсы + социальные сети. Варианты названий: {len(company_variants)}. Использовано {total_queries} запросов вместо 8-12")
        return CompanyCharityResponse(
            status="success",
            company_name=company_name,
            charity_info=[],
            summary=final_summary_for_response
        )

    print(f"✅🇰🇿📱 [CHARITY_RESEARCH] Расширенное исследование завершено для '{company_name}' в КАЗАХСТАНЕ: найдено {total_results} релевантных результатов из {total_queries} оптимизированных запросов")
    print(f"📊 [CHARITY_RESEARCH] Охват: веб-ресурсы + социальные сети. Варианты названий: {len(company_variants)}. Экономия API квот: {total_queries} вместо 8-12 запросов")
    
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