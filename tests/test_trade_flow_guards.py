import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cogs.trade import TradeCog
from utils import crypto


class CryptoDepositMatchingTests(unittest.IsolatedAsyncioTestCase):
    async def test_wait_for_transaction_matches_by_from_to_and_value(self):
        crypto.TRANSACTIONS.clear()

        sender = "0xaabbccdd00000000000000000000000000000001"
        escrow = "0x676320a4f2ccd0d6a8a56c0ebf2af1aa984a12fd"
        another_escrow = "0x676320a4f2ccd0d6a8a56c0ebf2af1aa984a12000"
        min_value = 10

        tx_a = {"from": sender, "to": escrow, "value": 20, "hash": "0xaaa"}
        tx_b = {"from": sender, "to": another_escrow, "value": 20, "hash": "0xbbb"}
        crypto.TRANSACTIONS["0xaaa"] = tx_a
        crypto.TRANSACTIONS["0xbbb"] = tx_b

        matched = await asyncio.wait_for(
            crypto.wait_for_transaction(sender_wallet=sender, recipient_wallet=escrow, min_value_wei=min_value),
            timeout=1,
        )
        self.assertEqual(matched["hash"], "0xaaa")
        self.assertIn("0xbbb", crypto.TRANSACTIONS)

    async def test_same_cached_tx_is_consumed_once(self):
        crypto.TRANSACTIONS.clear()
        sender = "0xaabbccdd00000000000000000000000000000001"
        escrow = "0x676320a4f2ccd0d6a8a56c0ebf2af1aa984a12fd"
        tx = {"from": sender, "to": escrow, "value": 20, "hash": "0xonly"}
        crypto.TRANSACTIONS["0xonly"] = tx

        first = await asyncio.wait_for(
            crypto.wait_for_transaction(sender_wallet=sender, recipient_wallet=escrow, min_value_wei=1),
            timeout=1,
        )
        self.assertEqual(first["hash"], "0xonly")

        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(
                crypto.wait_for_transaction(sender_wallet=sender, recipient_wallet=escrow, min_value_wei=1),
                timeout=0.2,
            )


class ReleaseGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_release_before_ready_is_rejected(self):
        cog = TradeCog(bot=SimpleNamespace())
        chan = SimpleNamespace(send=AsyncMock())

        with patch("cogs.trade.try_update_transaction_status", new=AsyncMock(return_value=False)), patch(
            "cogs.trade.crypto.sign_and_send", new=AsyncMock()
        ) as sign_and_send:
            await cog.handle_confirm_money(1, 0.1, "0xreceiver", chan)

        sign_and_send.assert_not_called()

    async def test_release_double_call_sends_once(self):
        cog = TradeCog(bot=SimpleNamespace())
        msg = SimpleNamespace(edit=AsyncMock())
        chan = SimpleNamespace(send=AsyncMock(return_value=msg))

        class DummyTxHash:
            def hex(self):
                return "0xabc"

        w3 = SimpleNamespace(
            eth=SimpleNamespace(
                wait_for_transaction_receipt=AsyncMock(return_value={"status": 1}),
            )
        )

        with patch("cogs.trade.crypto.W3", w3), patch(
            "cogs.trade.try_update_transaction_status",
            new=AsyncMock(side_effect=[True, True, False]),
        ) as transition, patch(
            "cogs.trade.crypto.sign_and_send",
            new=AsyncMock(return_value=DummyTxHash()),
        ) as sign_and_send:
            await cog.handle_confirm_money(1, 0.1, "0xreceiver", chan)
            await cog.handle_confirm_money(1, 0.1, "0xreceiver", chan)

        sign_and_send.assert_awaited_once()
        self.assertEqual(transition.await_count, 3)


class WatcherLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_watcher_avoids_duplicates(self):
        cog = TradeCog(bot=SimpleNamespace())

        class FakeTask:
            def __init__(self):
                self._callbacks = []

            def done(self):
                return False

            def add_done_callback(self, cb):
                self._callbacks.append(cb)

            def cancel(self):
                return None

        fake_task = FakeTask()
        def _fake_create_task(coro):
            coro.close()
            return fake_task

        with patch("cogs.trade.asyncio.create_task", side_effect=_fake_create_task) as create_task:
            cog._schedule_deposit_watcher(42)
            cog._schedule_deposit_watcher(42)

        self.assertEqual(create_task.call_count, 1)


class ReleasingRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_cog_load_moves_releasing_to_manual_reconciliation_without_resend(self):
        transaction = SimpleNamespace(id=7, channel_id=777)
        channel = SimpleNamespace(send=AsyncMock(), guild=SimpleNamespace())
        bot = SimpleNamespace(get_channel=lambda _channel_id: None, fetch_channel=AsyncMock())
        cog = TradeCog(bot=bot)

        with patch(
            "cogs.trade.list_transactions_by_statuses",
            new=AsyncMock(side_effect=[[transaction], []]),
        ), patch(
            "cogs.trade.try_update_transaction_status",
            new=AsyncMock(return_value=True),
        ) as transition, patch(
            "cogs.trade.send_transaction_log",
            new=AsyncMock(),
        ) as send_log, patch(
            "cogs.trade.TradeCog._resolve_text_channel",
            new=AsyncMock(return_value=channel),
        ), patch(
            "cogs.trade.crypto.sign_and_send",
            new=AsyncMock(),
        ) as sign_and_send:
            await cog.cog_load()

        transition.assert_awaited_once_with(7, "RELEASING", "NEEDS_RECONCILIATION")
        channel.send.assert_awaited()
        send_log.assert_awaited()
        sign_and_send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
