#!/usr/bin/env python3
"""
Прямая проверка Google API с реальными ключами
"""

import asyncio
import httpx
import urllib.parse

# Реальные ключи из вашего .env файла
GOOGLE_API_KEY = "AIzaSyDaosLf3VqRE_wsoqL3aTCI03SgdMYBnqQ"
GOOGLE_SEARCH_ENGINE_ID = "d68dd1921d0c745aa"

async def test_google_api_direct():
    """Прямая проверка Google API с реальными ключами"""
    
    print("🔍 ПРЯМАЯ ПРОВЕРКА GOOGLE API С РЕАЛЬНЫМИ КЛЮЧАМИ")
    print("="*60)
    
    company_name = "ТЕЛЕРАДИОКОРПОРАЦИЯ КАЗАХСТАН"
    
    # Тестовые запросы
    test_queries = [
        f'"{company_name}" благотворительность',
        f'"{company_name}" социальная ответственность',
        f'"{company_name}" фонд помощь',
        f'"{company_name}" спонсирует',
        f'"{company_name}" пожертвования'
    ]
    
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for i, query in enumerate(test_queries, 1):
            print(f"\n🔍 Запрос {i}: {query}")
            
            search_url = (
                f"https://www.googleapis.com/customsearch/v1?"
                f"key={GOOGLE_API_KEY}&"
                f"cx={GOOGLE_SEARCH_ENGINE_ID}&"
                f"q={urllib.parse.quote(query)}&"
                f"num=5&"
                f"lr=lang_ru&"
                f"gl=kz"
            )
            
            try:
                response = await client.get(search_url)
                print(f"📊 Статус: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print("✅ Google API работает!")
                    
                    if 'items' in data:
                        print(f"   Найдено результатов: {len(data['items'])}")
                        for j, item in enumerate(data['items'], 1):
                            title = item.get('title', 'Нет заголовка')
                            snippet = item.get('snippet', 'Нет описания')
                            link = item.get('link', 'Нет ссылки')
                            
                            print(f"  {j}. {title}")
                            print(f"     {snippet[:100]}...")
                            print(f"     {link}")
                            print()
                    else:
                        print("   Результаты не найдены")
                        if 'error' in data:
                            print(f"   Ошибка API: {data['error']}")
                else:
                    print(f"❌ Ошибка: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"   Детали ошибки: {error_data}")
                    except:
                        print(f"   Текст ответа: {response.text}")
                
            except Exception as e:
                print(f"❌ Исключение: {e}")
            
            # Задержка между запросами
            if i < len(test_queries):
                await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test_google_api_direct()) 