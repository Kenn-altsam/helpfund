
import json
from functools import lru_cache
from typing import Optional
import google.generativeai as genai

from ..core.config import get_settings

# A constant for the prompt makes it easier to manage
LOCATION_EXTRACTION_PROMPT = """
You are an expert in Kazakh geography. Your task is to extract ONE canonical city or region name from the user's text.
- If the city is in Latin (e.g., Almaty, Astana), convert it to Cyrillic (Алматы, Астана).
- If multiple cities are mentioned, return only the most prominent one.
- If no recognizable city is found, return the word "null".
- Respond with ONLY the city name or "null". Do not add any other text.
Example 1: "Find me IT companies in Almaty" -> "Алматы"
Example 2: "I'm looking for a sponsor" -> "null"
Example 3: "Горнодобывающие компании Шымкента" -> "Шымкент"
"""

@lru_cache(maxsize=256)
def get_canonical_location_from_text(text: str) -> Optional[str]:
    """
    Uses Gemini to extract the canonical city name from a user's query.
    Results are cached, and specific API errors are handled gracefully.
    """
    if not text.strip():
        return None

    try:
        settings = get_settings()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL_NAME)

        # This will log only when the API is actually called (not a cache hit)
        print(f"🧠 Calling Gemini API for location extraction: '{text[:50]}...'")
        
        full_prompt = f"{LOCATION_EXTRACTION_PROMPT}\n\nUser text: \"{text}\""
        response = model.generate_content(full_prompt)
        
        location = response.text.strip()

        if location.lower() == "null" or not location:
            return None
        
        return location

    except Exception as e:
        print(f"❌ An unexpected error occurred in location service: {e}")
        return None 