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
- If the city is in Latin (e.g., Almaty, Astana), convert it to Cyrillic (Алматы, Астана).
- If multiple cities are mentioned, return only the most prominent one.
- If no recognizable city is found, return the word "null".
- For oblast names, always return the full canonical form with "область" (e.g., "Улытауская область", "Алматинская область").
- Handle various forms of oblast names: "Жетысу" -> "Жетисуская область", "Улытау" -> "Улытауская область"
- Handle "области [город]" pattern: "области Жетысу" -> "Жетисуская область", "области Актобе" -> "Актюбинская область", "области Атырау" -> "Атырауская область"
- Handle all Kazakh regions: Алматинская, Актюбинская, Атырауская, Карагандинская, Костанайская, Кызылординская, Мангистауская, Павлодарская, Акмолинская, Жамбылская, Жетисуская, Улытауская, Восточно-Казахстанская, Западно-Казахстанская, Северо-Казахстанская, Южно-Казахстанская области
- Respond with ONLY the city name or region name(область) or "null". Do not add any other text.

Examples:
"Find me IT companies in Almaty" -> "Алматы"
"I'm looking for a sponsor" -> "null"
"Горнодобывающие компании Шымкента" -> "Шымкент"
"Найди компании в Улытауской области" -> "Улытауская область"
"Компании Алматинской области" -> "Алматинская область"
"В Актюбинской области" -> "Актюбинская область"
"Найди компании в Жетысуской области" -> "Жетисуская область"
"10 крупных компаний области Жетысу" -> "Жетисуская область"
"области Жетысу" -> "Жетисуская область"
"области Актобе" -> "Актюбинская область"
"области Атырау" -> "Атырауская область"
"области Караганда" -> "Карагандинская область"
"области Костанай" -> "Костанайская область"
"области Кызылорда" -> "Кызылординская область"
"области Мангистау" -> "Мангистауская область"
"области Павлодар" -> "Павлодарская область"
"области Акмола" -> "Акмолинская область"
"области Жамбыл" -> "Жамбылская область"
"области Улытау" -> "Улытауская область"
"Компании Улытау" -> "Улытауская область"
"В Алматинской области" -> "Алматинская область"
"область Жетысу" -> "Жетисуская область"
"Жетысуская область" -> "Жетисуская область"
"Улытауская область" -> "Улытауская область"
"Алматинская область" -> "Алматинская область"
"Актюбинская область" -> "Актюбинская область"
"Атырауская область" -> "Атырауская область"
"Карагандинская область" -> "Карагандинская область"
"Костанайская область" -> "Костанайская область"
"Кызылординская область" -> "Кызылординская область"
"Мангистауская область" -> "Мангистауская область"
"Павлодарская область" -> "Павлодарская область"
"Акмолинская область" -> "Акмолинская область"
"Жамбылская область" -> "Жамбылская область"

"Жетысуской область" -> "Жетисуская область"
"Улытауской область" -> "Улытауская область"
"Алматинской область" -> "Алматинская область"
"Актюбинской область" -> "Актюбинская область"
"Атырауской область" -> "Атырауская область"
"Карагандинской область" -> "Карагандинская область"
"Костанайской область" -> "Костанайская область"
"Кызылординской область" -> "Кызылординская область"
"Мангистауской область" -> "Мангистауская область"
"Павлодарской область" -> "Павлодарская область"
"Акмолинской область" -> "Акмолинская область"
"Жамбылской область" -> "Жамбылская область"
"""

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
    """
    if not text.strip():
        return None

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
        return None # Fail gracefully on temporary issues
    except AuthenticationError as e:
        print(f"❌ OpenAI authentication error in location service. Check API Key. Error: {e}")
        # This is a critical configuration error, re-raising might be appropriate
        # so developers see it immediately. For now, we fail gracefully.
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred in location service: {e}")
        # Optionally log the full traceback for debugging
        # import traceback
        # traceback.print_exc()
        return None 