import json
from functools import lru_cache
from typing import Optional

# Import the specific client and errors for robustness
from openai import OpenAI, APIConnectionError, AuthenticationError, RateLimitError

from ..core.config import get_settings
from ..core.translation_service import CityTranslationService

# Use a global variable for a singleton client, initialized as None
_client: Optional[OpenAI] = None

# A constant for the prompt makes it easier to manage
LOCATION_EXTRACTION_PROMPT = """
You are an expert in Kazakh geography. Your task is to extract ONE canonical city or region name from the user's text.
- If the city is in Latin (e.g., Almaty, Astana), convert it to Cyrillic (Алматы, Астана).
- If multiple cities are mentioned, return only the most prominent one.
- If no recognizable city is found, return the word "null".
- For oblast names, always return the full canonical form with "область" ending in "-ая область" (e.g., "Улытауская область", "Алматинская область").
- Special oblast mappings:
  * "Жетысу" or "Жетысуской" → "Жетисуская область"
  * "Актобе" or "Актобеской" → "Актюбинская область" 
  * "Атырау" or "Атырауской" → "Атырауская область"
  * "Караганда" or "Карагандинской" → "Карагандинская область"
- Respond with ONLY the city name or region name(область) or "null". Do not add any other text.
Example 1: "Find me IT companies in Almaty" -> "Алматы"
Example 2: "I'm looking for a sponsor" -> "null"
Example 3: "Горнодобывающие компании Шымкента" -> "Шымкент"
Example 4: "Найди компании в Улытауской области" -> "Улытауская область"
Example 5: "Компании Алматинской области" -> "Алматинская область"
Example 6: "В Актюбинской области" -> "Актюбинская область"
Example 7: "области Жетысу" -> "Жетисуская область"
Example 8: "области Актобе" -> "Актюбинская область"
Example 9: "области Атырау" -> "Атырауская область"
Example 10: "Жетысуской области" -> "Жетисуская область"
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
        
        # Apply translation service as a safety net to correct any AI output variations
        translated_location = CityTranslationService.translate_city_name(location)
        print(f"🧠 Location service: AI output '{location}' -> translated to '{translated_location}'")
        
        return translated_location

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