from __future__ import annotations

from enum import Enum


class TradeState(str, Enum):
    DRAFT = "DRAFT"
    WAITING_COUNTERPARTY = "WAITING_COUNTERPARTY"
    WAITING_PAYMENT = "WAITING_PAYMENT"
    PAYMENT_PENDING_CONFIRMATION = "PAYMENT_PENDING_CONFIRMATION"
    FUNDS_RECEIVED = "FUNDS_RECEIVED"
    WAITING_DELIVERY = "WAITING_DELIVERY"
    WAITING_BUYER_CONFIRMATION = "WAITING_BUYER_CONFIRMATION"
    DISPUTED = "DISPUTED"
    RELEASE_REQUESTED = "RELEASE_REQUESTED"
    RELEASED = "RELEASED"
    REFUND_REQUESTED = "REFUND_REQUESTED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class AuditEventType(str, Enum):
    TRADE_CREATED = "trade_created"
    COUNTERPARTY_JOINED = "counterparty_joined"
    INVOICE_CREATED = "invoice_created"
    PAYMENT_DETECTED = "payment_detected"
    DELIVERY_MARKED = "delivery_marked"
    BUYER_CONFIRMED = "buyer_confirmed"
    PAYOUT_REQUESTED = "payout_requested"
    PAYOUT_COMPLETED = "payout_completed"
    PAYOUT_FAILED = "payout_failed"
    DISPUTE_OPENED = "dispute_opened"
    ADMIN_MANUAL_ACTION = "admin_manual_action"
    TRADE_STATE_CHANGED = "trade_state_changed"
    WEBHOOK_PROCESSED = "webhook_processed"
    WEBHOOK_REPLAY_DROPPED = "webhook_replay_dropped"


class PaymentRecordStatus(str, Enum):
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


class PayoutRecordStatus(str, Enum):
    REQUESTED = "REQUESTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DisputeStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"

