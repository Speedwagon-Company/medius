from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tortoise.exceptions import IntegrityError

from domain.state_machine import InvalidTradeTransition, ensure_transition
from domain.trade_states import AuditEventType, TradeState
from payments.base import (
    PaymentStatusSnapshot,
    PayoutRequest,
    ProviderPaymentStatus,
    ProviderPayoutStatus,
    WebhookEventResult,
)
from payments.mock import MockPaymentProvider
from services.authz import is_admin_discord_user
from services.trade_service import TradeService
from settings import Settings
from utils.validation import validate_trade_amount, validate_trade_description


class _DummyTrade:
    def __init__(self, state: TradeState):
        self.public_id = "TRD-UNIT-1"
        self.state = state.value
        self.amount = Decimal("10.00")
        self.asset = "USDT"
        self.network = "ETH"

    async def save(self, using_db=None) -> None:  # noqa: ANN001
        return None


class _DummyPaymentIntent:
    def __init__(self, provider_intent_id: str, trade_id: int = 1):
        self.provider_intent_id = provider_intent_id
        self.trade_id = trade_id
        self.status = ProviderPaymentStatus.PENDING
        self.confirmations = 0
        self.required_confirmations = 3
        self.observed_tx_hash = None
        self.observed_amount = None
        self.failure_reason = None
        self.metadata_json = {}
        self.save_calls = 0

    async def save(self, using_db=None) -> None:  # noqa: ANN001
        self.save_calls += 1


class _DummyWebhookEvent:
    def __init__(self):
        self.payment_intent = None
        self.trade = None
        self.processed = False
        self.processed_at = None
        self.save_calls = 0

    async def save(self, using_db=None) -> None:  # noqa: ANN001
        self.save_calls += 1


class _Query:
    def __init__(self, result):
        self._result = result

    def using_db(self, _connection):
        return self

    def select_for_update(self):
        return self

    async def first(self):
        return self._result


class _AsyncNullContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False


class _RecordingTradeService(TradeService):
    def __init__(self, *, settings: Settings, provider: MockPaymentProvider):
        super().__init__(settings=settings, provider=provider)
        self.transition_log: list[tuple[TradeState, TradeState, bool]] = []
        self.audit_log: list[tuple[AuditEventType, dict, str | None]] = []
        self._audit_idempotency: set[tuple[str, AuditEventType, str]] = set()
        self.latest_intent = _DummyPaymentIntent("mock_pi_refund")

    async def _transition(
        self,
        trade,
        target_state: TradeState,
        *,
        actor,  # noqa: ANN001
        reason_event: AuditEventType | None = None,
        reason_metadata=None,  # noqa: ANN001
        using_db=None,  # noqa: ANN001
    ) -> None:
        current_state = TradeState(str(trade.state))
        transition = ensure_transition(current_state, target_state)
        if transition.changed:
            trade.state = target_state.value
        self.transition_log.append(
            (transition.old_state, transition.new_state, transition.changed)
        )
        await self._audit(
            trade=trade,
            actor=actor,
            event_type=AuditEventType.TRADE_STATE_CHANGED,
            metadata={
                "from_state": transition.old_state.value,
                "to_state": transition.new_state.value,
                "changed": transition.changed,
            },
        )
        if reason_event:
            await self._audit(
                trade=trade,
                actor=actor,
                event_type=reason_event,
                metadata=dict(reason_metadata or {}),
            )

    async def _audit(
        self,
        *,
        trade,
        actor,  # noqa: ANN001
        event_type: AuditEventType,
        metadata,
        idempotency_key: str | None = None,
    ) -> None:
        if idempotency_key:
            key = (trade.public_id, event_type, idempotency_key)
            if key in self._audit_idempotency:
                return
            self._audit_idempotency.add(key)
        self.audit_log.append((event_type, dict(metadata), idempotency_key))

    async def _get_latest_payment_intent(self, trade):  # noqa: ANN001
        return self.latest_intent


class MockProviderAndValidationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.provider = MockPaymentProvider(
            webhook_secret="mock-secret",
            auto_complete_payout=True,
        )

    async def test_payment_intent_idempotency(self) -> None:
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        intent_1 = await self.provider.create_payment_intent(
            amount=Decimal("1.00"),
            asset="USDT",
            network="ETH",
            idempotency_key="pi-1",
            expires_at=expires_at,
            context={"required_confirmations": 2},
        )
        intent_2 = await self.provider.create_payment_intent(
            amount=Decimal("1.00"),
            asset="USDT",
            network="ETH",
            idempotency_key="pi-1",
            expires_at=expires_at,
            context={"required_confirmations": 2},
        )

        self.assertEqual(intent_1.provider_intent_id, intent_2.provider_intent_id)

    async def test_payout_idempotency(self) -> None:
        request = PayoutRequest(
            idempotency_key="po-1",
            amount=Decimal("2.50"),
            asset="USDT",
            network="ETH",
            destination="0x1111111111111111111111111111111111111111",
        )

        payout_1 = await self.provider.create_payout(request)
        payout_2 = await self.provider.create_payout(request)

        self.assertEqual(payout_1.provider_payout_id, payout_2.provider_payout_id)
        self.assertEqual(payout_1.status, ProviderPayoutStatus.COMPLETED)

    async def test_webhook_signature_and_replay_idempotency(self) -> None:
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        intent = await self.provider.create_payment_intent(
            amount=Decimal("5.00"),
            asset="USDT",
            network="ETH",
            idempotency_key="pi-2",
            expires_at=expires_at,
            context={"required_confirmations": 3},
        )

        payload_dict = {
            "event_id": "evt_1",
            "provider_intent_id": intent.provider_intent_id,
            "status": "CONFIRMED",
            "tx_hash": "mocktx-123",
            "confirmations": 3,
            "required_confirmations": 3,
            "observed_amount": "5.00",
        }
        payload = json.dumps(payload_dict).encode("utf-8")
        signature = hmac.new(b"mock-secret", payload, hashlib.sha256).hexdigest()

        self.assertTrue(self.provider.verify_webhook_signature(payload, signature))

        first = await self.provider.apply_webhook_event(payload_dict)
        second = await self.provider.apply_webhook_event(payload_dict)

        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(first.status, ProviderPaymentStatus.CONFIRMED)

        snapshot = await self.provider.get_payment_status(intent.provider_intent_id)
        self.assertEqual(snapshot.status, ProviderPaymentStatus.CONFIRMED)
        self.assertEqual(snapshot.confirmations, 3)

    def test_input_validation(self) -> None:
        validate_trade_amount(Decimal("1.0"))
        validate_trade_description("valid description")

        with self.assertRaises(ValueError):
            validate_trade_amount(Decimal("0"))

        with self.assertRaises(ValueError):
            validate_trade_description("bad")

    def test_admin_permission_check(self) -> None:
        settings = Settings(
            app_env="development",
            discord_token="x",
            database_url="sqlite://bot.db",
            payment_provider="mock",
            payment_timeout_minutes=30,
            required_confirmations=3,
            custodial_mode=False,
            custodial_mode_approved=False,
            payout_encryption_key="x" * 32,
            admin_discord_ids={777, 888},
            mock_webhook_secret="secret",
            mock_auto_complete_payout=True,
        )

        self.assertTrue(is_admin_discord_user(777, settings))
        self.assertFalse(is_admin_discord_user(999, settings))


class TradeServiceFlowUnitTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.settings = Settings(
            app_env="development",
            discord_token="x",
            database_url="sqlite://bot.db",
            payment_provider="mock",
            payment_timeout_minutes=30,
            required_confirmations=3,
            custodial_mode=False,
            custodial_mode_approved=False,
            payout_encryption_key="x" * 32,
            admin_discord_ids={9001},
            mock_webhook_secret="mock-secret",
            mock_auto_complete_payout=True,
        )
        self.provider = MockPaymentProvider(
            webhook_secret=self.settings.mock_webhook_secret,
            auto_complete_payout=True,
        )
        self.service = _RecordingTradeService(
            settings=self.settings,
            provider=self.provider,
        )

    async def test_refresh_waiting_payment_with_confirmed(self) -> None:
        trade = _DummyTrade(TradeState.WAITING_PAYMENT)
        intent = _DummyPaymentIntent("mock_pi_1")
        snapshot = PaymentStatusSnapshot(
            provider_intent_id=intent.provider_intent_id,
            status=ProviderPaymentStatus.CONFIRMED,
            confirmations=3,
            required_confirmations=3,
            tx_hash="mocktx-1",
            observed_amount=Decimal("10.00"),
        )

        changed = await self.service._apply_payment_snapshot(
            trade=trade,
            payment_intent=intent,
            snapshot=snapshot,
            actor=None,
            using_db=None,
        )

        self.assertTrue(changed)
        self.assertEqual(trade.state, TradeState.WAITING_DELIVERY.value)
        self.assertIn(
            (TradeState.WAITING_PAYMENT, TradeState.PAYMENT_PENDING_CONFIRMATION, True),
            self.service.transition_log,
        )
        self.assertIn(
            (TradeState.PAYMENT_PENDING_CONFIRMATION, TradeState.FUNDS_RECEIVED, True),
            self.service.transition_log,
        )

    async def test_refresh_waiting_payment_with_pending(self) -> None:
        trade = _DummyTrade(TradeState.WAITING_PAYMENT)
        intent = _DummyPaymentIntent("mock_pi_2")
        snapshot = PaymentStatusSnapshot(
            provider_intent_id=intent.provider_intent_id,
            status=ProviderPaymentStatus.PENDING,
            confirmations=0,
            required_confirmations=3,
        )

        changed = await self.service._apply_payment_snapshot(
            trade=trade,
            payment_intent=intent,
            snapshot=snapshot,
            actor=None,
            using_db=None,
        )

        self.assertTrue(changed)
        self.assertEqual(trade.state, TradeState.PAYMENT_PENDING_CONFIRMATION.value)

    async def test_refresh_pending_confirmation_with_confirmed(self) -> None:
        trade = _DummyTrade(TradeState.PAYMENT_PENDING_CONFIRMATION)
        intent = _DummyPaymentIntent("mock_pi_3")
        snapshot = PaymentStatusSnapshot(
            provider_intent_id=intent.provider_intent_id,
            status=ProviderPaymentStatus.CONFIRMED,
            confirmations=3,
            required_confirmations=3,
            tx_hash="mocktx-2",
            observed_amount=Decimal("10.00"),
        )

        changed = await self.service._apply_payment_snapshot(
            trade=trade,
            payment_intent=intent,
            snapshot=snapshot,
            actor=None,
            using_db=None,
        )

        self.assertTrue(changed)
        self.assertEqual(trade.state, TradeState.WAITING_DELIVERY.value)

    async def test_repeated_refresh_does_not_duplicate_state_or_audit(self) -> None:
        trade = _DummyTrade(TradeState.WAITING_PAYMENT)
        intent = _DummyPaymentIntent("mock_pi_4")
        snapshot = PaymentStatusSnapshot(
            provider_intent_id=intent.provider_intent_id,
            status=ProviderPaymentStatus.CONFIRMED,
            confirmations=3,
            required_confirmations=3,
            tx_hash="mocktx-3",
            observed_amount=Decimal("10.00"),
        )

        first_changed = await self.service._apply_payment_snapshot(
            trade=trade,
            payment_intent=intent,
            snapshot=snapshot,
            actor=None,
            using_db=None,
        )
        transitions_after_first = len(self.service.transition_log)
        audits_after_first = len(self.service.audit_log)

        second_changed = await self.service._apply_payment_snapshot(
            trade=trade,
            payment_intent=intent,
            snapshot=snapshot,
            actor=None,
            using_db=None,
        )

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)
        self.assertEqual(len(self.service.transition_log), transitions_after_first)
        self.assertEqual(len(self.service.audit_log), audits_after_first)

    async def test_refund_allowed_states(self) -> None:
        admin = SimpleNamespace(id=9001)
        allowed_states = [
            TradeState.DISPUTED,
            TradeState.FUNDS_RECEIVED,
            TradeState.WAITING_DELIVERY,
            TradeState.WAITING_BUYER_CONFIRMATION,
            TradeState.REFUND_REQUESTED,
        ]
        for state in allowed_states:
            with self.subTest(state=state.value):
                trade = _DummyTrade(state)
                await self.service._execute_refund(
                    trade=trade,
                    admin=admin,
                    note=f"refund from {state.value}",
                )
                self.assertEqual(trade.state, TradeState.REFUNDED.value)

    async def test_refund_disallowed_states(self) -> None:
        admin = SimpleNamespace(id=9001)
        disallowed_states = [
            TradeState.WAITING_PAYMENT,
            TradeState.PAYMENT_PENDING_CONFIRMATION,
            TradeState.RELEASE_REQUESTED,
            TradeState.FAILED,
            TradeState.RELEASED,
        ]
        for state in disallowed_states:
            with self.subTest(state=state.value):
                trade = _DummyTrade(state)
                with self.assertRaises(InvalidTradeTransition):
                    await self.service._execute_refund(
                        trade=trade,
                        admin=admin,
                        note=f"refund from {state.value}",
                    )

    async def test_handle_webhook_duplicate_event_id_is_safe(self) -> None:
        service = TradeService(settings=self.settings, provider=self.provider)
        intent = _DummyPaymentIntent("mock_pi_webhook", trade_id=11)
        trade = SimpleNamespace(id=11, public_id="TRD-WEBHOOK")
        created_webhook = _DummyWebhookEvent()
        existing_webhook = SimpleNamespace(trade_id=trade.id)
        webhook_result = WebhookEventResult(
            event_id="evt-dup",
            provider_intent_id=intent.provider_intent_id,
            status=ProviderPaymentStatus.CONFIRMED,
            tx_hash="mocktx-dup",
            confirmations=3,
            required_confirmations=3,
            observed_amount=Decimal("10.00"),
            metadata={"provider": "mock"},
        )

        payload_dict = {
            "event_id": "evt-dup",
            "provider_intent_id": intent.provider_intent_id,
            "status": "CONFIRMED",
            "tx_hash": "mocktx-dup",
            "confirmations": 3,
            "required_confirmations": 3,
            "observed_amount": "10.00",
        }
        payload = json.dumps(payload_dict).encode("utf-8")
        signature = hmac.new(b"mock-secret", payload, hashlib.sha256).hexdigest()

        with (
            patch("services.trade_service.in_transaction", return_value=_AsyncNullContext()),
            patch(
                "services.trade_service.WebhookEvent.create",
                new=AsyncMock(side_effect=[created_webhook, IntegrityError()]),
            ),
            patch(
                "services.trade_service.WebhookEvent.filter",
                return_value=_Query(existing_webhook),
            ),
            patch(
                "services.trade_service.PaymentIntent.filter",
                return_value=_Query(intent),
            ),
            patch(
                "services.trade_service.Trade.filter",
                side_effect=[_Query(trade), _Query(trade)],
            ),
            patch.object(
                service.provider,
                "apply_webhook_event",
                new=AsyncMock(return_value=webhook_result),
            ) as apply_webhook_event_mock,
            patch.object(
                service,
                "refresh_payment_status",
                new=AsyncMock(return_value=None),
            ) as refresh_status_mock,
            patch.object(service, "_audit", new=AsyncMock()) as audit_mock,
        ):
            first = await service.handle_webhook(payload=payload, signature=signature)
            second = await service.handle_webhook(payload=payload, signature=signature)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(intent.save_calls, 1)
        self.assertEqual(created_webhook.save_calls, 1)
        self.assertEqual(apply_webhook_event_mock.await_count, 1)
        self.assertEqual(refresh_status_mock.await_count, 1)
        self.assertEqual(audit_mock.await_count, 2)
        self.assertEqual(
            [call.kwargs["event_type"] for call in audit_mock.await_args_list],
            [AuditEventType.WEBHOOK_PROCESSED, AuditEventType.WEBHOOK_REPLAY_DROPPED],
        )
