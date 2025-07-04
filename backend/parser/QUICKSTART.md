# KGD Tax Parser - Быстрый старт

## 🚀 Установка и запуск за 3 шага

### Шаг 1: Установите зависимости
```bash
pip install -r requirements.txt
playwright install chromium
```

### Шаг 2: Быстрый тест
```bash
# Вариант 1: Запуск из корня проекта
python run_kgd_parser.py

# Вариант 2: Запуск из папки parser
cd parser/
python quick_start.py
```

### Шаг 3: Импорт в базу данных
```bash
python parser/kgd_data_importer.py
```

## 📁 Что происходит?

1. **Парсер** открывает браузер и ищет компании на сайте КГД по БИН
2. **Извлекает** налоговые данные за 2020-2025 годы из таблицы
3. **Сохраняет** результаты в CSV файлы в папке `parser/kgd_data/`
4. **Импортер** загружает данные в PostgreSQL базу в таблицу `companies`

## 📊 Результаты

После парсинга вы получите:

- `company_tax_data.csv` - успешно извлеченные налоговые данные
- `failed_searches.csv` - компании, которые не удалось найти
- `search_log.csv` - подробный лог всех поисков

## ⚙️ Настройки CAPTCHA

### Автоматическое решение (рекомендуется)
1. Зарегистрируйтесь на [2captcha.com](https://2captcha.com)
2. Добавьте API ключ в переменную окружения:
```bash
export CAPTCHA_API_KEY="ваш_ключ_2captcha"
```
3. Измените метод в коде:
```python
parser = KGDTaxParser(captcha_method="2captcha")
```

### Ручное решение (по умолчанию)
- Парсер остановится при появлении CAPTCHA
- Решите капчу вручную в браузере
- Нажмите Enter в терминале для продолжения

## 🔧 Настройка базы данных

Убедитесь, что PostgreSQL настроен:
```bash
# Проверить подключение
python parser/kgd_data_importer.py --test

# Показать статистику
python parser/kgd_data_importer.py --stats
```

## ❗ Важные примечания

- **Задержки**: Используйте задержки 3-5 секунд между запросами
- **Ограничения**: Не парсите больше 50-100 компаний за раз
- **Время работы**: Сайт КГД может блокировать при частых запросах
- **CAPTCHA**: Появляется случайно, будьте готовы решать

## 🏃‍♂️ Быстрые команды

```bash
# Парсинг компаний для теста (из корня проекта)
python run_kgd_parser.py

# Или из папки parser/
cd parser/
python quick_start.py

# Полный тест всех функций
cd parser/
python test_kgd_parser.py

# Импорт существующих данных
cd parser/
python kgd_data_importer.py

# Проверка статистики БД
cd parser/
python kgd_data_importer.py --stats
```

## 📖 Подробная документация

Полное руководство: [README.md](README.md) 