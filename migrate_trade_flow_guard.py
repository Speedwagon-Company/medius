import sqlite3

DB_PATH = "bot.db"
TABLE_NAME = "transactions"

COLUMNS_TO_ADD = [
    ("trade_id", "INTEGER"),
    ("channel_id", "INTEGER"),
    ("escrow_wallet", "VARCHAR"),
    ("expected_amount", "FLOAT"),
]


class DuplicateTransactionHashError(RuntimeError):
    pass


def _table_exists(cursor, table_name: str) -> bool:
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _existing_columns(cursor) -> set[str]:
    rows = cursor.execute(f"PRAGMA table_info({TABLE_NAME})").fetchall()
    return {row[1] for row in rows}


def _duplicate_hash_rows(cursor) -> list[tuple[str, int]]:
    rows = cursor.execute(
        f"""
        SELECT lower(trim(hash)) AS normalized_hash, COUNT(*) AS cnt
        FROM {TABLE_NAME}
        WHERE hash IS NOT NULL AND trim(hash) <> ''
        GROUP BY normalized_hash
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, normalized_hash ASC
        """
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def migrate() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        if not _table_exists(cursor, TABLE_NAME):
            print(f"Skipped migration: table '{TABLE_NAME}' does not exist")
            conn.commit()
            return

        existing_columns = _existing_columns(cursor)
        for column_name, column_type in COLUMNS_TO_ADD:
            if column_name in existing_columns:
                print(f"Skipped column {column_name}: already exists")
                continue
            cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column_name} {column_type}")
            print(f"Added column: {column_name} ({column_type})")

        cursor.execute(
            f"UPDATE {TABLE_NAME} SET status = 'WAITING_DEPOSIT' "
            "WHERE status IS NULL OR status = '' OR status = 'WAITING'"
        )

        duplicates = _duplicate_hash_rows(cursor)
        if duplicates:
            preview = ", ".join([f"{tx_hash} (x{count})" for tx_hash, count in duplicates[:10]])
            raise DuplicateTransactionHashError(
                "Cannot create unique index uq_transactions_hash: duplicate non-null hashes found in legacy data. "
                f"Duplicates: {preview}. "
                "Resolve duplicates manually (see README migration runbook), then rerun migration."
            )

        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_hash "
            f"ON {TABLE_NAME}(hash) WHERE hash IS NOT NULL"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_transactions_trade_id "
            f"ON {TABLE_NAME}(trade_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_transactions_channel_id "
            f"ON {TABLE_NAME}(channel_id)"
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
