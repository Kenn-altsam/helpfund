#!/usr/bin/env python3
"""
Тестовый скрипт для проверки fallback механизма поиска благотворительности
"""

import asyncio
import sys
import os

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ai_conversation.charity_fallback import charity_fallback

async def test_charity_fallback():
    """Тестирует fallback механизм поиска благотворительности"""
    
    test_companies = [
        "ТЕЛЕРАДИОКОРПОРАЦИЯ КАЗАХСТАН",
        "КАЗАХТЕЛЕКОМ", 
        "КАЗМУНАЙГАЗ",
        "НЕИЗВЕСТНАЯ КОМПАНИЯ"  # Для тестирования случая без данных
    ]
    
    print("🔍 ТЕСТИРОВАНИЕ FALLBACK МЕХАНИЗМА ПОИСКА БЛАГОТВОРИТЕЛЬНОСТИ")
    print("="*70)
    
    for company_name in test_companies:
        print(f"\n📋 Тестирую компанию: {company_name}")
        print("-" * 50)
        
        # Тест 1: Локальная база данных
        print("🔍 Тест 1: Поиск в локальной базе данных")
        local_results = charity_fallback.search_local_database(company_name)
        
        if local_results:
            print(f"✅ Найдено {len(local_results)} результатов:")
            for i, result in enumerate(local_results, 1):
                print(f"  {i}. {result.title}")
                print(f"     {result.description}")
                print(f"     Источник: {result.source}")
                print(f"     Релевантность: {result.relevance_score}")
                print()
        else:
            print("❌ Результаты не найдены в локальной базе")
        
        # Тест 2: Альтернативные источники
        print("🔍 Тест 2: Поиск в альтернативных источниках")
        try:
            alternative_results = await charity_fallback.search_alternative_sources(company_name)
            
            if alternative_results:
                print(f"✅ Найдено {len(alternative_results)} результатов:")
                for i, result in enumerate(alternative_results, 1):
                    print(f"  {i}. {result.title}")
                    print(f"     {result.description}")
                    print(f"     Источник: {result.source}")
                    print(f"     Релевантность: {result.relevance_score}")
                    print()
            else:
                print("❌ Результаты не найдены в альтернативных источниках")
        except Exception as e:
            print(f"⚠️ Ошибка при поиске в альтернативных источниках: {e}")
        
        # Тест 3: Генерация сводки
        print("🔍 Тест 3: Генерация сводки")
        all_results = local_results + (alternative_results if 'alternative_results' in locals() else [])
        summary = charity_fallback.generate_summary(all_results, company_name)
        
        print("📝 Сводка:")
        print(summary)
        
        print("\n" + "="*70)

def test_charity_relevance():
    """Тестирует функцию определения релевантности"""
    
    print("\n🔍 ТЕСТИРОВАНИЕ ФУНКЦИИ РЕЛЕВАНТНОСТИ")
    print("="*50)
    
    test_texts = [
        "Компания ТРК оказывает благотворительную помощь детским домам",
        "ТРК спонсирует образовательные проекты в Казахстане",
        "Купить товары компании ТРК по низким ценам",
        "Вакансии в компании ТРК - работа для всех",
        "ТРК реализует социальные проекты и поддерживает фонды"
    ]
    
    for text in test_texts:
        is_relevant = charity_fallback._is_charity_relevant(text)
        status = "✅ РЕЛЕВАНТНО" if is_relevant else "❌ НЕ РЕЛЕВАНТНО"
        print(f"{status}: {text}")

if __name__ == "__main__":
    print("🚀 Запуск тестов fallback механизма...")
    
    # Тест релевантности
    test_charity_relevance()
    
    # Тест поиска
    asyncio.run(test_charity_fallback())
    
    print("\n✅ Тестирование завершено!") 