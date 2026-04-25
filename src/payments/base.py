from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class ProviderPaymentStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMING = "CONFIRMING"
    CONFIRMED = "CONFIRMED"
    UNDERPAID = "UNDERPAID"
    OVERPAID = "OVERPAID"
    WRONG_ASSET = "WRONG_ASSET"
    WRONG_NETWORK = "WRONG_NETWORK"
    EXPIRED = "EXPIRED"
    DUPLICATE = "DUPLICATE"
    FAILED = "FAILED"


class ProviderPayoutStatus(str, Enum):
    REQUESTED = "REQUESTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class PaymentInstruction:
    provider_intent_id: str
    amount: Decimal
    asset: str
    network: str
    deposit_address: str
    qr_payload: str
    expires_at: datetime
    warning: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentStatusSnapshot:
    provider_intent_id: str
    status: ProviderPaymentStatus
    confirmations: int = 0
    required_confirmations: int = 0
    tx_hash: str | None = None
    observed_amount: Decimal | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PayoutRequest:
    idempotency_key: str
    amount: Decimal
    asset: str
    network: str
    destination: str


@dataclass
class PayoutResult:
    provider_payout_id: str
    status: ProviderPayoutStatus
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefundResult:
    provider_refund_id: str
    status: ProviderPayoutStatus
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookEventResult:
    event_id: str
    provider_intent_id: str
    status: ProviderPaymentStatus
    tx_hash: str | None = None
    confirmations: int = 0
    required_confirmations: int = 0
    observed_amount: Decimal | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    async def get_payment_status(self, provider_intent_id: str) -> PaymentStatusSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def create_payout(self, request: PayoutRequest) -> PayoutResult:
        raise NotImplementedError

    @abstractmethod
    async def refund(
        self,
        *,
        provider_intent_id: str,
        amount: Decimal,
        asset: str,
        network: str,
        idempotency_key: str,
    ) -> RefundResult:
        raise NotImplementedError

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def apply_webhook_event(self, payload: Mapping[str, Any]) -> WebhookEventResult:
        raise NotImplementedError
