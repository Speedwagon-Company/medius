# src/migrate.py
import sqlite3
from pathlib import Path

# Путь к файлу БД (настройте под свой проект)
DB_PATH = "bot.db"  # или Path(__file__).parent / "bot.db"
TABLE_NAME = "config"

# Определяем столбцы для таблицы
COLUMNS = [
    ("id", "INTEGER PRIMARY KEY"),
    ("embed_suc_color", "VARCHAR NOT NULL"),
]


def migrate() -> None:
    """Создаёт таблицу config если она не существует"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        
        # Проверяем существует ли таблица
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE_NAME,)
        )
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Создаём таблицу
            columns_def = ", ".join([f"{col_name} {col_type}" for col_name, col_type in COLUMNS])
            create_query = f"CREATE TABLE {TABLE_NAME} ({columns_def})"
            cursor.execute(create_query)
            print(f"Created table: {TABLE_NAME}")
            
            # Добавляем запись по умолчанию
            cursor.execute(
                f"INSERT INTO {TABLE_NAME} (id, embed_suc_color) VALUES (1, ?)",
                ("#00ff00",)
            )
            print(f"Added default config: embed_suc_color=#00ff00")
        else:
            # Проверяем и добавляем отсутствующие колонки (на случай обновлений)
            cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            for column_name, column_type in COLUMNS:
                # Пропускаем id, так как он уже есть
                if column_name == "id":
                    continue
                    
                if column_name not in existing_columns:
                    try:
                        cursor.execute(
                            f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column_name} {column_type}"
                        )
                        print(f"Added column: {column_name} ({column_type})")
                    except sqlite3.OperationalError as err:
                        print(f"Skipped column {column_name}: {err}")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()