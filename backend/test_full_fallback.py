#!/usr/bin/env python3
"""
Тест полного fallback parsing с новыми паттернами
"""

import re
import json
from typing import Optional, List, Dict, Any

def extract_location_simple(text: str) -> Optional[str]:
    """Упрощенное извлечение локации для тестирования"""
    if not text:
        return None
        
    text_lower = text.lower()
    
    # Простые паттерны для тестирования (включая новые)
    location_patterns = {
        "алмате": "Алматы",
        "алматы": "Алматы", 
        "астане": "Астана",
        "астана": "Астана",
        "улытауской области": "Улытауская область",
        "улытауская область": "Улытауская область",
        "области улытау": "Улытауская область",
        "области алматы": "Алматинская область",
        "области атырау": "Атырауская область",
        "области караганда": "Карагандинская область",
        "караганде": "Караганда",
        "караганда": "Караганда"
    }
    
    for pattern, canonical in location_patterns.items():
        if pattern in text_lower:
            return canonical
    
    return None

def parse_intent_fallback_simple(user_input: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """Упрощенный fallback parsing для тестирования"""
    print(f"🔄 [FALLBACK_PARSER] Используем fallback parsing для: {user_input}")
    
    # Извлекаем локацию
    location = extract_location_simple(user_input)
    
    # Простое извлечение количества
    quantity = 10  # по умолчанию
    quantity_patterns = [
        (r'(\d+)\s*компан', r'\1'),
        (r'найди\s*(\d+)', r'\1'),
        (r'покажи\s*(\d+)', r'\1'),
        (r'дай\s*(\d+)', r'\1'),
    ]
    
    for pattern, replacement in quantity_patterns:
        match = re.search(pattern, user_input.lower())
        if match:
            try:
                quantity = int(match.group(1))
                break
            except ValueError:
                continue
    
    # Определяем, является ли это запросом на продолжение
    continuation_keywords = [
        'еще', 'ещё', 'дальше', 'следующие', 'следующая', 'продолжи', 'продолжай',
        'more', 'next', 'continue', 'дай еще', 'дай ещё', 'покажи еще', 'покажи ещё'
    ]
    
    is_continuation = any(keyword in user_input.lower() for keyword in continuation_keywords)
    
    # Для запросов на продолжение пытаемся извлечь информацию о странице из истории
    page_number = 1
    if is_continuation and history:
        # Ищем последнее сообщение ассистента с parsed_intent
        for msg in reversed(history):
            if msg.get('role') == 'assistant' and 'parsed_intent' in msg:
                try:
                    last_intent = json.loads(msg['parsed_intent'])
                    page_number = last_intent.get('page_number', 1) + 1
                    quantity = last_intent.get('quantity', 10)
                    break
                except (json.JSONDecodeError, KeyError):
                    continue
    
    # Определяем intent
    if is_continuation and history:
        # Для запросов на продолжение пытаемся получить локацию из предыдущих сообщений
        for msg in reversed(history):
            if msg.get('role') == 'assistant' and 'parsed_intent' in msg:
                try:
                    last_intent = json.loads(msg['parsed_intent'])
                    if last_intent.get('location'):
                        location = last_intent.get('location')
                        break
                except (json.JSONDecodeError, KeyError):
                    continue
    
    intent = "find_companies" if location else "unclear"
    
    # Извлекаем ключевые слова деятельности (простой подход)
    activity_keywords = None
    
    # Общие ключевые слова бизнес-деятельности
    business_keywords = [
        'строительн', 'транспортн', 'торгов', 'производств', 'услуг', 'медицинск',
        'образовательн', 'финансов', 'банковск', 'страхов', 'нефтегазов', 'горнодобывающ',
        'сельскохозяйственн', 'пищев', 'текстильн', 'химическ', 'металлургическ',
        'электротехническ', 'информационн', 'телекоммуникационн', 'гостиничн', 'ресторанн'
    ]
    
    # Ищем ключевые слова бизнес-деятельности во вводе
    found_keywords = []
    for keyword in business_keywords:
        if keyword in user_input.lower():
            found_keywords.append(keyword)
    
    if found_keywords:
        activity_keywords = found_keywords
    
    result = {
        "intent": intent,
        "location": location,
        "activity_keywords": activity_keywords,
        "quantity": quantity,
        "page_number": page_number,
        "reasoning": f"Fallback parsing использован из-за недоступности Gemini API. Извлеченная локация: {location}, количество: {quantity}, страница: {page_number}",
        "preliminary_response": "Обрабатываю ваш запрос..." if intent == "find_companies" else "Извините, не могу понять ваш запрос. Пожалуйста, укажите город или область для поиска компаний."
    }
    
    print(f"✅ [FALLBACK_PARSER] Результат fallback parsing: {result}")
    return result

def test_full_fallback():
    """Тестируем полный fallback parsing с новыми паттернами"""
    
    test_cases = [
        "10 компаний в области Улытау",
        "Найди 5 компаний в области Алматы", 
        "Покажи компании в области Атырау",
        "Дай 15 компаний в области Караганда",
        "Найди строительные компании в области Костанай",
        "10 компаний в Улытауской области",  # для сравнения
    ]
    
    print("🧪 Тестируем полный fallback parsing с новыми паттернами...")
    print("=" * 70)
    
    for i, test_query in enumerate(test_cases, 1):
        print(f"\n📝 Тест {i}: '{test_query}'")
        
        # Тестируем извлечение локации
        location = extract_location_simple(test_query)
        print(f"📍 Локация извлечена: {location}")
        
        # Тестируем извлечение количества
        quantity_patterns = [
            (r'(\d+)\s*компан', r'\1'),
            (r'найди\s*(\d+)', r'\1'),
            (r'покажи\s*(\d+)', r'\1'),
            (r'дай\s*(\d+)', r'\1'),
        ]
        
        quantity = 10  # по умолчанию
        for pattern, replacement in quantity_patterns:
            match = re.search(pattern, test_query.lower())
            if match:
                try:
                    quantity = int(match.group(1))
                    break
                except ValueError:
                    continue
        
        print(f"🔢 Количество извлечено: {quantity}")
        
        # Тестируем полный fallback parsing
        history = [{"role": "user", "content": test_query}]
        result = parse_intent_fallback_simple(test_query, history)
        
        print(f"🎯 Intent: {result['intent']}")
        print(f"📍 Location: {result['location']}")
        print(f"🔢 Quantity: {result['quantity']}")
        print(f"📄 Page: {result['page_number']}")
        print(f"🏷️ Activity keywords: {result['activity_keywords']}")
        
        # Проверяем успешность
        if result['intent'] == 'find_companies' and result['location']:
            print("✅ УСПЕХ: Запрос должен работать корректно!")
        else:
            print("❌ ОШИБКА: Запрос не работает корректно")
        
        print("-" * 50)
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    test_full_fallback() 