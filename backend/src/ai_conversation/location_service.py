import json
from functools import lru_cache
from typing import Optional

# Import the specific client and errors for robustness
from openai import OpenAI, APIConnectionError, AuthenticationError, RateLimitError

from ..core.config import get_settings

# Use a global variable for a singleton client, initialized as None
_client: Optional[OpenAI] = None

# A constant for the prompt makes it easier to manage
LOCATION_EXTRACTION_PROMPT = """
You are an expert in Kazakh geography. Your task is to extract ONE canonical city or region name from the user's text.

AVAILABLE REGIONS IN DATABASE (2015-2017 data):
- Алматинская область
- Атырауская область  
- Актюбинская область
- Карагандинская область
- Костанайская область
- Кызылординская область
- Мангистауская область
- Павлодарская область
- Жамбылская область
- Восточно-Казахстанская область
- Западно-Казахстанская область
- Акмолинская область
- Южно-Казахстанская область
- Абайская область
- Жетисуская область
- Северо-Казахстанская область
- Туркестанская область
- Улытауская область

MAJOR CITIES:
- Алматы (Almaty, Алмате, Алмата)
- Астана (Astana, Nur-Sultan, Нур-Султан)
- Шымкент (Shymkent, Чимкент)
- Актобе (Aktobe, Актюбинск)
- Тараз (Taraz, Джамбул)
- Павлодар (Pavlodar)
- Усть-Каменогорск (Ust-Kamenogorsk, Оскемен)
- Семей (Semey, Семипалатинск)
- Атырау (Atyrau, Гурьев)
- Костанай (Kostanay)
- Петропавл (Petropavl, Петропавловск)
- Караганда (Karaganda)
- Актау (Aktau, Шевченко)
- Кызылорда (Kyzylorda)

RULES:
- If the city is in Latin (e.g., Almaty, Astana), convert it to Cyrillic (Алматы, Астана).
- If multiple cities are mentioned, return only the most prominent one.
- If no recognizable city or region is found, return the word "null".
- For regions: convert any form to canonical form (e.g., "Улытауской области" -> "Улытауская область")
- IMPORTANT: If a region is not in the available list above, return "null" and do not guess.
- Handle common misspellings: "Алмате" -> "Алматы", "Алмата" -> "Алматы"
- Respond with ONLY the city name or region name or "null". Do not add any other text.

EXAMPLES:
Example 1: "Find me IT companies in Almaty" -> "Алматы"
Example 2: "I'm looking for a sponsor" -> "null"
Example 3: "Горнодобывающие компании Шымкента" -> "Шымкент"
Example 4: "Улытауской области" -> "null" (not in database)
Example 5: "Алматинской области" -> "Алматинская область"
Example 6: "в Атырауской области" -> "Атырауская область"
Example 7: "Карагандинская область" -> "Карагандинская область"
Example 8: "Найди компании в Алмате" -> "Алматы"
Example 9: "компании Алматы" -> "Алматы"
Example 10: "ВКО" -> "Восточно-Казахстанская область"
Example 11: "СКО" -> "Северо-Казахстанская область"
Example 12: "ЮКО" -> "Южно-Казахстанская область"
Example 13: "ЗКО" -> "Западно-Казахстанская область"
"""

# Simple fallback logic for common cities when AI is unavailable
SIMPLE_CITY_PATTERNS = {
    # Алматы variations
    "алмате": "Алматы",
    "алмата": "Алматы", 
    "алматы": "Алматы",
    "almaty": "Алматы",
    "в алмате": "Алматы",
    "в алматы": "Алматы",
    "алмате": "Алматы",
    # Астана variations
    "астана": "Астана",
    "astana": "Астана",
    "нур-султан": "Астана",
    "nur-sultan": "Астана",
    "астане": "Астана",
    "в астане": "Астана",
    # Шымкент variations
    "шымкент": "Шымкент",
    "shymkent": "Шымкент",
    "чимкент": "Шымкент",
    # Актобе variations
    "актобе": "Актобе",
    "aktobe": "Актобе",
    "актюбинск": "Актобе",
    # Тараз variations
    "тараз": "Тараз",
    "taraz": "Тараз",
    "джамбул": "Тараз",
    # Павлодар variations
    "павлодар": "Павлодар",
    "pavlodar": "Павлодар",
    # Усть-Каменогорск variations
    "усть-каменогорск": "Усть-Каменогорск",
    "ust-kamenogorsk": "Усть-Каменогорск",
    "оскемен": "Усть-Каменогорск",
    # Семей variations
    "семей": "Семей",
    "semey": "Семей",
    "семипалатинск": "Семей",
    # Атырау variations
    "атырау": "Атырау",
    "atyrau": "Атырау",
    "гурьев": "Атырау",
    # Костанай variations
    "костанай": "Костанай",
    "kostanay": "Костанай",
    # Петропавл variations
    "петропавл": "Петропавл",
    "petropavl": "Петропавл",
    "петропавловск": "Петропавл",
    # Караганда variations
    "караганда": "Караганда",
    "karaganda": "Караганда",
    # Актау variations
    "актау": "Актау",
    "aktau": "Актау",
    "шевченко": "Актау",
    # Кызылорда variations
    "кызылорда": "Кызылорда",
    "kyzylorda": "Кызылорда",
}

# Simple region patterns
SIMPLE_REGION_PATTERNS = {
    "алматинская область": "Алматинская область",
    "алматинской области": "Алматинская область",
    "атырауская область": "Атырауская область",
    "атырауской области": "Атырауская область",
    "актюбинская область": "Актюбинская область",
    "актюбинской области": "Актюбинская область",
    "карагандинская область": "Карагандинская область",
    "карагандинской области": "Карагандинская область",
    "костанайская область": "Костанайская область",
    "костанайской области": "Костанайская область",
    "кызылординская область": "Кызылординская область",
    "кызылординской области": "Кызылординская область",
    "мангистауская область": "Мангистауская область",
    "мангистауской области": "Мангистауская область",
    "павлодарская область": "Павлодарская область",
    "павлодарской области": "Павлодарская область",
    "жамбылская область": "Жамбылская область",
    "жамбылской области": "Жамбылская область",
    "восточно-казахстанская область": "Восточно-Казахстанская область",
    "восточно-казахстанской области": "Восточно-Казахстанская область",
    "западно-казахстанская область": "Западно-Казахстанская область",
    "западно-казахстанской области": "Западно-Казахстанская область",
    "акмолинская область": "Акмолинская область",
    "акмолинской области": "Акмолинская область",
    "южно-казахстанская область": "Южно-Казахстанская область",
    "южно-казахстанской области": "Южно-Казахстанская область",
    "улытауская область": "Улытауская область",
    "улытауской области": "Улытауская область",
    # Additional canonical forms
    "абайская область": "Абайская область",
    "абайской области": "Абайская область",
    "жетисуская область": "Жетисуская область",
    "жетисуской области": "Жетисуская область",
    "жетысуская область": "Жетисуская область",
    "жетысуской области": "Жетисуская область",
    # Region names without "область"
    "абай": "Абайская область",
    "жетысу": "Жетисуская область",
    "жетису": "Жетисуская область",
    "область абай": "Абайская область",
    "область жетысу": "Жетисуская область",
    "область жетису": "Жетисуская область",
    # Other regions without "область"
    "акмола": "Акмолинская область",
    "алматы": "Алматинская область",
    "атырау": "Атырауская область",
    "восточно-казахстан": "Восточно-Казахстанская область",
    "жамбыл": "Жамбылская область",
    "западно-казахстан": "Западно-Казахстанская область",
    "караганда": "Карагандинская область",
    "костанай": "Костанайская область",
    "кызылорда": "Кызылординская область",
    "мангистау": "Мангистауская область",
    "павлодар": "Павлодарская область",
    "северо-казахстан": "Северо-Казахстанская область",
    "туркестан": "Туркестанская область",
    "улытау": "Улытауская область",
    "южный казахстан": "Южно-Казахстанская область",
    "северо-казахстанская область": "Северо-Казахстанская область",
    "северо-казахстанской области": "Северо-Казахстанская область",
    "туркестанская область": "Туркестанская область",
    "туркестанской области": "Туркестанская область",
    # Обратный порядок слов для областей
    "области алматы": "Алматинская область",
    "области атырау": "Атырауская область",
    "области актобе": "Актюбинская область",
    "области караганда": "Карагандинская область",
    "области костанай": "Костанайская область",
    "области кызылорда": "Кызылординская область",
    "области мангистау": "Мангистауская область",
    "области павлодар": "Павлодарская область",
    "области жамбыл": "Жамбылская область",
    "области восточный казахстан": "Восточно-Казахстанская область",
    "области западный казахстан": "Западно-Казахстанская область",
    "области акмола": "Акмолинская область",
    "области южный казахстан": "Южно-Казахстанская область",
    "области улытау": "Улытауская область",
    # Additional region mappings
    "области абай": "Абайская область",
    "области жетысу": "Жетисуская область",
    "области жетису": "Жетисуская область",
    "области акмола": "Акмолинская область",
    "области алматы": "Алматинская область",
    "области атырау": "Атырауская область",
    "области восточно-казахстан": "Восточно-Казахстанская область",
    "области жамбыл": "Жамбылская область",
    "области западно-казахстан": "Западно-Казахстанская область",
    "области караганда": "Карагандинская область",
    "области костанай": "Костанайская область",
    "области кызылорда": "Кызылординская область",
    "области мангистау": "Мангистауская область",
    "области павлодар": "Павлодарская область",
    "области северо-казахстан": "Северо-Казахстанская область",
    "области туркестан": "Туркестанская область",
}

def extract_location_simple(text: str) -> Optional[str]:
    """
    Simple fallback function to extract location without AI
    """
    if not text:
        return None
        
    text_lower = text.lower()
    
    # Check for regions first
    for pattern, canonical in SIMPLE_REGION_PATTERNS.items():
        if pattern in text_lower:
            return canonical
    
    # Check for cities
    for pattern, canonical in SIMPLE_CITY_PATTERNS.items():
        if pattern in text_lower:
            return canonical
    
    return None

def get_client() -> OpenAI:
    """
    Safely initializes and returns a singleton OpenAI client.
    This "lazy initialization" prevents the app from crashing at startup if keys are missing.
    """
    global _client
    if _client is None:
        print("🔧 Initializing OpenAI client for location service...")
        settings = get_settings()
        
        # Explicitly check for required settings
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured for the location service.")
        
        _client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=15.0, # Add a timeout for network resilience
        )
    return _client

@lru_cache(maxsize=256) # Increased cache size
def get_canonical_location_from_text(text: str) -> Optional[str]:
    """
    Uses OpenAI to extract the canonical city name from a user's query.
    Results are cached, and specific API errors are handled gracefully.
    Falls back to simple pattern matching if AI is unavailable.
    """
    if not text.strip():
        return None

    # First try simple pattern matching as fallback
    simple_result = extract_location_simple(text)
    if simple_result:
        print(f"✅ Found location using simple pattern matching: '{simple_result}'")
        return simple_result

    try:
        # This will log only when the API is actually called (not a cache hit)
        print(f"🧠 Calling OpenAI API for location extraction: '{text[:50]}...'")
        
        settings = get_settings()
        client = get_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=[
                {"role": "system", "content": LOCATION_EXTRACTION_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.0,
            max_tokens=20
        )
        
        location = response.choices[0].message.content.strip()

        if location.lower() == "null" or not location:
            return None
        
        return location

    except (APIConnectionError, RateLimitError) as e:
        print(f"❌ OpenAI network/rate limit error in location service: {e}")
        print(f"🔄 Falling back to simple pattern matching for: '{text[:50]}...'")
        # Try simple pattern matching as fallback
        fallback_result = extract_location_simple(text)
        if fallback_result:
            print(f"✅ Fallback successful: '{fallback_result}'")
            return fallback_result
        return None # Fail gracefully on temporary issues
    except AuthenticationError as e:
        print(f"❌ OpenAI authentication error in location service. Check API Key. Error: {e}")
        print(f"🔄 Falling back to simple pattern matching for: '{text[:50]}...'")
        # Try simple pattern matching as fallback
        fallback_result = extract_location_simple(text)
        if fallback_result:
            print(f"✅ Fallback successful: '{fallback_result}'")
            return fallback_result
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred in location service: {e}")
        print(f"🔄 Falling back to simple pattern matching for: '{text[:50]}...'")
        # Try simple pattern matching as fallback
        fallback_result = extract_location_simple(text)
        if fallback_result:
            print(f"✅ Fallback successful: '{fallback_result}'")
            return fallback_result
        return None 