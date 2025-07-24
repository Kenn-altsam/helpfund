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

# Новый промпт для генерации сводки по благотворительности с использованием Gemini
CHARITY_SUMMARY_PROMPT_TEMPLATE = """
Проанализируй предоставленные результаты веб-поиска о компании "{company_name}" и подготовь краткую, информативную сводку о её благотворительной деятельности или социальных проектах. 

Если прямых доказательств благотворительности не найдено, укажи это. Если найдены косвенные упоминания (например, общая социальная ответственность без конкретных проектов), отметь это.

ФОКУСИРУЙСЯ ТОЛЬКО НА ИНФОРМАЦИИ, СВЯЗАННОЙ С БЛАГОТВОРИТЕЛЬНОСТЬЮ И КСО. НЕ ВКЛЮЧАЙ ИНФОРМАЦИЮ О ПРОДАЖАХ, ПРОДУКТАХ, ВАКАНСИЯХ ИЛИ НЕРЕЛЕВАНТНЫЕ НОВОСТИ.

Результаты веб-поиска:
{search_results_text}

Начни свой ответ со статуса: "НАЙДЕНЫ ПРЯМЫЕ ДОКАЗАТЕЛЬСТВА" или "КОСВЕННЫЕ УПОМИНАНИЯ" или "НЕ НАЙДЕНО ДОКАЗАТЕЛЬСТВ".
Далее предоставь краткую сводку. НЕ используй Markdown, только обычный текст.
"""


# Новый промпт для Gemini, чтобы он сам "искал" информацию
GEMINI_CHARITY_RESEARCH_PROMPT_TEMPLATE = """
Ты - эксперт по корпоративной социальной ответственности и благотворительности компаний. Твоя задача - найти и обобщить информацию о благотворительной деятельности компании "{company_name}" на основе твоих обширных знаний. 

{additional_context_prompt}

Сосредоточься на следующих аспектах:
- Наличие благотворительных программ или фондов.
- Конкретные области поддержки (например, образование, здравоохранение, экология, поддержка нуждающихся).
- Примеры конкретных акций, проектов или сумм пожертвований (если известны).
- Долгосрочные инициативы в области КСО.

Предоставь краткую, но исчерпывающую сводку. Если прямых доказательств благотворительной деятельности не найдено в твоих знаниях, укажи это, но предложи потенциальные причины или пути дальнейшего исследования. 

Ответь в структурированном виде, но НЕ В ФОРМАТЕ JSON. Используй маркированные списки или абзацы. Начни сразу с ответа, без вступлений типа "Конечно, вот информация...".
"""

class GeminiService:
    def __init__(self, api_key: str):
        self.settings = get_settings()
        self.gemini_api_key = api_key # ИСПОЛЬЗУЕМ API КЛЮЧ, ПЕРЕДАННЫЙ В КОНСТРУКТОР
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

    async def research_charity_online(self, company_name: str, additional_context: Optional[str] = None) -> str:
        """
        Выполняет исследование прошлой благотворительной деятельности компании через Gemini.
        Gemini будет генерировать сводку на основе своих внутренних знаний, без внешнего веб-поиска.
        """
        print(f"🌐 [GEMINI_RESEARCH] Starting charity research via Gemini for: {company_name}")

        additional_context_prompt = ""
        if additional_context and additional_context.strip():
            additional_context_prompt = f"Учитывай дополнительный контекст: {additional_context.strip()}.\n"

        prompt = GEMINI_CHARITY_RESEARCH_PROMPT_TEMPLATE.format(
            company_name=company_name,
            additional_context_prompt=additional_context_prompt
        )

        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client: # Увеличиваем таймаут на случай долгих ответов Gemini
                response = await client.post(self.gemini_url, json=payload)
                response.raise_for_status()
                g_data = response.json()
                
                # Проверяем наличие 'candidates' и 'content' перед доступом
                if 'candidates' in g_data and len(g_data['candidates']) > 0 and 'content' in g_data['candidates'][0] and 'parts' in g_data['candidates'][0]['content'] and len(g_data['candidates'][0]['content']['parts']) > 0:
                    summary = g_data["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"✅ [GEMINI_RESEARCH] Gemini charity analysis completed successfully.")
                    return summary.strip()
                else:
                    print(f"❌ [GEMINI_RESEARCH] Gemini returned no candidates or content: {g_data}")
                    return f"Не удалось получить информацию о благотворительности компании '{company_name}' от Gemini. Возможно, нет данных или проблема с ответом модели."

        except Exception as e:
            print(f"❌ [GEMINI_RESEARCH] Failed to perform Gemini charity research: {e}")
            traceback.print_exc()
            return f"Произошла техническая ошибка при обращении к Gemini для исследования благотворительности компании '{company_name}'. Попробуйте позже."

# Global service instance
ai_service = GeminiService(os.getenv("GEMINI_API_KEY"))