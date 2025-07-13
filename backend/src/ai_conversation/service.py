"""
OpenAI service for AI conversation functionality

Handles communication with Azure OpenAI API for charity sponsorship matching.
"""

import asyncio
import json
import re
import traceback
from typing import Optional, Dict, Any, List

from openai import OpenAI
from fastapi import HTTPException
from sqlalchemy.orm import Session

# You will need to import your ConversationHistory model and the browse tool
# from where they are defined in your project.
# from ..conversations.models import ConversationHistory 
# from ..core.browser import browse # Assuming you have a browser tool

from ..core.config import get_settings
from ..companies.service import CompanyService
from .location_service import get_canonical_location_from_text

# Language detection helper (use langdetect if installed)
try:
    from langdetect import detect as _detect_lang
except ImportError:  # Fallback – default to Russian
    def _detect_lang(text: str) -> str:  # type: ignore
        return "ru"


class OpenAIService:
    """Service for handling OpenAI API interactions with database integration"""
    
    def __init__(self):
        """Initializes the service and sets up the OpenAI client."""
        self.settings = get_settings()
        
        # Use the SYNCHRONOUS OpenAI client
        self.client = OpenAI(
            api_key=self.settings.OPENAI_API_KEY,
        )

    def _parse_user_intent_with_history(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Uses OpenAI to parse the latest user message in Russian, using the full conversation history for context.
        """
        
        # --- DEBUG: Add extensive logging for pagination troubleshooting ---
        print(f"🔍 [INTENT_PARSER] Analyzing history length: {len(history)}")
        if history:
            print(f"🔍 [INTENT_PARSER] Last user message: {history[-1].get('content', 'N/A')[:100]}...")
            
            # Find the most recent search context for debugging
            user_messages = [msg for msg in history if msg.get('role') == 'user']
            print(f"🔍 [INTENT_PARSER] Total user messages in history: {len(user_messages)}")
            
            # Look for previous search requests
            search_keywords = ['найди', 'find', 'компани', 'companies', 'поиск']
            for i, msg in enumerate(reversed(user_messages)):
                content = msg.get('content', '').lower()
                if any(keyword in content for keyword in search_keywords):
                    print(f"🔍 [INTENT_PARSER] Found previous search at position -{i}: {content[:100]}...")
                    break
        
        # --- FALLBACK LOGIC: Pattern-based continuation detection ---
        fallback_result = self._detect_continuation_fallback(history)
        if fallback_result:
            print(f"🔄 [INTENT_PARSER] Fallback detection succeeded, using fallback result")
            return fallback_result
        
        # --- PROMPT FIX FOR MAXIMUM CONTEXT RELIABILITY ---
        system_prompt = """
        Ты — ИИ-ассистент для проекта 'Ayala'. Твоя задача — анализировать ПОСЛЕДНЕЕ сообщение пользователя, используя ИСТОРИЮ ДИАЛОГА как единственный источник контекста, чтобы извлечь параметры для поиска.

        Ты ДОЛЖЕН всегда отвечать ТОЛЬКО одним валидным JSON-объектом.

        **КЛЮЧЕВОЕ ПРАВИЛО: КОНТЕКСТ ИЗ ИСТОРИИ**
        Твоя главная задача — безошибочно поддерживать контекст диалога для поиска.
        1.  **Найди "базовый контекст":** В истории диалога найди **самый последний запрос от пользователя**, в котором были явно указаны параметры поиска (`location`, `activity_keywords`). Это и есть твой "базовый контекст".
        2.  **Используй "базовый контекст":** Если текущий запрос пользователя — это продолжение поиска (например, "дай еще", "следующие", "Find another 15 companies", "Give me more", "Show me more companies"), ты ОБЯЗАН использовать `location` и `activity_keywords` из "базового контекста".
            - **Критически важно:** Игнорируй любые промежуточные сообщения ассистента (например, о неудаче поиска или с предложением сменить город). Контекст для продолжения поиска всегда берется из последнего релевантного *запроса пользователя*.
        3.  **Определи количество:** Если в текущем запросе указано новое количество ("дай еще 20", "another 15"), используй его. Если количество не указано, возьми его из "базового контекста" или используй 10 по умолчанию.
        4.  **Увеличь страницу:** Для каждого запроса-продолжения ("дай еще", "следующие", "more", "another") **увеличивай `page_number` на 1**. Для первого (или нового) поиска `page_number` всегда 1.

        **ПРАВИЛО ЛОКАЛИЗАЦИИ:**
        - Если город указан латиницей (Almaty, Astana), переведи его на русский (Алматы, Астана).

        **КЛЮЧЕВЫЕ СЛОВА ПРОДОЛЖЕНИЯ:**
        Распознавай эти фразы как запросы на продолжение поиска:
        - Русские: "дай еще", "покажи еще", "найди еще", "еще X компаний", "следующие", "больше", "дополнительно", "продолжи"
        - Английские: "give me more", "show me more", "another", "next", "additional", "find more"

        Структура JSON:
        {
          "intent": "string",
          "location": "string | null",
          "activity_keywords": ["string"] | null,
          "quantity": "number | null",
          "page_number": "number",
          "reasoning": "string",
          "preliminary_response": "string"
        }

        Описание полей:
        - "intent": "find_companies", "general_question", "unclear".
        - "location": Город НА РУССКОМ. Если в текущем запросе его нет, **ОБЯЗАТЕЛЬНО БЕРИ ИЗ ИСТОРИИ**. Если в истории нет — null.
        - "activity_keywords": Ключевые слова. Если в текущем запросе их нет, **ОБЯЗАТЕЛЬНО БЕРИ ИЗ ИСТОРИИ**. Если в истории нет — null.
        - "quantity": Число компаний. Это КРИТИЧЕСКИ ВАЖНОЕ поле. Ты ОБЯЗАН извлечь точное число из запроса пользователя (например, из "найди 30 компаний" извлеки 30). Если число не указано ЯВНО, используй 10. Не придумывай число, если его нет.
        - "page_number": Номер страницы. Увеличивай на 1 для запросов-продолжений.
        - "reasoning": Твое пошаговое объяснение логики.
        - "preliminary_response": Ответ-заглушка для пользователя.

        --- ПРИМЕРЫ (ПОКАЗЫВАЮТ ТОЛЬКО ФОРМАТ) ---

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
          "reasoning": "Это первый запрос. Пользователь указал город 'Almaty', я перевел его в 'Алматы'. Количество 15, страница 1.",
          "preliminary_response": "Отлично! Ищу для вас 15 IT-компаний в Алматы. Один момент..."
        }

        Пример 2: Последующий запрос (самый важный пример!)
        История: [
          {"role": "user", "content": "Найди 15 IT компаний в Almaty"},
          {"role": "assistant", "content": "Отличные новости! Я нашел информацию о 15 компаниях..."}
        ]
        Пользователь: "Give me another 15 companies"
        Ожидаемый JSON:
        {
          "intent": "find_companies",
          "location": "Алматы", 
          "activity_keywords": ["IT"],
          "quantity": 15,
          "page_number": 2,
          "reasoning": "Пользователь просит 'another 15 companies'. Я проанализировал историю и нашел предыдущий поиск 'Найди 15 IT компаний в Almaty'. Я ОБЯЗАН использовать `location` ('Алматы') и `activity_keywords` (['IT']) из этого поиска. Количество '15' взято из текущего запроса. Я увеличил номер страницы до 2, так как это продолжение.",
          "preliminary_response": "Конечно! Ищу следующую группу из 15 IT-компаний в Алматы. Подождите, пожалуйста."
        }
        """
        # --- PROMPT FIX ENDS HERE ---
        
        messages_with_context = [{"role": "system", "content": system_prompt}] + history

        try:
            print(f"🤖 [INTENT_PARSER] Calling OpenAI with {len(messages_with_context)} messages...")
            
            response = self.client.chat.completions.create(
                model=self.settings.OPENAI_MODEL_NAME, # Use the standard model name
                messages=messages_with_context,
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # --- DEBUG: Log the parsed result ---
            print(f"✅ [INTENT_PARSER] OpenAI response:")
            print(f"   Intent: {result.get('intent')}")
            print(f"   Location: {result.get('location')}")
            print(f"   Activity Keywords: {result.get('activity_keywords')}")
            print(f"   Quantity: {result.get('quantity')}")
            print(f"   Page Number: {result.get('page_number')}")
            print(f"   Reasoning: {result.get('reasoning', '')[:100]}...")
            
            return result
            
        except Exception as e:
            # Enhanced error logging
            print(f"❌ Error during OpenAI intent parsing: {e}")
            print(f"🔍 History length: {len(history)}")
            print(f"🔍 Last user message: {history[-1].get('content', 'N/A') if history else 'No history'}")
            traceback.print_exc()
            
            # Try fallback again if OpenAI fails completely
            print(f"🔄 [INTENT_PARSER] Trying fallback detection after OpenAI failure...")
            fallback_after_error = self._detect_continuation_fallback(history)
            if fallback_after_error:
                print(f"✅ [INTENT_PARSER] Fallback succeeded after OpenAI error")
                return fallback_after_error
            
            return {
                "intent": "unclear", 
                "location": None,
                "activity_keywords": None,
                "quantity": None,
                "page_number": 1,
                "reasoning": f"Не удалось корректно обработать запрос пользователя из-за внутренней ошибки: {str(e)}",
                "preliminary_response": "Извините, у меня возникла проблема с пониманием вашего запроса. Пожалуйста, перефразируйте."
            }

    def _detect_continuation_fallback(self, history: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """
        Fallback method to detect continuation requests using pattern matching.
        This runs when OpenAI parsing might fail or return ambiguous results.
        """
        if not history or len(history) < 2:
            return None
            
        current_message = history[-1].get('content', '').lower().strip()
        print(f"🔄 [FALLBACK] Analyzing current message: {current_message}")
        
        # Continuation patterns
        continuation_patterns = [
            # English patterns
            r'\b(give\s+me\s+)?(more|another)\b',
            r'\b(show\s+me\s+)?(more|additional)\b',
            r'\bnext\s+\d+\b',
            r'\banother\s+\d+\b',
            # Russian patterns - improved to be more flexible
            r'\b(ещё|еще)\s+\d+\b',  # "еще 15" - more flexible
            r'\b(дай|покажи|найди)\s+.*(ещё|еще)\b',  # "найди мне еще" - includes найди
            r'\bследующие\s+\d+\b',
            r'\bболь?ше\s+компани',
            r'\bдополнительн\b',
            r'\bпродолжи\b',  # "продолжи"
            r'\bеще\s+\d+\s+компани\b'  # "еще 15 компаний"
        ]
        
        is_continuation = any(re.search(pattern, current_message) for pattern in continuation_patterns)
        
        if not is_continuation:
            print(f"🔄 [FALLBACK] Not a continuation request")
            return None
            
        print(f"🔄 [FALLBACK] Detected continuation request")
        
        # Extract quantity from current message
        quantity_match = re.search(r'\b(\d+)\b', current_message)
        quantity = int(quantity_match.group(1)) if quantity_match else 10
        
        # Find the most recent search context from user messages
        user_messages = [msg for msg in history if msg.get('role') == 'user']
        
        location = None
        activity_keywords = None
        previous_quantity = 10
        
        # Look for previous search parameters in reverse order
        for msg in reversed(user_messages[:-1]):  # Exclude current message
            content = msg.get('content', '').lower()
            
            # Look for location mentions
            if not location:
                # Common city names
                city_patterns = [
                    (r'\balmaty\b', 'Алматы'),
                    (r'\bалматы\b', 'Алматы'),
                    (r'\bastana\b', 'Астана'),
                    (r'\bастана\b', 'Астана'),
                    (r'\baktau\b', 'Актау'),
                    (r'\bактау\b', 'Актау'),
                    (r'\baktobe\b', 'Актобе'),
                    (r'\bактобе\b', 'Актобе')
                ]
                
                for pattern, city in city_patterns:
                    if re.search(pattern, content):
                        location = city
                        break
            
            # Look for activity keywords
            if not activity_keywords and any(kw in content for kw in ['компани', 'companies', 'найди', 'find']):
                # Extract potential activity keywords
                activity_patterns = [
                    r'\bit\s+компани', r'\bit\s+companies',
                    r'\bтехнолог', r'\btechnology',
                    r'\bстроитель', r'\bconstruction',
                    r'\bторгов', r'\btrade'
                ]
                
                for pattern in activity_patterns:
                    if re.search(pattern, content):
                        if 'it' in pattern:
                            activity_keywords = ['IT']
                        elif 'технолог' in pattern:
                            activity_keywords = ['технологии']
                        elif 'строитель' in pattern:
                            activity_keywords = ['строительство']
                        elif 'торгов' in pattern:
                            activity_keywords = ['торговля']
                        break
            
            # Look for previous quantity
            prev_quantity_match = re.search(r'\b(\d+)\b', content)
            if prev_quantity_match:
                previous_quantity = int(prev_quantity_match.group(1))
            
            # If we found location and search intent, we have enough context
            if location and any(kw in content for kw in ['компани', 'companies', 'найди', 'find']):
                break
        
        if not location:
            print(f"🔄 [FALLBACK] No location found in history")
            return None
            
        # Count previous continuation requests to determine page number
        page_number = 2  # Start at page 2 for first continuation
        continuation_count = 0
        
        for msg in user_messages[:-1]:
            content = msg.get('content', '').lower()
            if any(re.search(pattern, content) for pattern in continuation_patterns):
                continuation_count += 1
                
        page_number = 2 + continuation_count
        
        print(f"🔄 [FALLBACK] Detected context:")
        print(f"   location: {location}")
        print(f"   activity_keywords: {activity_keywords}")
        print(f"   quantity: {quantity}")
        print(f"   page_number: {page_number}")
        
        return {
            "intent": "find_companies",
            "location": location,
            "activity_keywords": activity_keywords,
            "quantity": quantity,
            "page_number": page_number,
            "reasoning": f"Fallback detection: Found continuation request with location={location}, quantity={quantity}, page={page_number}",
            "preliminary_response": f"Конечно! Ищу следующую группу из {quantity} компаний в {location}. Подождите, пожалуйста."
        }

    def _enrich_companies_with_web_search(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enriches company data with information from web searches (website, contacts, tax info).
        """
        # This function can remain synchronous if the 'browse' tool is synchronous
        # If browse is async, this would need to be an async function with asyncio.gather
        # For now, assuming a synchronous web search for simplicity
        
        def search_for_company(company: Dict[str, Any]):
            query = f"Найди сайт и дополнительную информацию о компании '{company['name']}' (БИН: {company['bin']}) в Казахстане."
            try:
                # Assuming 'browse' is a synchronous function you have defined elsewhere
                # search_result = browse(query, search_engine="google") 
                # For demonstration, we'll just mock a result
                search_result = f"Mock search result for {company['name']}"
                company["web_search_summary"] = search_result
            except Exception as e:
                company["web_search_summary"] = f"Не удалось выполнить веб-поиск: {e}"
            return company

        enriched_companies = [search_for_company(c) for c in companies]
        return enriched_companies

    @staticmethod
    def _get_message_language(history: List[Dict[str, str]]) -> str:
        """Detect the language of the last user message (returns 'en', 'ru', 'kk')."""
        for msg in reversed(history):
            if msg.get("role") == "user":
                try:
                    lang = _detect_lang(msg.get("content", ""))
                    return lang.lower()  # langdetect returns e.g., 'en', 'ru', 'kk'
                except Exception:
                    return "ru" # Default
        return "ru"

    def _generate_summary_response(self, history: List[Dict[str, str]], companies_data: List[Dict[str, Any]]) -> str:
        """Craft a summary response in the same language the user spoke."""

        user_lang = self._get_message_language(history)

        # Helper text selection
        def t(ru: str, en: str, kk: str) -> str:
            if user_lang.startswith("en"):
                return en
            if user_lang.startswith("kk"):
                return kk
            return ru  # default Russian

        if not companies_data:
            return t(
                ru="К сожалению, по вашему запросу не найдено подходящих компаний. Попробуйте изменить критерии поиска.",
                en="Unfortunately, no matching companies were found for your request. Please try different criteria.",
                kk="Өкінішке орай, сіздің сұранысыңыз бойынша сәйкес компаниялар табылмады. Басқа сүзгілерді қолданып көріңіз."
            )

        parts: list[str] = []

        count = len(companies_data)
        # Opening sentence
        if user_lang.startswith("en"):
            opening = f"Great news! I found information on {count} compan{'y' if count==1 else 'ies'}:"
        elif user_lang.startswith("kk"):
            opening = f"Тамаша жаңалық! Мен {count} компания туралы ақпарат таптым:"
        else:  # Russian
            if count == 1:
                opening = f"Отличные новости! Я нашел информацию о {count} компании:"
            elif 2 <= count <= 4:
                opening = f"Отличные новости! Я нашел информацию о {count} компаниях:"
            else:
                opening = f"Отличные новости! Я нашел информацию о {count} компаниях:"

        parts.append(opening)
        parts.append("")

        # Loop companies
        for comp in companies_data:
            name = comp.get("name", "Unknown company")
            bin_num = comp.get("bin", "N/A")
            activity = comp.get("activity", t("Деятельность не указана", "Activity not specified", "Қызметі көрсетілмеген"))
            size = comp.get("size") or t("Размер не указан", "Size not specified", "Өлшемі көрсетілмеген")

            if user_lang.startswith("en"):
                entry = (
                    f"• **{name}**\n"
                    f"  - BIN: {bin_num}\n"
                    f"  - Activity: {activity}\n"
                    f"  - Size: {size}"
                )
            elif user_lang.startswith("kk"):
                entry = (
                    f"• **{name}**\n"
                    f"  - БСН: {bin_num}\n"
                    f"  - Қызметі: {activity}\n"
                    f"  - Өлшемі: {size}"
                )
            else:  # Russian
                entry = (
                    f"• **{name}**\n"
                    f"  - БИН: {bin_num}\n"
                    f"  - Деятельность: {activity}\n"
                    f"  - Размер: {size}"
                )

            locality = comp.get("locality") or comp.get("city")
            if locality:
                if user_lang.startswith("en"):
                    entry += f"\n  - Location: {locality}"
                elif user_lang.startswith("kk"):
                    entry += f"\n  - Орналасқан жері: {locality}"
                else:
                    entry += f"\n  - Местоположение: {locality}"

            annual_tax = comp.get("annual_tax_paid")
            if annual_tax is not None:
                if user_lang.startswith("en"):
                    entry += f"\n  - Taxes paid (last year): {annual_tax:,.0f} ₸"
                elif user_lang.startswith("kk"):
                    entry += f"\n  - Төленген салық (соңғы жыл): {annual_tax:,.0f} ₸"
                else:
                    entry += f"\n  - Уплачено налогов (последний год): {annual_tax:,.0f} ₸"

            parts.append(entry)

        parts.append("")

        closing = t(
            ru="Потрясающая работа! У вас есть большой выбор для потенциального сотрудничества. Если есть что-то еще, чем я могу помочь, дайте знать!",
            en="Excellent! You now have a great list of potential partners. Let me know if there's anything else I can help with!",
            kk="Тамаша! Ықтимал серіктестердің жақсы тізімі бар. Тағы көмек керек болса, айтыңыз!"
        )
        parts.append(closing)

        return "\n".join(parts)


    def handle_conversation_turn(
        self,
        user_input: str,
        history: List[Dict[str, str]],
        db: Session,
        conversation_id: Optional[str] = None # Added for persistence
    ) -> Dict[str, Any]:
        """
        Main logic for handling a single turn in a conversation.
        - Parses intent
        - Searches database
        - Formulates a response
        """
        print(f"🔄 [SERVICE] Handling conversation turn for user input: {user_input[:100]}...")

        # Initialize default response values
        companies_data = []
        final_message = "Обрабатываю ваш запрос..."

        try:
            # 1. Get canonical location
            canonical_location = get_canonical_location_from_text(user_input)

            # 2. Append user message to history *before* parsing intent
            history.append({"role": "user", "content": user_input})

            # 3. Parse intent from the full history
            parsed_intent = self._parse_user_intent_with_history(history)
            
            # 4. Override location if canonical version was found
            if canonical_location:
                print(f"📍 [SERVICE] Overriding intent location with canonical name: '{canonical_location}'")
                parsed_intent['location'] = canonical_location
            
            intent = parsed_intent.get("intent")
            location = parsed_intent.get("location")
            activity_keywords = parsed_intent.get("activity_keywords")
            page = parsed_intent.get("page_number", 1)
            
            print(f"🎯 Intent parsed: {intent}, location: {location}, keywords: {activity_keywords}")
            
            # Calculate search parameters
            raw_quantity_from_ai = parsed_intent.get("quantity")
            default_limit = 10
            max_limit = 200

            # --- >>> START OF IMPROVED QUANTITY BLOCK <<< ---
            final_quantity = None

            # 1) Try to use the value provided by the model
            if raw_quantity_from_ai is not None:
                try:
                    final_quantity = int(raw_quantity_from_ai)
                except (ValueError, TypeError):
                    pass  # We'll try other heuristics below

            # 2) If the model didn't give us a useful number (None or default 10),
            #    attempt to extract a number directly from the user's last message.
            if final_quantity is None or final_quantity == default_limit:
                print("🤔 AI returned default/no quantity. Checking user_input for a number...")
                user_text = history[-1].get("content", "")
                match = re.search(r'\b(\d{1,3})\b', user_text)  # look for 1-3 digit number
                if match:
                    try:
                        num_from_text = int(match.group(1))
                        if num_from_text > 0:
                            print(f"✅ Found quantity '{num_from_text}' directly in user text. Using it.")
                            final_quantity = num_from_text
                    except (ValueError, TypeError):
                        pass

            # 3) Fallback to default if still unresolved
            if final_quantity is None:
                final_quantity = default_limit

            # Apply global limits
            search_limit = min(final_quantity, max_limit)
            # --- >>> END OF IMPROVED QUANTITY BLOCK <<< ---

            offset = (page - 1) * search_limit
            print(f"📊 Final search params: limit={search_limit}, offset={offset}, page={page}")

            # --- DEBUG: Add detailed pagination debugging ---
            print("🔢 [PAGINATION] Detailed calculation:")
            print(f"   Raw quantity from OpenAI: {raw_quantity_from_ai}")
            print(f"   Final quantity selected: {final_quantity}")
            print(f"   Page number from OpenAI: {page}")
            print(f"   Calculated offset: {offset} = ({page} - 1) * {search_limit}")
            print(f"   Final query will be: LIMIT {search_limit} OFFSET {offset}")
            
            final_message = parsed_intent.get("preliminary_response", "Обрабатываю ваш запрос...")

            # 3. If intent is to find companies, fetch data from DB
            if intent == "find_companies" and location:
                print(f"🏢 Searching for companies in {location}...")
                print(f"🔍 [DATABASE] Query parameters:")
                print(f"   location: {location}")
                print(f"   activity_keywords: {activity_keywords}")
                print(f"   limit: {search_limit}")
                print(f"   offset: {offset}")
                
                company_service = CompanyService(db)
                db_companies = company_service.search_companies(
                    location=location,
                    activity_keywords=activity_keywords,
                    limit=search_limit,
                    offset=offset
                )
                
                print(f"📈 Found {len(db_companies) if db_companies else 0} companies in database")
                print(f"🔍 [DATABASE] Query returned {len(db_companies) if db_companies else 0} results")
                
                # --- DEBUG: Log first few company names for verification ---
                if db_companies:
                    print(f"🏢 [DATABASE] First few companies returned:")
                    for i, company in enumerate(db_companies[:3]):
                        print(f"   {i+1}. {company.get('name', 'N/A')} (ID: {company.get('id', 'N/A')[:8]}...)")
                    if len(db_companies) > 3:
                        print(f"   ... and {len(db_companies) - 3} more companies")
                else:
                    print(f"⚠️ [DATABASE] No companies returned - this might indicate:")
                    print(f"   - End of results reached (no more companies match criteria)")
                    print(f"   - Query parameters don't match any records")
                    print(f"   - Database connectivity issue")
                
                if db_companies:
                    # 4. Enrich DB data with web search results
                    print("🌐 Enriching companies with web search...")
                    enriched_companies = self._enrich_companies_with_web_search(db_companies)
                    companies_data = enriched_companies
                    
                    # 5. Generate a final summary response with all data
                    print("✍️ Generating summary response...")
                    final_message = self._generate_summary_response(history, companies_data)
                else:
                    final_message = f"Я искал компании в {location}, но не смог найти больше результатов, соответствующих вашему запросу. Может, попробуем другой город или изменим ключевые слова?"
            
            elif intent == "find_companies" and not location:
                final_message = "Чтобы найти компании, мне нужно знать, в каком городе или регионе вы хотите искать. Пожалуйста, укажите местоположение."

        except Exception as e:
            print(f"❌ Critical error during conversation processing: {e}")
            # Roll back in case the session is in a failed state so that outer callers can continue safely
            try:
                if db:
                    db.rollback()
            except Exception as rollback_error:
                print(f"⚠️ Could not rollback session after critical error: {rollback_error}")
            traceback.print_exc()
            final_message = "Извините, произошла техническая ошибка. Попробуйте переформулировать ваш вопрос."

        # CRITICAL: Always append the final AI response to history
        history.append({"role": "assistant", "content": final_message})
        print(f"✅ Added AI response, final history length: {len(history)}")

        # 7. Save updated history to the database (if implementation exists)
        # if conversation_id and db: ...

        # 8. Prepare the final response object
        companies_found_count = len(companies_data)
        has_more = companies_found_count >= search_limit
        
        return {
            'message': final_message,
            'companies': companies_data,
            'updated_history': history,
            'intent': parsed_intent.get("intent") if 'parsed_intent' in locals() else 'unclear',
            'location_detected': parsed_intent.get("location") if 'parsed_intent' in locals() else None,
            'activity_keywords_detected': parsed_intent.get("activity_keywords") if 'parsed_intent' in locals() else None,
            'quantity_detected': parsed_intent.get("quantity") if 'parsed_intent' in locals() else None,
            'page_number': parsed_intent.get("page_number", 1) if 'parsed_intent' in locals() else 1,
            'companies_found': companies_found_count,
            'has_more_companies': has_more,
            'reasoning': parsed_intent.get('reasoning') if 'parsed_intent' in locals() else None,
            # 'conversation_id': conversation_id
        }

    def handle_conversation_with_assistant_fallback(
        self,
        user_input: str,
        history: List[Dict[str, str]],
        db: Session,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle conversation with assistant fallback.
        If the assistant fails, fallback to the traditional OpenAI service.
        This provides the best of both worlds - enhanced context with reliability.
        """
        try:
            # First, try using the enhanced assistant
            print("🤖 [SERVICE] Attempting to use enhanced assistant...")
            from .assistant_creator import handle_conversation_with_context
            
            # TODO: This call has incorrect arguments. `handle_conversation_with_context` expects a `user` object.
            response_data = handle_conversation_with_context(
                user_input=user_input,
                conversation_history=history,
                db=db
            )
            
            print("✅ [SERVICE] Enhanced assistant succeeded")
            return response_data
            
        except Exception as assistant_error:
            print(f"⚠️ [SERVICE] Enhanced assistant failed: {str(assistant_error)}")
            print("🔄 [SERVICE] Falling back to traditional OpenAI service...")
            
            try:
                # Fallback to traditional service
                response_data = self.handle_conversation_turn(
                    user_input=user_input,
                    history=history,
                    db=db,
                    conversation_id=conversation_id
                )
                
                # Add a note about fallback
                original_message = response_data.get('message', '')
                response_data['message'] = f"{original_message}\n\n(Обработано с использованием базового сервиса)"
                
                print("✅ [SERVICE] Traditional service fallback succeeded")
                return response_data
                
            except Exception as fallback_error:
                print(f"❌ [SERVICE] Both assistant and traditional service failed")
                print(f"   Assistant error: {str(assistant_error)}")
                print(f"   Fallback error: {str(fallback_error)}")
                
                # Last resort: preserve history and return error
                error_history = history.copy()
                error_history.append({"role": "user", "content": user_input})
                error_history.append({
                    "role": "assistant", 
                    "content": "Извините, произошла техническая ошибка в обеих системах. Ваша история разговора сохранена. Попробуйте переформулировать запрос."
                })
                
                return {
                    'message': "Извините, произошла техническая ошибка в обеих системах. Ваша история разговора сохранена. Попробуйте переформулировать запрос.",
                    'companies': [],
                    'updated_history': error_history,
                    'intent': "error",
                    'location_detected': None,
                    'activity_keywords': None,
                    'quantity_requested': None,
                    'companies_found': 0,
                    'has_more_companies': False,
                    'reasoning': f"Both systems failed. Assistant: {str(assistant_error)}, Fallback: {str(fallback_error)}"
                }


# Global service instance
ai_service = OpenAIService()