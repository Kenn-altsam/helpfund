# backend/src/ai_conversation/location_service.py

import openai
import json
import os

# Make sure your OpenAI client is configured.
# It automatically reads the OPENAI_API_KEY from your environment variables.
client = openai.AsyncOpenAI()

async def get_canonical_location_from_text(user_input: str) -> str | None:
    """
    Uses an AI model to extract a canonical city name from user text.

    Args:
        user_input: The raw text from the user (e.g., "найди мне 15 компаний в Алмате").

    Returns:
        The standardized city name (e.g., "Алматы") or None if no city is found.
    """
    system_prompt = """
    You are a highly specialized linguistic tool. Your single task is to analyze user text and extract the main city name mentioned.
    You must return the city name in its canonical, nominative case (именительный падеж).
    - If the user says "в Алмате", you return "Алматы".
    - If the user says "из Астаны", you return "Астана".
    - If the user says "компании Шымкента", you return "Шымкент".
    - If no Kazakhstani city is found, you must return null.
    Your response MUST be a valid JSON object with a single key: "city".
    Example of a successful response: {"city": "Алматы"}
    Example of a failed response: {"city": null}
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",  # Fast and cost-effective
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.0,  # We want deterministic, not creative, output
            response_format={"type": "json_object"}  # Enforces JSON output
        )

        result_text = response.choices[0].message.content
        result_json = json.loads(result_text)
        city = result_json.get("city")

        if city:
            print(f"🤖 AI successfully identified city: '{city}'")
            return city
        else:
            print(f"🤖 AI did not find a city in the user input.")
            return None

    except Exception as e:
        print(f"❌ An error occurred while calling the AI for location extraction: {e}")
        return None 