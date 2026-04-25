from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from payments.base import (
    PaymentInstruction,
    PaymentProvider,
    PaymentStatusSnapshot,
    PayoutRequest,
    PayoutResult,
    ProviderPaymentStatus,
    ProviderPayoutStatus,
    RefundResult,
    WebhookEventResult,
)


class MockPaymentProvider(PaymentProvider):
    """
    Development-only provider.

    This provider intentionally does not move real funds.
    It supports deterministic simulation for tests and local dev.
    """

    name = "mock"

    def __init__(self, *, webhook_secret: str, auto_complete_payout: bool = True):
        self._webhook_secret = webhook_secret.encode("utf-8")
        self._auto_complete_payout = auto_complete_payout
        self._intents: dict[str, dict[str, Any]] = {}
        self._idempotent_intent_map: dict[str, str] = {}
        self._payouts: dict[str, dict[str, Any]] = {}
        self._idempotent_payout_map: dict[str, str] = {}
        self._refunds: dict[str, dict[str, Any]] = {}
        self._webhook_events: dict[str, WebhookEventResult] = {}

    async def create_payment_intent(
        self,
        *,
        amount: Decimal,
        asset: str,
        network: str,
        idempotency_key: str,
        expires_at: datetime,
        context: Mapping[str, Any],
    ) -> PaymentInstruction:
        existing_id = self._idempotent_intent_map.get(idempotency_key)
        if existing_id:
            existing = self._intents[existing_id]
            return self._as_instruction(existing_id, existing)

        intent_id = f"mock_pi_{uuid.uuid4().hex[:24]}"
        deposit_address = f"mock://{network.lower()}/{asset.lower()}/{intent_id}"
        qr_payload = (
            f"mockpay://pay?intent_id={intent_id}&amount={amount}&asset={asset}&network={network}"
        )
        data = {
            "amount": amount,
            "asset": asset,
            "network": network,
            "status": ProviderPaymentStatus.PENDING,
            "confirmations": 0,
            "required_confirmations": int(context.get("required_confirmations", 3)),
            "tx_hash": None,
            "observed_amount": None,
            "reason": None,
            "expires_at": expires_at,
            "deposit_address": deposit_address,
            "qr_payload": qr_payload,
            "metadata": {"provider": self.name},
        }
        self._intents[intent_id] = data
        self._idempotent_intent_map[idempotency_key] = intent_id
        return self._as_instruction(intent_id, data)

    async def get_payment_status(self, provider_intent_id: str) -> PaymentStatusSnapshot:
        data = self._intents.get(provider_intent_id)
        if data is None:
            return PaymentStatusSnapshot(
                provider_intent_id=provider_intent_id,
                status=ProviderPaymentStatus.FAILED,
                reason="Unknown intent id",
            )
        return self._as_snapshot(provider_intent_id, data)

    async def create_payout(self, request: PayoutRequest) -> PayoutResult:
        existing_id = self._idempotent_payout_map.get(request.idempotency_key)
        if existing_id:
            existing = self._payouts[existing_id]
            return PayoutResult(
                provider_payout_id=existing_id,
                status=existing["status"],
                reason=existing.get("reason"),
                metadata=existing.get("metadata", {}),
            )

        payout_id = f"mock_po_{uuid.uuid4().hex[:24]}"
        status = (
            ProviderPayoutStatus.COMPLETED
            if self._auto_complete_payout
            else ProviderPayoutStatus.REQUESTED
        )
        payout = {
            "status": status,
            "reason": None,
            "amount": request.amount,
            "asset": request.asset,
            "network": request.network,
            "destination": request.destination,
            "metadata": {"provider": self.name},
        }
        self._payouts[payout_id] = payout
        self._idempotent_payout_map[request.idempotency_key] = payout_id
        return PayoutResult(
            provider_payout_id=payout_id,
            status=status,
            reason=None,
            metadata=payout["metadata"],
        )

    async def refund(
        self,
        *,
        provider_intent_id: str,
        amount: Decimal,
        asset: str,
        network: str,
        idempotency_key: str,
    ) -> RefundResult:
        existing = self._refunds.get(idempotency_key)
        if existing:
            return RefundResult(
                provider_refund_id=existing["provider_refund_id"],
                status=existing["status"],
                reason=existing["reason"],
                metadata=existing["metadata"],
            )

        refund_id = f"mock_rf_{uuid.uuid4().hex[:24]}"
        result = {
            "provider_refund_id": refund_id,
            "status": ProviderPayoutStatus.COMPLETED,
            "reason": None,
            "metadata": {
                "provider": self.name,
                "provider_intent_id": provider_intent_id,
                "amount": str(amount),
                "asset": asset,
                "network": network,
            },
        }
        self._refunds[idempotency_key] = result
        return RefundResult(**result)

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        expected = hmac.new(self._webhook_secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.strip())

    async def apply_webhook_event(self, payload: Mapping[str, Any]) -> WebhookEventResult:
        event_id = str(payload["event_id"])
        existing = self._webhook_events.get(event_id)
        if existing is not None:
            return existing

        intent_id = str(payload["provider_intent_id"])
        status = ProviderPaymentStatus(str(payload["status"]))
        tx_hash = payload.get("tx_hash")
        confirmations = int(payload.get("confirmations", 0))
        required_confirmations = int(payload.get("required_confirmations", 0))
        reason = payload.get("reason")
        observed_amount_raw = payload.get("observed_amount")
        observed_amount = Decimal(str(observed_amount_raw)) if observed_amount_raw is not None else None

        intent = self._intents.get(intent_id)
        if intent is None:
            raise ValueError("Unknown provider_intent_id in webhook payload")

        intent["status"] = status
        intent["tx_hash"] = tx_hash
        intent["confirmations"] = confirmations
        if required_confirmations:
            intent["required_confirmations"] = required_confirmations
        intent["reason"] = reason
        intent["observed_amount"] = observed_amount

        result = WebhookEventResult(
            event_id=event_id,
            provider_intent_id=intent_id,
            status=status,
            tx_hash=tx_hash,
            confirmations=confirmations,
            required_confirmations=intent["required_confirmations"],
            observed_amount=observed_amount,
            reason=reason,
            metadata={"provider": self.name},
        )
        self._webhook_events[event_id] = result
        return result

    async def mark_payment_confirmed(
        self,
        provider_intent_id: str,
        *,
        tx_hash: str,
        confirmations: int,
    ) -> PaymentStatusSnapshot:
        intent = self._intents.get(provider_intent_id)
        if intent is None:
            raise ValueError("Unknown provider_intent_id")
        intent["status"] = ProviderPaymentStatus.CONFIRMED
        intent["tx_hash"] = tx_hash
        intent["confirmations"] = confirmations
        intent["observed_amount"] = intent["amount"]
        return self._as_snapshot(provider_intent_id, intent)

    def _as_instruction(self, intent_id: str, data: Mapping[str, Any]) -> PaymentInstruction:
        return PaymentInstruction(
            provider_intent_id=intent_id,
            amount=data["amount"],
            asset=data["asset"],
            network=data["network"],
            deposit_address=data["deposit_address"],
            qr_payload=data["qr_payload"],
            expires_at=data["expires_at"],
            warning=(
                "Send only the exact configured asset and network. "
                "Wrong asset/network may be unrecoverable."
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def _as_snapshot(self, intent_id: str, data: Mapping[str, Any]) -> PaymentStatusSnapshot:
        return PaymentStatusSnapshot(
            provider_intent_id=intent_id,
            status=data["status"],
            confirmations=data["confirmations"],
            required_confirmations=data["required_confirmations"],
            tx_hash=data["tx_hash"],
            observed_amount=data["observed_amount"],
            reason=data["reason"],
            metadata=dict(data.get("metadata", {})),
        )
