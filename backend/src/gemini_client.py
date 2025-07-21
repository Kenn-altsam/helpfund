import google.generativeai as genai
from dotenv import load_dotenv
import os
import traceback

load_dotenv()

# Initialize Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY не найден в переменных окружения")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini API настроен успешно")

# Use different model for better performance
model = genai.GenerativeModel("gemini-1.5-flash")

def get_gemini_response(prompt: str) -> str:
    """
    Get response from Gemini AI with improved error handling
    """
    if not GEMINI_API_KEY:
        print("❌ Gemini API key not configured")
        return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Gemini API key not configured", "preliminary_response": "Извините, сервис временно недоступен."}'
    
    try:
        print(f"🤖 [GEMINI] Sending request to Gemini API (prompt: {len(prompt)} chars)")
        
        # Configure generation settings for better reliability
        generation_config = genai.types.GenerationConfig(
            temperature=0.1,
            top_p=0.8,
            top_k=40,
            max_output_tokens=2048,
        )
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        )
        
        # Check if response was blocked
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            print(f"⚠️ Gemini blocked response: {response.prompt_feedback.block_reason}")
            return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Response blocked by safety filters", "preliminary_response": "Извините, не могу обработать этот запрос."}'
        
        response_text = response.text
        
        # Проверяем, что ответ не пустой
        if not response_text or not response_text.strip():
            print("⚠️ Gemini вернул пустой ответ")
            return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Empty response from Gemini", "preliminary_response": "Извините, я не смог обработать ваш запрос."}'
        
        print(f"✅ [GEMINI] Successfully received response ({len(response_text)} chars)")
        return response_text
        
    except genai.types.BlockedPromptException as e:
        print(f"❌ Gemini blocked prompt: {e}")
        return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Prompt blocked by safety filters", "preliminary_response": "Извините, не могу обработать этот запрос."}'
    
    except genai.types.StopCandidateException as e:
        print(f"❌ Gemini stopped generation: {e}")
        return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Generation stopped by safety filters", "preliminary_response": "Извините, не смог завершить обработку запроса."}'
    
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        print(f"📋 Error details:")
        traceback.print_exc()
        
        # Check for specific error types
        error_str = str(e).lower()
        if "quota" in error_str or "limit" in error_str:
            return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "API quota exceeded", "preliminary_response": "Сервис временно перегружен. Попробуйте позже."}'
        elif "authentication" in error_str or "api_key" in error_str:
            return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Authentication error", "preliminary_response": "Проблема с аутентификацией сервиса."}'
        elif "network" in error_str or "connection" in error_str:
            return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Network connection error", "preliminary_response": "Проблема с подключением к сервису."}'
        else:
            # Generic fallback
            return '{"intent": "unclear", "location": null, "activity_keywords": null, "quantity": null, "page_number": 1, "reasoning": "Gemini failed to respond", "preliminary_response": "Извините, я не смог обработать ваш запрос."}' 