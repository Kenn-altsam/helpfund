#!/usr/bin/env python3
"""
Тест для проверки парсинга различных вариантов написания областей
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.translation_service import CityTranslationService

def test_location_translations():
    """Тестируем различные варианты написания областей"""
    
    test_cases = [
        # Новые области
        ("5 крупных компаний Улытауской области", "Улытауская область"),
        ("10 крупных компаний области Абай", "Абайская область"),
        ("10 крупных компаний области Жетысу", "Жетисуская область"),
        ("10 крупных компаний Жетысуской области", "Жетисуская область"),
        ("10 крупных компаний Жетисуской области", "Жетисуская область"),
        
        # Старые области
        ("5 компаний Алматинской области", "Алматинская область"),
        ("10 компаний области Алматы", "Алматинская область"),
        ("15 компаний Актюбинской области", "Актюбинская область"),
        ("20 компаний области Актобе", "Актюбинская область"),
        
        # Английские варианты
        ("5 companies in Ulytau region", "Улытауская область"),
        ("10 companies in Abay oblast", "Абайская область"),
        ("15 companies in Jetysu region", "Жетисуская область"),
    ]
    
    print("🧪 Тестирование парсинга локаций...")
    print("=" * 60)
    
    for i, (input_text, expected) in enumerate(test_cases, 1):
        # Извлекаем локацию из текста (упрощенная логика)
        words = input_text.lower().split()
        location_found = None
        
        # Ищем ключевые слова локации
        for j, word in enumerate(words):
            if word in ["области", "область", "region", "oblast"]:
                if j + 1 < len(words):
                    location_found = f"{words[j]} {words[j+1]}"
                break
            elif word in ["улытауской", "улытауская", "ulytau"]:
                location_found = "улытауская область"
                break
            elif word in ["абайской", "абайская", "abay"]:
                location_found = "абайская область"
                break
            elif word in ["жетысуской", "жетысуская", "жетисуской", "жетисуская", "jetysu"]:
                location_found = "жетисуская область"
                break
            elif word in ["алматинской", "алматинская", "almaty"]:
                location_found = "алматинская область"
                break
            elif word in ["актюбинской", "актюбинская", "aktobe"]:
                location_found = "актюбинская область"
                break
        
        # Переводим найденную локацию
        if location_found:
            translated = CityTranslationService.translate_city_name(location_found)
        else:
            translated = "не найдено"
        
        status = "✅" if translated == expected else "❌"
        print(f"{status} Тест {i}: '{input_text}' -> '{translated}' (ожидалось: '{expected}')")
    
    print("=" * 60)
    print("Тест завершен!")

if __name__ == "__main__":
    test_location_translations() 