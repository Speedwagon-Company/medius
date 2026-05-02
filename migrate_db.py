import sqlite3

DB_PATH = "bot.db"
TABLE_NAME = "transactions"

COLUMNS_TO_ADD = [
    ("reciever_wallet", "VARCHAR"),
    ("sender_wallet", "VARCHAR"),
    ("recieved", "FLOAT"),
    ("network", "VARCHAR"),
]


def migrate() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        for column_name, column_type in COLUMNS_TO_ADD:
            try:
                cursor.execute(
                    f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column_name} {column_type}"
                )
                print(f"Added column: {column_name} ({column_type})")
            except sqlite3.OperationalError as err:
                print(f"Skipped column {column_name}: {err}")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
