import sqlite3
import tempfile
import unittest
from pathlib import Path

import migrate_trade_flow_guard as migration


def _create_old_transactions_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY,
                reciever_id INTEGER,
                sender_id INTEGER,
                reciever_wallet TEXT,
                sender_wallet TEXT,
                recieved FLOAT,
                hash VARCHAR,
                network VARCHAR,
                coin VARCHAR NOT NULL,
                status VARCHAR
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class TradeFlowGuardMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.original_db_path = migration.DB_PATH
        migration.DB_PATH = self.db_path

    def tearDown(self):
        migration.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_empty_db_migration_is_safe_noop(self):
        migration.migrate()
        conn = sqlite3.connect(self.db_path)
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='transactions' LIMIT 1"
            ).fetchone()
            self.assertIsNone(exists)
        finally:
            conn.close()

    def test_old_schema_is_migrated_and_idempotent(self):
        _create_old_transactions_schema(self.db_path)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO transactions(id, reciever_id, sender_id, reciever_wallet, sender_wallet, recieved, hash, network, coin, status) "
                "VALUES (1, 1, 2, 'rw', 'sw', 0.0, NULL, NULL, 'ETH', 'WAITING')"
            )
            conn.execute(
                "INSERT INTO transactions(id, reciever_id, sender_id, reciever_wallet, sender_wallet, recieved, hash, network, coin, status) "
                "VALUES (2, 1, 2, 'rw', 'sw', 0.0, NULL, NULL, 'ETH', NULL)"
            )
            conn.execute(
                "INSERT INTO transactions(id, reciever_id, sender_id, reciever_wallet, sender_wallet, recieved, hash, network, coin, status) "
                "VALUES (3, 1, 2, 'rw', 'sw', 0.0, '0xabc', NULL, 'ETH', 'DEPOSIT_SEEN')"
            )
            conn.commit()
        finally:
            conn.close()

        migration.migrate()
        migration.migrate()

        conn = sqlite3.connect(self.db_path)
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()}
            self.assertTrue({"trade_id", "channel_id", "escrow_wallet", "expected_amount"}.issubset(columns))

            statuses = conn.execute("SELECT id, status FROM transactions ORDER BY id").fetchall()
            self.assertEqual(
                statuses,
                [
                    (1, "WAITING_DEPOSIT"),
                    (2, "WAITING_DEPOSIT"),
                    (3, "DEPOSIT_SEEN"),
                ],
            )

            indexes = {row[1] for row in conn.execute("PRAGMA index_list('transactions')").fetchall()}
            self.assertIn("uq_transactions_hash", indexes)

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO transactions(reciever_id, sender_id, reciever_wallet, sender_wallet, recieved, hash, coin, status) "
                    "VALUES (1, 2, 'rw', 'sw', 0.0, '0xabc', 'ETH', 'WAITING_DEPOSIT')"
                )
                conn.commit()
        finally:
            conn.close()

    def test_latest_schema_is_safe_noop(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY,
                    trade_id INTEGER,
                    reciever_id INTEGER,
                    sender_id INTEGER,
                    channel_id INTEGER,
                    reciever_wallet TEXT NOT NULL,
                    sender_wallet TEXT NOT NULL,
                    escrow_wallet TEXT,
                    expected_amount FLOAT,
                    recieved FLOAT NOT NULL,
                    hash VARCHAR,
                    network VARCHAR,
                    coin VARCHAR NOT NULL,
                    status VARCHAR,
                    CONSTRAINT uq_transactions_hash UNIQUE (hash)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_transactions_trade_id ON transactions(trade_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_transactions_channel_id ON transactions(channel_id)"
            )
            conn.commit()
        finally:
            conn.close()

        migration.migrate()
        migration.migrate()

    def test_duplicate_legacy_hashes_fail_fast_with_actionable_error(self):
        _create_old_transactions_schema(self.db_path)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO transactions(id, reciever_id, sender_id, reciever_wallet, sender_wallet, recieved, hash, network, coin, status) "
                "VALUES (1, 1, 2, 'rw', 'sw', 0.0, '0xdup', NULL, 'ETH', 'WAITING')"
            )
            conn.execute(
                "INSERT INTO transactions(id, reciever_id, sender_id, reciever_wallet, sender_wallet, recieved, hash, network, coin, status) "
                "VALUES (2, 1, 2, 'rw', 'sw', 0.0, '0xdup', NULL, 'ETH', 'WAITING')"
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(migration.DuplicateTransactionHashError) as ctx:
            migration.migrate()
        self.assertIn("duplicate non-null hashes", str(ctx.exception).lower())
        self.assertIn("0xdup", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
