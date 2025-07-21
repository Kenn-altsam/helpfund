import time
import requests
import json
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def call_gemini_with_retry(payload: dict, max_attempts: int = 3, backoff: int = 2) -> dict:
    url = f"{GEMINI_BASE_URL}/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"✅ Gemini responded on attempt {attempt}")
            return response.json()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response else None
            if status == 429:
                wait = backoff ** attempt
                print(f"⚠️ Gemini 429 Too Many Requests. Retrying in {wait}s...")
                time.sleep(wait)
            elif status and 500 <= status < 600:
                wait = backoff ** attempt
                print(f"⚠️ Gemini {status} Server Error. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"❌ Gemini error: {e}")
                raise
        except Exception as e:
            print(f"❌ Unexpected Gemini error: {e}")
            raise
    raise Exception("❌ Gemini API failed after max retries.")


def get_gemini_response(prompt: str) -> str:
    """
    Использует OpenAI-совместимый Gemini API эндпоинт с retry-обёрткой
    """
    try:
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topK": 1,
                "topP": 1,
                "maxOutputTokens": 2048,
            }
        }
        data = call_gemini_with_retry(payload)
        # Извлекаем текст из ответа Gemini
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                parts = candidate["content"]["parts"]
                if len(parts) > 0 and "text" in parts[0]:
                    response_text = parts[0]["text"]
                    if not response_text or not response_text.strip():
                        print("⚠️ Gemini вернул пустой ответ")
                        raise ValueError("Empty response from Gemini")
                    return response_text
        print("⚠️ Неожиданная структура ответа Gemini")
        raise ValueError("Unexpected Gemini response structure")
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        # Возвращаем валидный JSON-заглушку при любых ошибках
        return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Gemini failed to respond", "preliminary_response": "Извините, я не смог обработать ваш запрос."}'

def create_gemini_assistant(name: str, instructions: str) -> str:
    """
    Эмулирует создание assistant_id для Gemini
    Возвращает UUID который будет использоваться как assistant_id
    """
    import uuid
    assistant_id = str(uuid.uuid4())
    print(f"🤖 [GEMINI] Created emulated assistant_id: {assistant_id}")
    return assistant_id

def create_gemini_thread() -> str:
    """
    Эмулирует создание thread_id для Gemini
    Возвращает UUID который будет использоваться как thread_id
    """
    import uuid
    thread_id = str(uuid.uuid4())
    print(f"🤖 [GEMINI] Created emulated thread_id: {thread_id}")
    return thread_id

def run_gemini_assistant(assistant_id: str, thread_id: str, user_input: str, history: Optional[list] = None) -> Dict[str, Any]:
    """
    Эмулирует запуск assistant с Gemini API
    assistant_id и thread_id - это локальные UUID для совместимости
    """
    try:
        # Формируем промпт с историей
        if history:
            context = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in history[-5:]])  # Последние 5 сообщений
            full_prompt = f"Context:\n{context}\n\nUser: {user_input}\n\nAssistant:"
        else:
            full_prompt = f"User: {user_input}\n\nAssistant:"
        
        # Вызываем Gemini API
        response_text = get_gemini_response(full_prompt)
        
        return {
            "response": response_text,
            "assistant_id": assistant_id,  # Возвращаем тот же assistant_id
            "thread_id": thread_id,       # Возвращаем тот же thread_id
            "success": True
        }
        
    except Exception as e:
        print(f"❌ Error running Gemini assistant: {e}")
        return {
            "response": "Извините, произошла ошибка при обработке вашего запроса.",
            "assistant_id": assistant_id,
            "thread_id": thread_id,
            "success": False,
            "error": str(e)
        } 