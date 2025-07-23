"""
OpenAI service for AI conversation functionality

Handles communication with Azure OpenAI API for charity sponsorship matching.
"""

import httpx
import json
import re
import traceback
import os
from typing import Optional, Dict, Any, List

from fastapi import HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from ..core.config import get_settings
from ..companies.service import CompanyService
from .location_service import get_canonical_location_from_text

load_dotenv()

# <<< НОВЫЙ ПРОМПТ ДЛЯ GEMINI >>>
GEMINI_INTENT_PROMPT = """
Твоя задача — проанализировать историю диалога и последнее сообщение пользователя, чтобы извлечь параметры для поиска компаний в базе данных. Ты должен ответить ТОЛЬКО одним валидным JSON-объектом без каких-либо других слов или форматирования.

КОНТЕКСТ ИЗ ИСТОРИИ:
1.  **Найди базовый запрос:** В истории диалога найди последний запрос пользователя, где были указаны параметры поиска (город, ключевые слова).
2.  **Используй контекст:** Если текущий запрос — это продолжение ("дай еще", "следующие"), ты ОБЯЗАН использовать город и ключевые слова из найденного базового запроса.
3.  **Страницы (Pagination) и Quantity:** Если текущий запрос является продолжением (например, "дай еще", "next"), **найди в истории последний объект с ролью "assistant", который имеет поле `parsed_intent`. Из этого `parsed_intent` возьми `quantity` и увеличь `page_number` на 1.** Для первого или нового поиска `page_number` всегда 1, а `quantity` извлекается из текущего запроса пользователя или по умолчанию 10.

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
"""

class GeminiService:
    def __init__(self):
        self.settings = get_settings()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in the environment variables.")
        self.gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.gemini_api_key}"

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
        """Main logic for handling a conversation turn using Gemini."""
        print(f"🔄 [SERVICE] Handling turn with Gemini for: {user_input[:100]}...")
        
        # Добавляем сообщение пользователя в историю ДО того, как передать ее Gemini для парсинга
        history.append({"role": "user", "content": user_input})
        
        parsed_intent = await self._parse_user_intent_with_gemini(history)

        intent = parsed_intent.get("intent")
        location = parsed_intent.get("location")
        activity_keywords = parsed_intent.get("activity_keywords")
        page = parsed_intent.get("page_number", 1)
        search_limit = parsed_intent.get("quantity", 10) # Это значение теперь должно приходить из Gemini корректно
        offset = (page - 1) * search_limit
        final_message = parsed_intent.get("preliminary_response", "Обрабатываю ваш запрос...")
        companies_data = []

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
                final_message = self._generate_summary_response(history, companies_data)
            else:
                # Если компаний не найдено для текущего офсета
                final_message = f"Я искал компании в {location} по вашему запросу, но не смог найти больше результатов на странице {page}. Попробуйте изменить критерии поиска."
                if page > 1: # Если пользователь уже делал пагинацию, подскажем, что результаты могли закончиться
                    final_message += " Возможно, вы уже просмотрели все доступные компании по этим критериям."
        
        elif intent == "find_companies" and not location:
            final_message = "Чтобы найти компании, мне нужно знать, в каком городе вы хотите искать. Пожалуйста, укажите местоположение."
        else:
            # Для intent 'general_question' или 'unclear' preliminary_response уже установлен.
            pass # Нет специфичной логики поиска компаний

        # <--- ГЛАВНОЕ ИЗМЕНЕНИЕ ЗДЕСЬ --->
        # Сохраняем спарсенный интент вместе с ответом ассистента в истории
        # Это позволит Gemini в следующем запросе прочитать предыдущие параметры, такие как quantity.
        assistant_response_for_history = {
            "role": "assistant",
            "content": final_message,
            "metadata": {"companies": companies_data}, # Оставьте это для ваших нужд, если есть
            "parsed_intent": parsed_intent # <-- Вот что важно добавить!
        }
        history.append(assistant_response_for_history)

        return {
            'message': final_message,
            'companies': companies_data,
            'updated_history': history,
            'reasoning': parsed_intent.get('reasoning'),
            'metadata': {"companies": companies_data}
        }

# Global service instance
ai_service = GeminiService()