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
import asyncio
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from ..core.config import get_settings
from ..companies.service import CompanyService
from .location_service import get_canonical_location_from_text
from ..chats import service as chat_service
from ..chats.models import Chat, Message

load_dotenv()

# Rate limiting configuration
class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []
    
    async def acquire(self) -> bool:
        now = datetime.now()
        # Remove old requests outside the window
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < timedelta(seconds=self.window_seconds)]
        
        if len(self.requests) >= self.max_requests:
            return False
        
        self.requests.append(now)
        return True
    
    def get_wait_time(self) -> float:
        if not self.requests:
            return 0
        oldest_request = min(self.requests)
        return max(0, self.window_seconds - (datetime.now() - oldest_request).total_seconds())

# Global rate limiters
gemini_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)  # 30 requests per minute
google_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 10 requests per minute

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
- **Локация:** Город/область всегда должен быть на русском языке в официальном виде. Правила преобразования:
  - Английские названия: "Almaty" -> "Алматы", "Astana" -> "Астана"
  - Склонённые формы: "в Алмате", "из Астаны" -> "Алматы", "Астана"
  - Области с разными вариантами написания:
    * "Улытауской области", "области Улытау", "Улытау область" -> "Улытауская область"
    * "Абайской области", "области Абай", "Абай область" -> "Абайская область"
    * "Жетысуской области", "Жетисуской области", "области Жетысу", "области Жетису", "Жетысу область", "Жетису область" -> "Жетисуская область"
    * "Алматинской области", "области Алматы" -> "Алматинская область"
    * "Актюбинской области", "области Актобе" -> "Актюбинская область"
    * "Атырауской области", "области Атырау" -> "Атырауская область"
    * "Восточно-Казахстанской области", "области Восточный Казахстан" -> "Восточно-Казахстанская область"
    * "Жамбылской области", "области Жамбыл" -> "Жамбылская область"
    * "Западно-Казахстанской области", "области Западный Казахстан" -> "Западно-Казахстанская область"
    * "Карагандинской области", "области Караганда" -> "Карагандинская область"
    * "Костанайской области", "области Костанай" -> "Костанайская область"
    * "Кызылординской области", "области Кызылорда" -> "Кызылординская область"
    * "Мангистауской области", "области Мангистау" -> "Мангистауская область"
    * "Павлодарской области", "области Павлодар" -> "Павлодарская область"
    * "Северо-Казахстанской области", "области Северный Казахстан" -> "Северо-Казахстанская область"
    * "Туркестанской области", "области Туркестан" -> "Туркестанская область"
  Если локация не указана ни в текущем сообщении, ни в истории, `location` должен быть `null`.
- **Количество:** Извлеки точное число компаний из запроса (например, из "найди 30 компаний" извлеки 30). Если число не указано, используй 10.
- **Ключевые слова размера:** Если пользователь использует слова типа "крупных", "малых", "средних" компаний - просто игнорируй их и ищи обычные компании. Не добавляй их в activity_keywords.

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

Пример 1b: Запрос по размеру компаний (игнорируется)
История: []
Пользователь: "Найди 5 крупных компаний в Алматы"
Ожидаемый JSON:
{
  "intent": "find_companies",
  "location": "Алматы",
  "activity_keywords": null,
  "quantity": 5,
  "page_number": 1,
  "reasoning": "Запрос на поиск компаний. Слово 'крупных' игнорируется. Количество 5, страница 1.",
  "preliminary_response": "Ищу для вас 5 компаний в Алматы. Пожалуйста, подождите..."
}

Пример 1c: Запрос по размеру и деятельности (размер игнорируется)
История: []
Пользователь: "Найди 10 малых IT компаний в Астане"
Ожидаемый JSON:
{
  "intent": "find_companies",
  "location": "Астана",
  "activity_keywords": ["IT"],
  "quantity": 10,
  "page_number": 1,
  "reasoning": "Запрос на поиск IT компаний. Слово 'малых' игнорируется. Количество 10, страница 1.",
  "preliminary_response": "Ищу для вас 10 IT компаний в Астане. Пожалуйста, подождите..."
}

Пример 1d: Различные варианты написания областей
История: []
Пользователь: "5 крупных компаний Улытауской области"
Ожидаемый JSON:
{
  "intent": "find_companies",
  "location": "Улытауская область",
  "activity_keywords": null,
  "quantity": 5,
  "page_number": 1,
  "reasoning": "Запрос на поиск компаний. 'Улытауской области' преобразовано в 'Улытауская область'. Слово 'крупных' игнорируется. Количество 5, страница 1.",
  "preliminary_response": "Ищу для вас 5 компаний в Улытауской области. Пожалуйста, подождите..."
}

Пример 1e: Область с сокращенным названием
История: []
Пользователь: "10 крупных компаний области Абай"
Ожидаемый JSON:
{
  "intent": "find_companies",
  "location": "Абайская область",
  "activity_keywords": null,
  "quantity": 10,
  "page_number": 1,
  "reasoning": "Запрос на поиск компаний. 'области Абай' преобразовано в 'Абайская область'. Слово 'крупных' игнорируется. Количество 10, страница 1.",
  "preliminary_response": "Ищу для вас 10 компаний в Абайской области. Пожалуйста, подождите..."
}

Пример 1f: Жетысуская область с разными вариантами
История: []
Пользователь: "10 крупных компаний Жетысуской области"
Ожидаемый JSON:
{
  "intent": "find_companies",
  "location": "Жетисуская область",
  "activity_keywords": null,
  "quantity": 10,
  "page_number": 1,
  "reasoning": "Запрос на поиск компаний. 'Жетысуской области' преобразовано в 'Жетисуская область'. Слово 'крупных' игнорируется. Количество 10, страница 1.",
  "preliminary_response": "Ищу для вас 10 компаний в Жетисуской области. Пожалуйста, подождите..."
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

# <<< ШАБЛОН ПРОМПТА ДЛЯ АНАЛИЗА БЛАГОТВОРИТЕЛЬНОСТИ >>>
CHARITY_SUMMARY_PROMPT_TEMPLATE = """
Проанализируй найденную информацию о благотворительной деятельности компании "{company_name}" и составь краткую, но информативную сводку.

НАЙДЕННЫЕ МАТЕРИАЛЫ:
{search_results_text}

ЗАДАЧА:
1. Определи, есть ли достоверные доказательства благотворительной деятельности компании
2. Если есть - кратко опиши конкретные примеры (что делали, кому помогали, когда)
3. Если информации недостаточно или она неясная - честно об этом скажи
4. Используй профессиональный, но дружелюбный тон
5. Ответ должен быть в 2-4 предложениях, не больше

ВАЖНО:
- Не выдумывай информацию, которой нет в источниках
- Если найдена только реклама или общие фразы без конкретики - так и скажи
- Укажи конкретные факты, если они есть (суммы, получатели помощи, даты)

Пример хорошего ответа:
"По данным открытых источников, компания "Пример" в 2022 году выделила средства на ремонт детского дома №5 в Алматы и регулярно спонсирует образовательные программы для детей из малообеспеченных семей. Конкретные суммы пожертвований в источниках не указаны."

Пример честного ответа при недостатке информации:
"В открытых источниках найдены только общие упоминания о социальной ответственности компании без конкретных примеров благотворительных проектов или пожертвований."
"""

class GeminiService:
    def __init__(self):
        self.settings = get_settings()
        self.gemini_api_key = self.settings.GEMINI_API_KEY
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
        Uses Gemini to parse the user's intent from conversation history with rate limiting and retry logic.
        """
        # Rate limiting check
        if not await gemini_rate_limiter.acquire():
            wait_time = gemini_rate_limiter.get_wait_time()
            print(f"⚠️ [RATE_LIMIT] Gemini API rate limit reached. Wait {wait_time:.1f} seconds")
            raise HTTPException(
                status_code=429, 
                detail=f"Rate limit exceeded. Please wait {wait_time:.1f} seconds before trying again."
            )

        full_prompt_text = f"{GEMINI_INTENT_PROMPT}\n\n---\n\nИСТОРИЯ ДИАЛОГА:\n{json.dumps(history, ensure_ascii=False)}\n\n---\n\nПроанализируй последнее сообщение в истории и верни JSON."

        payload = {"contents": [{"parts": [{"text": full_prompt_text}]}]}
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Increased timeout values to handle complex prompts and slow responses
                timeout = httpx.Timeout(connect=10.0, read=90.0, write=20.0, pool=10.0)
                print(f"🔄 [GEMINI_REQUEST] Attempt {attempt + 1}/{max_retries}: Sending request to Gemini...")
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(self.gemini_url, json=payload)
                    
                    # Handle rate limiting
                    if response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', base_delay * (2 ** attempt)))
                        print(f"⚠️ [GEMINI_RATE_LIMIT] Attempt {attempt + 1}/{max_retries}: Rate limited, waiting {retry_after}s")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            raise HTTPException(status_code=429, detail="Gemini API rate limit exceeded. Please try again later.")
                    
                    # Handle service unavailable
                    if response.status_code == 503:
                        delay = base_delay * (2 ** attempt)
                        print(f"⚠️ [GEMINI_SERVICE_UNAVAILABLE] Attempt {attempt + 1}/{max_retries}: Service unavailable, waiting {delay}s")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(delay)
                            continue
                        else:
                            raise HTTPException(status_code=503, detail="Gemini API service temporarily unavailable. Please try again later.")
                    
                    response.raise_for_status()
                    
                    g_data = response.json()
                    raw_json_text = g_data["candidates"][0]["content"]["parts"][0]["text"]
                    
                    # Очистка от возможных ```json ... ``` оберток
                    cleaned_json_text = re.sub(r'```json\s*([\s\S]*?)\s*```', r'\1', raw_json_text, re.DOTALL).strip()
                    
                    parsed_result = json.loads(cleaned_json_text)
                    print(f"✅ [GEMINI_PARSER] Gemini response parsed successfully: {parsed_result}")
                    return parsed_result

            except httpx.TimeoutException as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⏰ [GEMINI_TIMEOUT] Attempt {attempt + 1}/{max_retries}: Request timed out after {timeout.read}s, waiting {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"❌ [GEMINI_TIMEOUT] Final attempt timed out: {e}")
                    return {
                        "intent": "unclear",
                        "location": None,
                        "activity_keywords": None,
                        "quantity": 10,
                        "page_number": 1,
                        "reasoning": f"Запрос к Gemini превысил время ожидания ({timeout.read}s). Попробуйте упростить запрос.",
                        "preliminary_response": "Извините, обработка вашего запроса заняла слишком много времени. Пожалуйста, упростите запрос или попробуйте позже."
                    }
            except httpx.HTTPStatusError as e:
                if e.response.status_code in [429, 503] and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️ [GEMINI_HTTP_ERROR] Attempt {attempt + 1}/{max_retries}: {e.response.status_code}, waiting {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"❌ [GEMINI_HTTP_ERROR] Final attempt failed: {e}")
                    raise
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️ [GEMINI_ERROR] Attempt {attempt + 1}/{max_retries}: {type(e).__name__}: {e}, waiting {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"❌ [GEMINI_PARSER] Error during Gemini intent parsing: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    return {
                        "intent": "unclear",
                        "location": None,
                        "activity_keywords": None,
                        "quantity": 10,
                        "page_number": 1,
                        "reasoning": f"Не удалось обработать запрос через Gemini: {type(e).__name__}: {str(e)}",
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
            
            # Проверяем, был ли это запрос на продолжение
            is_continuation_request = any(keyword in user_input.lower() for keyword in [
                'еще', 'ещё', 'дальше', 'следующие', 'следующая', 'продолжи', 'продолжай',
                'more', 'next', 'continue', 'дай еще', 'дай ещё', 'покажи еще', 'покажи ещё'
            ])
            
            if db_companies:
                companies_data = db_companies
                final_message = self._generate_summary_response(db_history, companies_data)
            else:
                # Получаем общее количество компаний в регионе для информативности
                total_companies_in_region = company_service.get_total_company_count_by_location(location)
                companies_viewed = (page - 1) * search_limit
                # Улучшенное сообщение для случая отсутствия результатов
                if page == 1:
                    # Первый поиск - нет компаний вообще
                    if activity_keywords:
                        final_message = f"К сожалению, в {location} не найдено компаний по запросу '{', '.join(activity_keywords)}'. Попробуйте:\n\n• Изменить ключевые слова поиска\n• Убрать фильтры по деятельности\n• Поискать в другом регионе"
                    else:
                        final_message = f"К сожалению, в {location} не найдено компаний. Возможные причины:\n\n• В базе данных нет компаний из этого региона\n• Попробуйте поискать в соседних регионах\n• Укажите более крупный город в этом регионе"
                else:
                    # Последующие страницы - больше нет компаний
                    if is_continuation_request:
                        # Специальное сообщение для запросов "еще"
                        if activity_keywords:
                            final_message = f"Больше компаний в {location} по запросу '{', '.join(activity_keywords)}' не найдено. Вы просмотрели все доступные результаты.\n\nПопробуйте:\n• Изменить критерии поиска\n• Поискать в других регионах\n• Убрать фильтры по деятельности"
                        else:
                            final_message = f"Больше компаний в {location} не найдено. Вы просмотрели все доступные результаты.\n\nПопробуйте:\n• Поискать в других регионах\n• Добавить фильтры по деятельности\n• Указать более крупный город"
                    else:
                        # Обычное сообщение для последующих страниц с информацией о количестве
                        if total_companies_in_region > 0:
                            if activity_keywords:
                                final_message = f"Вы просмотрели все доступные компании в {location} по запросу '{', '.join(activity_keywords)}' (страница {page}). Всего в регионе найдено {total_companies_in_region} компаний, вы просмотрели {companies_viewed}.\n\nПопробуйте:\n• Изменить критерии поиска\n• Поискать в других регионах\n• Убрать фильтры по деятельности"
                            else:
                                final_message = f"Вы просмотрели все доступные компании в {location} (страница {page}). Всего в регионе найдено {total_companies_in_region} компаний, вы просмотрели {companies_viewed}.\n\nПопробуйте:\n• Поискать в других регионах\n• Добавить фильтры по деятельности\n• Указать более крупный город"
                        else:
                            if activity_keywords:
                                final_message = f"Вы просмотрели все доступные компании в {location} по запросу '{', '.join(activity_keywords)}' (страница {page}). Больше результатов нет.\n\nПопробуйте:\n• Изменить критерии поиска\n• Поискать в других регионах\n• Убрать фильтры по деятельности"
                            else:
                                final_message = f"Вы просмотрели все доступные компании в {location} (страница {page}). Больше результатов нет.\n\nПопробуйте:\n• Поискать в других регионах\n• Добавить фильтры по деятельности\n• Указать более крупный город"
        
        elif intent == "find_companies" and not location:
            final_message = "Чтобы найти компании, мне нужно знать, в каком городе вы хотите искать. Пожалуйста, укажите местоположение."
        
        elif intent == "find_companies" and location == "null":
            # Специальная обработка для случая, когда область не найдена
            final_message = """К сожалению, указанная область не найдена в базе данных. 

Доступные области:
• Алматинская область
• Атырауская область  
• Актюбинская область
• Карагандинская область
• Костанайская область
• Кызылординская область
• Мангистауская область
• Павлодарская область
• Жамбылская область
• Восточно-Казахстанская область
• Западно-Казахстанская область
• Акмолинская область
• Южно-Казахстанская область
• Улытауская область
• Абайская область
• Жетисуская область

Пожалуйста, выберите одну из доступных областей или укажите конкретный город."""

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
        Выполняет оптимизированный и умный Google поиск прошлой благотворительной деятельности компании.
        Делает максимум 2 целенаправленных запроса для максимальной релевантности.
        """
        # Rate limiting check for Google API
        if not await google_rate_limiter.acquire():
            wait_time = google_rate_limiter.get_wait_time()
            print(f"⚠️ [RATE_LIMIT] Google API rate limit reached. Wait {wait_time:.1f} seconds")
            raise HTTPException(
                status_code=429, 
                detail=f"Google API rate limit exceeded. Please wait {wait_time:.1f} seconds before trying again."
            )

        print(f"🌐 [WEB_RESEARCH] Starting SMART charity research for: {company_name}")

        # УЛУЧШЕНИЕ 1: Умная очистка названия компании
        # Убираем организационно-правовые формы и символы для более точного поиска
        clean_company_name = re.sub(
            r'^(ТОО|АО|ИП|A\.O\.|TOO|LLP|JSC|ОДО|ООО|ЗАО|ПАО)\s*|"|«|»|["\']', 
            '', 
            company_name, 
            flags=re.IGNORECASE
        ).strip()
        print(f"   -> Optimized search name: '{clean_company_name}'")

        # УЛУЧШЕНИЕ 2: Максимально релевантные ключевые слова для Казахстана
        core_charity_terms = [
            "благотворительность", "пожертвования", "спонсорство", 
            "социальная ответственность", "помощь", "поддержка"
        ]
        
        specific_charity_actions = [
            "детский дом", "фонд", "образование", "здравоохранение",
            "помощь малообеспеченным", "социальный проект"
        ]

        # УЛУЧШЕНИЕ 3: Два стратегических запроса вместо множества
        # Запрос 1: Основные благотворительные термины
        query_1 = f'"{clean_company_name}" Казахстан ({" OR ".join(core_charity_terms[:3])})'
        
        # Запрос 2: Конкретные благотворительные действия
        query_2 = f'"{clean_company_name}" ({" OR ".join(specific_charity_actions[:3])})'

        queries_to_execute = [query_1, query_2]
        
        search_results_text = ""
        unique_links = set()
        max_results_per_query = 3  # Ограничиваем для концентрации на качестве

        timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for i, query in enumerate(queries_to_execute, 1):
                search_url = f"https://www.googleapis.com/customsearch/v1?key={self.settings.GOOGLE_API_KEY}&cx={self.settings.GOOGLE_SEARCH_ENGINE_ID}&q={query}&num={max_results_per_query}&lr=lang_ru"
                print(f"   -> Executing strategic query {i}/2: {query}")
                
                # Retry logic for Google API calls
                max_retries = 2
                base_delay = 2.0
                
                for attempt in range(max_retries):
                    try:
                        response = await client.get(search_url)
                        
                        # Handle rate limiting
                        if response.status_code == 429:
                            retry_after = int(response.headers.get('Retry-After', base_delay * (2 ** attempt)))
                            print(f"⚠️ [GOOGLE_RATE_LIMIT] Query {i}, attempt {attempt + 1}: Rate limited, waiting {retry_after}s")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_after)
                                continue
                            else:
                                print(f"❌ [WEB_RESEARCH] Rate limit reached. Stopping search.")
                                break
                        
                        # Handle service unavailable
                        if response.status_code == 503:
                            delay = base_delay * (2 ** attempt)
                            print(f"⚠️ [GOOGLE_SERVICE_UNAVAILABLE] Query {i}, attempt {attempt + 1}: Service unavailable, waiting {delay}s")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(delay)
                                continue
                            else:
                                print(f"❌ [WEB_RESEARCH] Service unavailable. Stopping search.")
                                break
                        
                        response.raise_for_status()
                        data = response.json()

                        if 'items' in data:
                            for item in data['items']:
                                link = item.get('link')
                                title = item.get('title', '')
                                snippet = item.get('snippet', '')
                                
                                # Фильтруем результаты на релевантность
                                if link and link not in unique_links and self._is_charity_relevant(title, snippet):
                                    unique_links.add(link)
                                    search_results_text += f"📄 Источник:\n"
                                    search_results_text += f"Заголовок: {title}\n"
                                    search_results_text += f"Описание: {snippet}\n"
                                    search_results_text += f"Ссылка: {link}\n\n"
                        
                        # Success, break retry loop
                        break
                        
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code in [429, 503] and attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            print(f"⚠️ [GOOGLE_HTTP_ERROR] Query {i}, attempt {attempt + 1}: {e.response.status_code}, waiting {delay}s")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            print(f"⚠️ [WEB_RESEARCH] HTTP error for query {i}: {e}")
                            break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            print(f"⚠️ [GOOGLE_ERROR] Query {i}, attempt {attempt + 1}: {e}, waiting {delay}s")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            print(f"⚠️ [WEB_RESEARCH] Error for query {i}: {e}")
                            traceback.print_exc()
                            break
                
                # Задержка между запросами (теперь максимум 2 запроса)
                if i < len(queries_to_execute) - 1:  # Не ждем после последнего запроса
                    await asyncio.sleep(2.0)  # Увеличиваем задержку для стабильности

        # Если ничего релевантного не найдено
        if not search_results_text.strip():
            return f"По компании '{company_name}' в открытых источниках не найдено достоверной информации о благотворительной деятельности или социальных проектах. Рекомендуется обратиться напрямую к компании для получения такой информации."

        # УЛУЧШЕНИЕ 4: Генерация качественной сводки через Gemini
        summary_prompt = CHARITY_SUMMARY_PROMPT_TEMPLATE.format(
            company_name=company_name, 
            search_results_text=search_results_text
        )
        
        payload = {"contents": [{"parts": [{"text": summary_prompt}]}]}
        
        # Retry logic for Gemini summary generation
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                timeout = httpx.Timeout(connect=5.0, read=45.0, write=10.0, pool=5.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(self.gemini_url, json=payload)
                    
                    # Handle rate limiting
                    if response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', base_delay * (2 ** attempt)))
                        print(f"⚠️ [GEMINI_SUMMARY_RATE_LIMIT] Attempt {attempt + 1}/{max_retries}: Rate limited, waiting {retry_after}s")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            return f"Найдена информация о возможной благотворительной деятельности компании '{company_name}', но не удалось обработать данные из-за ограничений API. Попробуйте позже."
                    
                    # Handle service unavailable
                    if response.status_code == 503:
                        delay = base_delay * (2 ** attempt)
                        print(f"⚠️ [GEMINI_SUMMARY_SERVICE_UNAVAILABLE] Attempt {attempt + 1}/{max_retries}: Service unavailable, waiting {delay}s")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(delay)
                            continue
                        else:
                            return f"Найдена информация о возможной благотворительной деятельности компании '{company_name}', но сервис временно недоступен. Попробуйте позже."
                    
                    response.raise_for_status()
                    g_data = response.json()
                    summary = g_data["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"✅ [AI_SUMMARY] Smart charity analysis completed successfully.")
                    return summary.strip()
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code in [429, 503] and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️ [GEMINI_SUMMARY_HTTP_ERROR] Attempt {attempt + 1}/{max_retries}: {e.response.status_code}, waiting {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"❌ [AI_SUMMARY] Failed to generate charity summary: {e}")
                    return f"Найдена информация о возможной благотворительной деятельности компании '{company_name}', но не удалось обработать данные из-за технической ошибки. Попробуйте позже."
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️ [GEMINI_SUMMARY_ERROR] Attempt {attempt + 1}/{max_retries}: {e}, waiting {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"❌ [AI_SUMMARY] Failed to generate charity summary: {e}")
                    traceback.print_exc()
                    return f"Найдена информация о возможной благотворительной деятельности компании '{company_name}', но не удалось обработать данные из-за технической ошибки. Попробуйте позже."

    def _is_charity_relevant(self, title: str, snippet: str) -> bool:
        """
        Проверяет релевантность результата поиска для благотворительной деятельности.
        Фильтрует спам и нерелевантные результаты.
        """
        combined_text = f"{title} {snippet}".lower()
        
        # Позитивные индикаторы благотворительности
        positive_indicators = [
            "благотворительность", "пожертвование", "спонсорство", "помощь", 
            "поддержка", "фонд", "социальная ответственность", "CSR",
            "детский дом", "больница", "образование", "стипендия",
            "волонтер", "донор", "меценат", "гранты"
        ]
        
        # Негативные индикаторы (спам, реклама, не благотворительность)
        negative_indicators = [
            "купить", "скидка", "цена", "товар", "услуга", "продажа",
            "реклама", "заказать", "доставка", "магазин", "каталог",
            "вакансия", "работа", "резюме", "сотрудник"
        ]
        
        # Подсчитываем релевантность
        positive_score = sum(1 for indicator in positive_indicators if indicator in combined_text)
        negative_score = sum(1 for indicator in negative_indicators if indicator in combined_text)
        
        # Результат релевантен, если есть позитивные индикаторы и мало негативных
        is_relevant = positive_score > 0 and negative_score <= positive_score
        
        if not is_relevant:
            print(f"   -> Filtered out non-relevant result: {title[:50]}...")
        
        return is_relevant

# Global service instance
ai_service = GeminiService()