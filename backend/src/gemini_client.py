import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash")

def get_gemini_response(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Проверяем, что ответ не пустой
        if not response_text or not response_text.strip():
            print("⚠️ Gemini вернул пустой ответ")
            raise ValueError("Empty response from Gemini")
            
        return response_text
        
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        # Возвращаем валидный JSON-заглушку при любых ошибках
        return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Gemini failed to respond", "preliminary_response": "Извините, я не смог обработать ваш запрос."}' 