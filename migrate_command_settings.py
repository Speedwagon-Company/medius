import sqlite3

DB_PATH = "bot.db"
TABLE_NAME = "command_settings"
INDEX_NAME = "ix_command_settings_guild_id"


def migrate() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                command_name VARCHAR(100) NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                extra_settings JSON NOT NULL DEFAULT '{}',
                CONSTRAINT uq_command_settings_guild_command UNIQUE (guild_id, command_name)
            )
            """
        )
        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {INDEX_NAME}
            ON {TABLE_NAME} (guild_id)
            """
        )
        conn.commit()
        print("command_settings table is ready")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
