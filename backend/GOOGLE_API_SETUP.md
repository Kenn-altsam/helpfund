# Настройка Google API для поиска благотворительности

## Проблема
Сервис поиска благотворительности компаний не работает из-за неправильно настроенных Google API ключей.

## Диагностика
При тестировании обнаружено:
- API ключи загружаются как placeholder значения: `your_google_api_key_for_custom_search`
- Google Custom Search API возвращает ошибку 400: "API key not valid"
- Search Engine ID также не настроен правильно

## Решение

### 1. Получение Google API Key

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите **Custom Search API**:
   - Перейдите в "APIs & Services" > "Library"
   - Найдите "Custom Search API"
   - Нажмите "Enable"
4. Создайте API ключ:
   - Перейдите в "APIs & Services" > "Credentials"
   - Нажмите "Create Credentials" > "API Key"
   - Скопируйте созданный ключ

### 2. Создание Custom Search Engine

1. Перейдите на [Google Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Нажмите "Create a search engine"
3. В поле "Sites to search" введите: `www.google.com`
4. Назовите поисковую машину (например, "Charity Search")
5. Нажмите "Create"
6. Перейдите в настройки поисковой машины
7. Включите "Search the entire web"
8. Скопируйте **Search Engine ID** (cx)

### 3. Обновление .env файла

На сервере обновите файл `.env` в корне проекта:

```bash
# Замените placeholder значения на реальные
GOOGLE_API_KEY="AIzaSyC..."  # Ваш реальный Google API ключ
GOOGLE_SEARCH_ENGINE_ID="012345678901234567890:abcdefghijk"  # Ваш реальный Search Engine ID
```

### 4. Проверка настройки

После обновления .env файла запустите тест:

```bash
cd backend
python3 debug_google_api.py
```

Должны увидеть:
- ✅ Простой запрос работает!
- ✅ Запрос с кавычками работает!
- ✅ Запрос с благотворительностью работает!

### 5. Тестирование поиска благотворительности

Для компании "ТЕЛЕРАДИОКОРПОРАЦИЯ КАЗАХСТАН" должны найтись результаты, включая:
- Благотворительные проекты
- Социальную ответственность
- Спонсорские программы

## Альтернативное решение

Если Google API недоступен, можно реализовать fallback механизм:

1. Использовать другие поисковые API (Bing, DuckDuckGo)
2. Создать локальную базу данных благотворительных проектов
3. Использовать веб-скрапинг (с соблюдением robots.txt)

## Мониторинг

После настройки следите за:
- Лимитами API (100 запросов/день бесплатно)
- Качеством результатов поиска
- Скоростью ответов API 