#!/usr/bin/env python3
"""
Улучшенный тестовый скрипт для поиска конкретной благотворительной деятельности
"""

import asyncio
import httpx
import urllib.parse

# Реальные ключи из вашего .env файла
GOOGLE_API_KEY = "AIzaSyDaosLf3VqRE_wsoqL3aTCI03SgdMYBnqQ"
GOOGLE_SEARCH_ENGINE_ID = "d68dd1921d0c745aa"

async def test_improved_charity_search():
    """Тестирует улучшенные запросы для поиска конкретной благотворительной деятельности"""
    
    print("🔍 УЛУЧШЕННЫЙ ПОИСК БЛАГОТВОРИТЕЛЬНОЙ ДЕЯТЕЛЬНОСТИ")
    print("="*70)
    
    company_name = "ТЕЛЕРАДИОКОРПОРАЦИЯ КАЗАХСТАН"
    
    # Улучшенные запросы для поиска конкретной благотворительной деятельности
    improved_queries = [
        # Запрос 1: Конкретные благотворительные действия
        f'"{company_name}" ("детский дом" OR "интернат" OR "малообеспеченные семьи" OR "тяжелобольные дети" OR "инвалиды" OR "благотворительные акции")',
        
        # Запрос 2: Благотворительные термины с действиями
        f'"{company_name}" ("оказывает помощь" OR "организует праздники" OR "дарит подарки" OR "сбор средств" OR "благотворительные концерты" OR "материальная помощь")',
        
        # Запрос 3: Социальная ответственность и фонды
        f'"{company_name}" ("благотворительный фонд" OR "социальная ответственность" OR "КСО" OR "благотворительность" OR "спонсирует" OR "финансирует" OR "поддерживает")',
        
        # Запрос 4: Специфичные благотворительные проекты
        f'"{company_name}" ("помощь нуждающимся" OR "социальные проекты" OR "благотворительные программы" OR "поддержка детей" OR "помощь семьям")',
        
        # Запрос 5: Конкретные действия благотворительности
        f'"{company_name}" ("праздники для детей" OR "подарки детским домам" OR "лечение детей" OR "помощь инвалидам" OR "благотворительные мероприятия")'
    ]
    
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for i, query in enumerate(improved_queries, 1):
            print(f"\n🔍 Улучшенный запрос {i}: {query}")
            print("-" * 60)
            
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
                    
                    if 'items' in data:
                        print(f"✅ Найдено результатов: {len(data['items'])}")
                        
                        # Фильтруем результаты на релевантность
                        relevant_results = []
                        exclude_keywords = [
                            'госзаказ', 'тендер', 'закупки', 'goszakup', 'tender', 'procurement',
                            'филиал', 'областной', 'региональный', 'кадровые изменения', 
                            'назначение', 'увольнение', 'директор', 'руководитель'
                        ]
                        
                        for item in data['items']:
                            title = item.get('title', '').lower()
                            snippet = item.get('snippet', '').lower()
                            full_text = f"{title} {snippet}"
                            
                            # Проверяем на исключающие слова
                            has_exclude = any(exclude in full_text for exclude in exclude_keywords)
                            
                            if not has_exclude:
                                relevant_results.append(item)
                                print(f"  ✅ РЕЛЕВАНТНО: {item.get('title', 'Нет заголовка')}")
                                print(f"     {item.get('snippet', 'Нет описания')[:150]}...")
                                print(f"     {item.get('link', 'Нет ссылки')}")
                                print()
                            else:
                                print(f"  ❌ ОТФИЛЬТРОВАНО: {item.get('title', 'Нет заголовка')}")
                        
                        if not relevant_results:
                            print("  ⚠️ Все результаты отфильтрованы как нерелевантные")
                    else:
                        print("❌ Результаты не найдены")
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
            if i < len(improved_queries):
                await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(test_improved_charity_search()) 