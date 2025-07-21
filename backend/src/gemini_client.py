import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

def get_gemini_response(
    prompt: str = None,
    assistant_id: str = None,
    thread_id: str = None,
    user_input: str = None,
    history: list = None
) -> dict:
    try:
        # Логируем входные параметры
        print("\n[Gemini] --- Входные параметры ---")
        print(f"prompt: {prompt}")
        print(f"assistant_id: {assistant_id}")
        print(f"thread_id: {thread_id}")
        print(f"user_input: {user_input}")
        print(f"history: {history}")
        print("[Gemini] ------------------------\n")

        # Собираем финальный текст запроса (если явно не указан prompt)
        if not prompt and user_input:
            # Преобразуем историю в текст
            history_text = ""
            if history:
                for turn in history:
                    history_text += f"{turn['role'].capitalize()}: {turn['content']}\n"
            prompt = f"{history_text}User: {user_input}"

        print(f"[Gemini] Итоговый prompt:\n{prompt}\n")

        response = model.generate_content(prompt)
        response_text = response.text.strip() if response.text else ""

        print(f"[Gemini] Сырой ответ Gemini:\n{response_text}\n")

        if not response_text:
            print("⚠️ Gemini вернул пустой ответ")
            raise ValueError("Empty response from Gemini")

        print("[Gemini] Успешно получен ответ от Gemini!")
        return {
            "success": True,
            "response": response_text
        }

    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return {
            "success": False,
            "response": "Извините, я не смог обработать ваш запрос.",
            "error": str(e)
        } 