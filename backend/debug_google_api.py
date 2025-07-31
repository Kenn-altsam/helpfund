#!/usr/bin/env python3
"""
Детальная диагностика Google Custom Search API
"""

import asyncio
import httpx
import json
import urllib.parse
from src.core.config import get_settings

async def debug_google_api():
    """Детальная диагностика Google Custom Search API"""
    
    settings = get_settings()
    
    print("🔍 ДЕТАЛЬНАЯ ДИАГНОСТИКА GOOGLE CUSTOM SEARCH API")
    print("="*60)
    
    print(f"📋 API Key: {'Установлен' if settings.GOOGLE_API_KEY else 'НЕ УСТАНОВЛЕН'}")
    print(f"📋 Search Engine ID: {'Установлен' if settings.GOOGLE_SEARCH_ENGINE_ID else 'НЕ УСТАНОВЛЕН'}")
    
    if not settings.GOOGLE_API_KEY or not settings.GOOGLE_SEARCH_ENGINE_ID:
        print("❌ Отсутствуют необходимые API ключи!")
        return
    
    # Тест 1: Простой запрос
    print("\n" + "="*60)
    print("ТЕСТ 1: Простой запрос")
    print("="*60)
    
    simple_query = "Казахстан"
    search_url = (
        f"https://www.googleapis.com/customsearch/v1?"
        f"key={settings.GOOGLE_API_KEY}&"
        f"cx={settings.GOOGLE_SEARCH_ENGINE_ID}&"
        f"q={urllib.parse.quote(simple_query)}&"
        f"num=1"
    )
    
    print(f"🔗 URL: {search_url}")
    
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(search_url)
            print(f"📊 Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Простой запрос работает!")
                if 'items' in data:
                    print(f"   Найдено результатов: {len(data['items'])}")
                else:
                    print("   Результаты не найдены")
            else:
                print(f"❌ Ошибка: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Детали ошибки: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"   Текст ответа: {response.text}")
                    
        except Exception as e:
            print(f"❌ Исключение: {e}")
    
    # Тест 2: Запрос с кавычками
    print("\n" + "="*60)
    print("ТЕСТ 2: Запрос с кавычками")
    print("="*60)
    
    quoted_query = '"ТЕЛЕРАДИОКОРПОРАЦИЯ КАЗАХСТАН"'
    search_url = (
        f"https://www.googleapis.com/customsearch/v1?"
        f"key={settings.GOOGLE_API_KEY}&"
        f"cx={settings.GOOGLE_SEARCH_ENGINE_ID}&"
        f"q={urllib.parse.quote(quoted_query)}&"
        f"num=1"
    )
    
    print(f"🔗 URL: {search_url}")
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(search_url)
            print(f"📊 Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Запрос с кавычками работает!")
                if 'items' in data:
                    print(f"   Найдено результатов: {len(data['items'])}")
                else:
                    print("   Результаты не найдены")
            else:
                print(f"❌ Ошибка: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Детали ошибки: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"   Текст ответа: {response.text}")
                    
        except Exception as e:
            print(f"❌ Исключение: {e}")
    
    # Тест 3: Запрос с благотворительностью
    print("\n" + "="*60)
    print("ТЕСТ 3: Запрос с благотворительностью")
    print("="*60)
    
    charity_query = '"ТЕЛЕРАДИОКОРПОРАЦИЯ КАЗАХСТАН" благотворительность'
    search_url = (
        f"https://www.googleapis.com/customsearch/v1?"
        f"key={settings.GOOGLE_API_KEY}&"
        f"cx={settings.GOOGLE_SEARCH_ENGINE_ID}&"
        f"q={urllib.parse.quote(charity_query)}&"
        f"num=1"
    )
    
    print(f"🔗 URL: {search_url}")
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(search_url)
            print(f"📊 Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Запрос с благотворительностью работает!")
                if 'items' in data:
                    print(f"   Найдено результатов: {len(data['items'])}")
                    for item in data['items']:
                        print(f"   - {item.get('title', 'Нет заголовка')}")
                else:
                    print("   Результаты не найдены")
            else:
                print(f"❌ Ошибка: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Детали ошибки: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"   Текст ответа: {response.text}")
                    
        except Exception as e:
            print(f"❌ Исключение: {e}")
    
    # Тест 4: Проверка Search Engine ID
    print("\n" + "="*60)
    print("ТЕСТ 4: Проверка Search Engine ID")
    print("="*60)
    
    print(f"🔍 Search Engine ID: {settings.GOOGLE_SEARCH_ENGINE_ID}")
    
    # Проверяем формат Search Engine ID
    if settings.GOOGLE_SEARCH_ENGINE_ID.startswith('0'):
        print("⚠️  Search Engine ID начинается с '0' - это может быть проблемой")
    elif len(settings.GOOGLE_SEARCH_ENGINE_ID) < 10:
        print("⚠️  Search Engine ID слишком короткий")
    else:
        print("✅ Формат Search Engine ID выглядит корректно")

if __name__ == "__main__":
    asyncio.run(debug_google_api()) 