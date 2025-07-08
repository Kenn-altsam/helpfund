import os
import time
import psycopg2
import requests
from dotenv import load_dotenv

# --- НАСТРОЙКИ ---
# Загружаем переменные окружения из файла .env
load_dotenv()

# Укажите имя вашей таблицы и колонки с БИН
TABLE_NAME = "companies"  # <--- ЗАМЕНИТЕ НА ИМЯ ВАШЕЙ ТАБЛИЦЫ
BIN_COLUMN = "BIN"      # <--- ЗАМЕНИТЕ НА ИМЯ КОЛОНКИ С БИН

# Базовый URL для API
API_BASE_URL = "https://apiba.prgapp.kz/CompanyFullInfo"

# --- КОНЕЦ НАСТРОЕК ---


def get_db_connection():
    """Устанавливает соединение с базой данных PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )
        print("✅ Успешное подключение к базе данных.")
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return None

def fetch_all_bins(conn):
    """Получает все БИНы из указанной таблицы."""
    bins = []
    # Используем 'with' для автоматического закрытия курсора
    with conn.cursor() as cur:
        try:
            query = f"SELECT {BIN_COLUMN} FROM {TABLE_NAME};"
            cur.execute(query)
            # fetchall() возвращает список кортежей, например [('123',), ('456',)]
            # Мы преобразуем его в простой список ['123', '456']
            bins = [item[0] for item in cur.fetchall()]
            print(f"🔍 Найдено {len(bins)} БИНов для обработки.")
        except (psycopg2.Error, psycopg2.DatabaseError) as e:
            print(f"❌ Ошибка при получении БИНов: {e}")
    return bins

def fetch_company_data(bin_code):
    """Получает данные о компании по БИН с API."""
    params = {"id": bin_code, "lang": "ru"}
    try:
        response = requests.get(API_BASE_URL, params=params, timeout=15)
        # Проверяем на ошибки HTTP (4xx, 5xx)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        # Чаще всего 404 Not Found, если компании нет
        if e.response.status_code == 404:
            print(f"ℹ️  Компания с БИН {bin_code} не найдена на сайте. Пропускаем.")
        else:
            print(f"⚠️  Ошибка HTTP для БИН {bin_code}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Сетевая ошибка для БИН {bin_code}: {e}")
        return None

def update_taxes_in_db(conn, bin_code, taxes_to_update):
    """Обновляет данные по налогам для одного БИНа в БД."""
    if not taxes_to_update:
        print(f"ℹ️  Нет данных для обновления для БИН {bin_code}.")
        return

    # Динамически строим SET часть запроса для безопасности (защита от SQL-инъекций)
    # Пример: "tax_payment_2021" = %s, "tax_payment_2022" = %s
    set_clause = ", ".join([f"{col} = %s" for col in taxes_to_update.keys()])
    
    # Собираем полный запрос
    query = f"UPDATE {TABLE_NAME} SET {set_clause} WHERE {BIN_COLUMN} = %s;"
    
    # Значения должны быть в том же порядке, что и колонки в set_clause,
    # а в конце добавляем БИН для WHERE
    values = list(taxes_to_update.values()) + [bin_code]

    with conn.cursor() as cur:
        try:
            cur.execute(query, tuple(values))
            conn.commit() # Сохраняем изменения в БД
            print(f"✅ Успешно обновлены налоги для БИН {bin_code}.")
        except (psycopg2.Error, psycopg2.DatabaseError) as e:
            print(f"❌ Ошибка при обновлении БИН {bin_code}: {e}")
            conn.rollback() # Откатываем транзакцию в случае ошибки

def main():
    """Основная функция скрипта."""
    conn = get_db_connection()
    if not conn:
        return

    bins_to_process = fetch_all_bins(conn)
    if not bins_to_process:
        conn.close()
        return

    for bin_code in bins_to_process:
        print(f"\n--- Обработка БИН: {bin_code} ---")
        
        company_data = fetch_company_data(bin_code)
        
        if not (company_data and company_data.get("success") and "data" in company_data):
            print(f"ℹ️  Получен неверный или пустой ответ от API для БИН {bin_code}. Пропускаем.")
            continue
            
        tax_graph_data = company_data["data"].get("taxGraph")
        
        if not tax_graph_data or not isinstance(tax_graph_data, list):
            print(f"ℹ️  Отсутствует или некорректный ключ 'taxGraph' для БИН {bin_code}. Пропускаем.")
            continue

        # Преобразуем список словарей в удобный словарь {год: сумма}
        # [{'year': 2021, 'amount': 100}] -> {2021: 100}
        tax_map = {item['year']: item['amount'] for item in tax_graph_data if 'year' in item}

        taxes_to_update = {}
        # Проходим по годам, которые нас интересуют
        for year in range(2021, 2026):
            db_column = f"tax_payment_{year}"
            # .get(year) вернет None, если такой год не найден в tax_map
            amount = tax_map.get(year)
            
            if amount is not None:
                taxes_to_update[db_column] = amount

        # Обновляем данные в БД, если есть что обновлять
        update_taxes_in_db(conn, bin_code, taxes_to_update)
        
        # Добавляем небольшую задержку, чтобы не перегружать API
        time.sleep(0.5) # 0.5 секунды

    # Закрываем соединение с БД после завершения всех операций
    conn.close()
    print("\n🎉 Все БИНы обработаны. Работа завершена.")


if __name__ == "__main__":
    main()