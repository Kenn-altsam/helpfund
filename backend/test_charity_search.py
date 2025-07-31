#!/usr/bin/env python3
"""
Тестовый скрипт для проверки поиска благотворительности компании
"""

import asyncio
import httpx
import json
from src.core.config import get_settings

async def test_charity_search():
    """Тестирует поиск благотворительности для компании ТЕЛЕРАДИОКОРПОРАЦИЯ КАЗАХСТАН"""
    
    settings = get_settings()
    company_name = "ТЕЛЕРАДИОКОРПОРАЦИЯ КАЗАХСТАН"
    
    print(f"🔍 Тестирую поиск благотворительности для: {company_name}")
    print(f"📋 API ключи настроены: Google API - {'Да' if settings.GOOGLE_API_KEY else 'Нет'}")
    print(f"📋 Search Engine ID: {'Да' if settings.GOOGLE_SEARCH_ENGINE_ID else 'Нет'}")
    
    # Тест 1: Прямой запрос к Google Custom Search API
    print("\n" + "="*60)
    print("ТЕСТ 1: Прямой запрос к Google Custom Search API")
    print("="*60)
    
    # Очищаем название компании
    clean_company_name = company_name.replace('"', '').replace('«', '').replace('»', '').strip()
    
    # Создаем тестовые запросы
    test_queries = [
        f'"{clean_company_name}" благотворительность',
        f'"{clean_company_name}" социальная ответственность',
        f'"{clean_company_name}" фонд помощь',
        f'"{clean_company_name}" спонсирует',
        f'"{clean_company_name}" пожертвования'
    ]
    
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for i, query in enumerate(test_queries, 1):
            print(f"\n🔍 Запрос {i}: {query}")
            
            search_url = (
                f"https://www.googleapis.com/customsearch/v1?"
                f"key={settings.GOOGLE_API_KEY}&"
                f"cx={settings.GOOGLE_SEARCH_ENGINE_ID}&"
                f"q={query}&"
                f"num=5&"
                f"lr=lang_ru&"
                f"gl=kz"
            )
            
            try:
                response = await client.get(search_url)
                response.raise_for_status()
                data = response.json()
                
                if 'items' in data:
                    print(f"✅ Найдено результатов: {len(data['items'])}")
                    for j, item in enumerate(data['items'], 1):
                        title = item.get('title', 'Нет заголовка')
                        snippet = item.get('snippet', 'Нет описания')
                        link = item.get('link', 'Нет ссылки')
                        
                        print(f"  {j}. {title}")
                        print(f"     {snippet[:100]}...")
                        print(f"     {link}")
                        print()
                else:
                    print("❌ Результаты не найдены")
                    if 'error' in data:
                        print(f"   Ошибка API: {data['error']}")
                
            except httpx.HTTPStatusError as e:
                print(f"❌ HTTP ошибка: {e.response.status_code}")
                if e.response.status_code == 429:
                    print("   Превышен лимит запросов")
                elif e.response.status_code == 403:
                    print("   Ошибка авторизации API")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
            
            # Задержка между запросами
            if i < len(test_queries):
                await asyncio.sleep(1)
    
    # Тест 2: Проверка через роутер (если сервер запущен)
    print("\n" + "="*60)
    print("ТЕСТ 2: Проверка через API роутер")
    print("="*60)
    
    # Проверяем, запущен ли сервер
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/docs")
            if response.status_code == 200:
                print("✅ Сервер запущен на localhost:8000")
                print("ℹ️  Для тестирования API используйте:")
                print("   curl -X POST http://localhost:8000/api/v1/ai/charity-research \\")
                print("     -H 'Content-Type: application/json' \\")
                print("     -H 'Authorization: Bearer YOUR_TOKEN' \\")
                print(f"     -d '{{\"company_name\": \"{company_name}\"}}'")
            else:
                print("❌ Сервер не отвечает на localhost:8000")
    except Exception as e:
        print(f"❌ Не удалось подключиться к серверу: {e}")
        print("ℹ️  Запустите сервер командой: python run.py")

if __name__ == "__main__":
    asyncio.run(test_charity_search()) 