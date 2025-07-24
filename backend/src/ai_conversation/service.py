"""
OpenAI service for AI conversation functionality

Handles communication with Azure OpenAI API for charity sponsorship matching.
"""

import httpx
import json
import re
import traceback
import os
import uuid
from typing import Optional, Dict, Any, List

from fastapi import HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from ..core.config import get_settings
from ..companies.service import CompanyService
from .location_service import get_canonical_location_from_text
from ..chats import service as chat_service
from ..chats.models import Chat, Message

load_dotenv()

# <<< НОВЫЙ ПРОМПТ ДЛЯ GEMINI >>>
GEMINI_INTENT_PROMPT = """
Твоя задача — проанализировать историю диалога и последнее сообщение пользователя, чтобы извлечь параметры для поиска компаний в базе данных. Ты должен ответить ТОЛЬКО одним валидным JSON-объектом без каких-либо других слов или форматирования.

КОНТЕКСТ ИЗ ИСТОРИИ:
1.  **Найди базовый запрос:** В истории диалога найди последний запрос пользователя, где были указаны параметры поиска (город, ключевые слова).
2.  **Используй контекст:** Если текущий запрос — это продолжение ("дай еще", "следующие"), ты ОБЯЗАН использовать город и ключевые слова из найденного базового запроса.
3.  **Страницы (Pagination) и Quantity:** Если текущий запрос является продолжением (например, "дай еще", "next"), **найди в истории последний объект с ролью "assistant", который имеет поле `parsed_intent`. Из этого `parsed_intent` возьми `quantity` и увеличь `page_number` на 1.** Для первого или нового поиска `page_number` всегда 1, а `quantity` извлекается из текущего запроса пользователя или по умолчанию 10.

ВАЖНО ДЛЯ ПАГИНАЦИИ:
- **Первый запрос:** page_number = 1, offset = 0
- **Второй запрос ("дай еще"):** page_number = 2, offset = quantity
- **Третий запрос ("дай еще"):** page_number = 3, offset = quantity * 2
- И так далее...

ПРАВИЛА:
- **Локация:** Город всегда должен быть на русском языке (например, "Almaty" -> "Алматы"). Если пользователь пишет склонённую или неофициальную форму города (например, "в Алмате", "из Астаны"), ты ОБЯЗАН преобразовать её в официальный вид (например, "Алматы", "Астана"). Если город не указан ни в текущем сообщении, ни в истории, `location` должен быть `null`.
- **Количество:** Извлеки точное число компаний из запроса (например, из "найди 30 компаний" извлеки 30). Если число не указано, используй 10.
- **Ответ:** Только JSON. Никаких "Вот ваш JSON:" или ```json ... ```.

Помни, что `parsed_intent` в истории ассистента содержит предыдущие успешно извлеченные параметры.

Структура JSON:
{
  "intent": "find_companies" | "general_question" | "unclear",
  "location": "string | null",
  "activity_keywords": ["string"] | null,
  "quantity": "number | null,
  "page_number": "number",
  "reasoning": "Краткое объяснение твоей логики.",
  "preliminary_response": "Ответ-заглушка для пользователя, пока идет поиск."
}

--- ПРИМЕРЫ ---

Пример 1: Первый запрос
История: []
Пользователь: "Найди 15 IT компаний в Almaty"
Ожидаемый JSON:
{
  "intent": "find_companies",
  "location": "Алматы",
  "activity_keywords": ["IT"],
  "quantity": 15,
  "page_number": 1,
  "reasoning": "Первый запрос. Город Almaty переведен в Алматы. Количество 15, страница 1.",
  "preliminary_response": "Отлично! Ищу для вас 15 IT-компаний в Алматы. Один момент..."
}

Пример 1a: Склонённая форма города
История: []
Пользователь: "Найди 10 компаний в Алмате"
Ожидаемый JSON:
{
  "intent": "find_companies",
  "location": "Алматы",
  "activity_keywords": null,
  "quantity": 10,
  "page_number": 1,
  "reasoning": "Город указан в склонённой форме ('в Алмате'), преобразовал в официальный вид 'Алматы'. Количество 10, страница 1.",
  "preliminary_response": "Ищу для вас 10 компаний в Алматы. Пожалуйста, подождите..."
}

Пример 2: Запрос на продолжение
История: [
  {"role": "user", "content": "Найди 15 IT компаний в Almaty"},
  {"role": "assistant", "content": "Отличные новости! Я нашел информацию...", "parsed_intent": {"intent": "find_companies", "location": "Алматы", "activity_keywords": ["IT"], "quantity": 15, "page_number": 1}}
]
Пользователь: "дай еще"
Ожидаемый JSON:
{
  "intent": "find_companies",
  "location": "Алматы",
  "activity_keywords": ["IT"],
  "quantity": 15,
  "page_number": 2,
  "reasoning": "Запрос на продолжение. Взял location, activity_keywords и quantity из `parsed_intent` предыдущего ответа ассистента в истории. Увеличил страницу до 2.",
  "preliminary_response": "Конечно! Ищу следующую группу из 15 IT-компаний в Алматы. Подождите, пожалуйста."
}

Пример 3: Третий запрос на продолжение
История: [
  {"role": "user", "content": "Найди 15 IT компаний в Almaty"},
  {"role": "assistant", "content": "Отличные новости! Я нашел информацию...", "parsed_intent": {"intent": "find_companies", "location": "Алматы", "activity_keywords": ["IT"], "quantity": 15, "page_number": 1}},
  {"role": "user", "content": "дай еще"},
  {"role": "assistant", "content": "Конечно! Ищу следующую группу...", "parsed_intent": {"intent": "find_companies", "location": "Алматы", "activity_keywords": ["IT"], "quantity": 15, "page_number": 2}}
]
Пользователь: "дай еще"
Ожидаемый JSON:
{
  "intent": "find_companies",
  "location": "Алматы",
  "activity_keywords": ["IT"],
  "quantity": 15,
  "page_number": 3,
  "reasoning": "Запрос на продолжение. Взял location, activity_keywords и quantity из `parsed_intent` предыдущего ответа ассистента в истории. Увеличил страницу до 3.",
  "preliminary_response": "Конечно! Ищу следующую группу из 15 IT-компаний в Алматы. Подождите, пожалуйста."
}
"""

class GeminiService:
    def __init__(self):
        self.settings = get_settings()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in the environment variables.")
        self.gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.gemini_api_key}"

    def _load_chat_history_from_db(self, db: Session, chat_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        Загружает историю сообщений из базы данных и преобразует в формат для Gemini.
        """
        try:
            # Загружаем чат с сообщениями
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                print(f"🔍 [DB_HISTORY] Chat {chat_id} not found, starting with empty history")
                return []

            # Преобразуем сообщения в формат истории
            history = []
            for message in sorted(chat.messages, key=lambda m: m.created_at):
                message_dict = {
                    "role": message.role,
                    "content": message.content
                }
                
                # Если у сообщения есть данные (например parsed_intent), добавляем их
                if message.data:
                    message_dict.update(message.data)
                
                history.append(message_dict)

            print(f"🔍 [DB_HISTORY] Loaded {len(history)} messages from chat {chat_id}")
            return history

        except Exception as e:
            print(f"❌ [DB_HISTORY] Error loading chat history: {e}")
            traceback.print_exc()
            return []

    def _save_message_to_db(self, db: Session, chat_id: uuid.UUID, role: str, content: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Сохраняет сообщение в базу данных.
        """
        try:
            message = Message(
                chat_id=chat_id,
                role=role,
                content=content,
                data=data
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            print(f"💾 [DB_SAVE] Saved {role} message to chat {chat_id}")
        except Exception as e:
            print(f"❌ [DB_SAVE] Error saving message: {e}")
            traceback.print_exc()
            db.rollback()

    async def _parse_user_intent_with_gemini(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Uses Gemini to parse the user's intent from conversation history.
        """
        full_prompt_text = f"{GEMINI_INTENT_PROMPT}\n\n---\n\nИСТОРИЯ ДИАЛОГА:\n{json.dumps(history, ensure_ascii=False)}\n\n---\n\nПроанализируй последнее сообщение в истории и верни JSON."

        payload = {"contents": [{"parts": [{"text": full_prompt_text}]}]}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.gemini_url, json=payload)
                response.raise_for_status()
                
                g_data = response.json()
                raw_json_text = g_data["candidates"][0]["content"]["parts"][0]["text"]
                
                # Очистка от возможных ```json ... ``` оберток
                cleaned_json_text = re.sub(r'```json\s*([\s\S]*?)\s*```', r'\1', raw_json_text, re.DOTALL).strip()
                
                parsed_result = json.loads(cleaned_json_text)
                print(f"✅ [GEMINI_PARSER] Gemini response parsed successfully: {parsed_result}")
                return parsed_result

        except Exception as e:
            print(f"❌ [GEMINI_PARSER] Error during Gemini intent parsing: {e}")
            traceback.print_exc()
            return {
                "intent": "unclear",
                "location": None,
                "activity_keywords": None,
                "quantity": 10,
                "page_number": 1,
                "reasoning": f"Не удалось обработать запрос через Gemini: {str(e)}",
                "preliminary_response": "Извините, у меня возникла проблема с пониманием вашего запроса. Пожалуйста, перефразируйте."
            }

    def _generate_summary_response(self, history: List[Dict[str, str]], companies_data: List[Dict[str, Any]]) -> str:
        """Craft a summary response based on found companies."""
        if not companies_data:
            return "К сожалению, по вашему запросу не найдено подходящих компаний. Попробуйте изменить критерии поиска."

        count = len(companies_data)
        if count == 1:
            opening = f"Отличные новости! Я нашел информацию о {count} компании:"
        elif 2 <= count <= 4:
            opening = f"Отличные новости! Я нашел информацию о {count} компаниях:"
        else:
            opening = f"Отличные новости! Я нашел информацию о {count} компаниях:"

        parts = [opening, ""]
        for comp in companies_data:
            name = comp.get("name", "Неизвестная компания")
            activity = comp.get("activity", "Деятельность не указана")
            locality = comp.get("locality", "Местоположение не указано")
            entry = f"• **{name}**\n  - Деятельность: {activity}\n  - Местоположение: {locality}"
            parts.append(entry)
        
        parts.append("\nЕсли вам нужна дополнительная информация или новый поиск, дайте знать!")
        return "\n".join(parts)

    async def handle_conversation_turn(self, user_input: str, history: List[Dict[str, str]], db: Session, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Main logic for handling a conversation turn using Gemini with database persistence."""
        print(f"🔄 [SERVICE] Handling turn with database persistence for: {user_input[:100]}...")
        
        # Конвертируем conversation_id в UUID для работы с базой данных
        chat_id = None
        if conversation_id:
            try:
                chat_id = uuid.UUID(conversation_id)
                print(f"🔄 [SERVICE] Using existing chat_id: {chat_id}")
            except ValueError:
                print(f"❌ [SERVICE] Invalid conversation_id format: {conversation_id}")
                raise HTTPException(status_code=400, detail="Invalid conversation_id format")

        # Загружаем историю из базы данных вместо использования параметра history
        if chat_id:
            db_history = self._load_chat_history_from_db(db, chat_id)
        else:
            db_history = []
            print(f"🔄 [SERVICE] No chat_id provided, starting with empty history")

        # Добавляем новое сообщение пользователя в историю для анализа
        db_history.append({"role": "user", "content": user_input})
        
        # Парсим намерение пользователя через Gemini
        parsed_intent = await self._parse_user_intent_with_gemini(db_history)

        intent = parsed_intent.get("intent")
        location = parsed_intent.get("location")
        activity_keywords = parsed_intent.get("activity_keywords")
        page = parsed_intent.get("page_number", 1)
        search_limit = parsed_intent.get("quantity", 10)
        offset = (page - 1) * search_limit
        
        # Отладочная информация для пагинации
        print(f"📄 [PAGINATION] Page: {page}, Limit: {search_limit}, Offset: {offset}")
        print(f"📄 [PAGINATION] Parsed intent: {parsed_intent}")
        
        final_message = parsed_intent.get("preliminary_response", "Обрабатываю ваш запрос...")
        companies_data = []

        # Поиск компаний если это запрос поиска
        if intent == "find_companies" and location:
            print(f"🏢 Searching DB: location='{location}', keywords={activity_keywords}, limit={search_limit}, offset={offset}")
            company_service = CompanyService(db)
            db_companies = company_service.search_companies(
                location=location,
                activity_keywords=activity_keywords,
                limit=search_limit,
                offset=offset
            )
            
            print(f"📈 Found {len(db_companies) if db_companies else 0} companies in database.")
            
            if db_companies:
                companies_data = db_companies
                final_message = self._generate_summary_response(db_history, companies_data)
            else:
                final_message = f"Я искал компании в {location} по вашему запросу, но не смог найти больше результатов на странице {page}. Попробуйте изменить критерии поиска."
                if page > 1:
                    final_message += " Возможно, вы уже просмотрели все доступные компании по этим критериям."
        
        elif intent == "find_companies" and not location:
            final_message = "Чтобы найти компании, мне нужно знать, в каком городе вы хотите искать. Пожалуйста, укажите местоположение."

        # Сохраняем сообщения в базу данных если есть chat_id
        if chat_id:
            # Сохраняем сообщение пользователя
            self._save_message_to_db(db, chat_id, "user", user_input)
            
            # Сохраняем ответ ассистента с parsed_intent и данными о компаниях
            assistant_data = {
                "parsed_intent": parsed_intent,
                "companies": companies_data
            }
            self._save_message_to_db(db, chat_id, "assistant", final_message, assistant_data)

        # Формируем обновленную историю для ответа (включая новые сообщения)
        updated_history = db_history.copy()
        updated_history.append({
            "role": "assistant",
            "content": final_message,
            "metadata": {"companies": companies_data},
            "parsed_intent": parsed_intent
        })

        return {
            'message': final_message,
            'companies': companies_data,
            'updated_history': updated_history,
            'reasoning': parsed_intent.get('reasoning'),
            'metadata': {"companies": companies_data}
        }

    async def _research_charity_online(self, company_name: str) -> str:
        """
        Performs a FOCUSED AND OPTIMIZED Google search for a company's past charity involvement.
        Now uses a single, powerful query to avoid hitting rate limits.
        """
        print(f"🌐 [WEB_RESEARCH] Starting OPTIMIZED charity research for: {company_name}")
        
        # --- ОДИН, НО МОЩНЫЙ ЗАПРОС ---
        # Мы ищем точное название компании И одно из ключевых слов о благотворительности.
        # Оператор OR позволяет объединить все в один запрос.
        search_keywords = [
            "благотворительность",
            "пожертвования", 
            "спонсорство",
            "социальная ответственность",
            "поддержал фонд",
            "выступил спонсором",
            "charity",
            "donation",
            "sponsorship",
            "КСО",
            "CSR",
            "благотворительный фонд"
        ]
        # Собираем ключевые слова в одну строку с оператором OR
        keywords_query_part = " OR ".join(f'"{kw}"' for kw in search_keywords)
        
        # Формируем финальный запрос: "Название компании" И (ключевое слово 1 OR ключевое слово 2 ...)
        final_query = f'"{company_name}" ({keywords_query_part})'
        
        print(f"🔍 [WEB_RESEARCH] Sending single, powerful query: {final_query}")
        
        search_results_text = ""
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Увеличим количество результатов за один запрос до 10
            search_url = (
                f"https://www.googleapis.com/customsearch/v1?"
                f"key={os.getenv('GOOGLE_API_KEY')}&"
                f"cx={os.getenv('GOOGLE_SEARCH_ENGINE_ID')}&"
                f"q={final_query}&"
                f"num=10&"
                f"lr=lang_ru&"  # Предпочтение русскому языку
                f"gl=kz"  # Географическое ограничение - Казахстан
            )
            
            try:
                response = await client.get(search_url)
                response.raise_for_status()  # Проверяем на ошибки типа 429
                data = response.json()
                
                total_found = len(data.get('items', []))
                relevant_count = 0
                
                if 'items' in data:
                    for item in data['items']:
                        title = item.get('title', '')
                        snippet = item.get('snippet', '')
                        
                        # Простая проверка релевантности
                        text_to_check = (title + " " + snippet).lower()
                        charity_indicators = [
                            'благотворительность', 'пожертвования', 'спонсорство', 'фонд',
                            'социальная ответственность', 'КСО', 'charity', 'donation', 
                            'sponsorship', 'поддержка', 'помощь'
                        ]
                        
                        # Исключаем очевидно нерелевантные результаты
                        exclude_indicators = [
                            'вакансия', 'работа', 'услуги', 'продажа', 'цена', 'стоимость',
                            'vacancy', 'job', 'services', 'sale', 'price'
                        ]
                        
                        is_relevant = any(indicator in text_to_check for indicator in charity_indicators)
                        has_excludes = any(exclude in text_to_check for exclude in exclude_indicators)
                        
                        if is_relevant and not has_excludes:
                            search_results_text += f"Результат:\nЗаголовок: {title}\nФрагмент: {snippet}\n\n"
                            relevant_count += 1
                            print(f"✅ [WEB_RESEARCH] Релевантный: {title[:50]}...")
                        else:
                            print(f"🚫 [WEB_RESEARCH] Отфильтрован: {title[:50]}...")
                
                print(f"📊 [WEB_RESEARCH] Найдено {total_found} результатов, релевантных: {relevant_count}")
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    print(f"❌ [WEB_RESEARCH] Rate limit hit! You have exceeded your daily Google Search API quota.")
                    return "Не удалось выполнить поиск в интернете, так как дневной лимит запросов к поисковой системе исчерпан. Пожалуйста, попробуйте завтра."
                else:
                    print(f"❌ [WEB_RESEARCH] HTTP error during search: {e}")
                    return "Произошла ошибка при обращении к поисковой системе."
            except Exception as e:
                print(f"⚠️ [WEB_RESEARCH] Google Search query failed: {e}")

        if not search_results_text:
            return f"В открытых источниках не найдено информации о благотворительной деятельности компании '{company_name}'."

        # Генерируем сводку с помощью Gemini
        summary_prompt = CHARITY_SUMMARY_PROMPT_TEMPLATE.format(
            company_name=company_name, 
            search_results_text=search_results_text
        )
        
        payload = {"contents": [{"parts": [{"text": summary_prompt}]}]}
        
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(self.gemini_url, json=payload)
                response.raise_for_status()
                g_data = response.json()
                summary = g_data["candidates"][0]["content"]["parts"][0]["text"]
                print(f"✅ [AI_SUMMARY] Optimized charity summary generated successfully.")
                return summary
        except Exception as e:
            print(f"❌ [AI_SUMMARY] Failed to generate charity summary: {e}")
            return "Не удалось сгенерировать сводку по найденным материалам из-за технической ошибки."

# <<< НОВЫЙ ПРОМПТ ДЛЯ АНАЛИЗА БЛАГОТВОРИТЕЛЬНОСТИ >>>
CHARITY_SUMMARY_PROMPT_TEMPLATE = """
Проанализируй следующие результаты поиска о компании "{company_name}" и сгенерируй краткую, информативную сводку о её благотворительной деятельности.

РЕЗУЛЬТАТЫ ПОИСКА:
{search_results_text}

ИНСТРУКЦИИ:
1. Сосредоточься только на благотворительной деятельности, социальной ответственности и спонсорстве
2. Игнорируй информацию о вакансиях, рекламе товаров/услуг, обычной деловой активности
3. Если найдена релевантная информация, укажи:
   - Виды благотворительной деятельности
   - Области поддержки (образование, здравоохранение, спорт, культура, экология и т.д.)
   - Конкретные программы или фонды (если упоминаются)
4. Если релевантной информации мало или нет, честно об этом сообщи
5. Ответ должен быть на русском языке, объемом 2-4 предложения
6. Избегай домыслов и предположений - основывайся только на найденных фактах

Сводка:
"""

# Global service instance
ai_service = GeminiService()