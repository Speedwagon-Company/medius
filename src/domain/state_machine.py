from __future__ import annotations

from dataclasses import dataclass

from domain.trade_states import TradeState


class InvalidTradeTransition(ValueError):
    """Raised when a trade state transition is not allowed."""


ALLOWED_TRANSITIONS: dict[TradeState, set[TradeState]] = {
    TradeState.DRAFT: {
        TradeState.WAITING_COUNTERPARTY,
        TradeState.CANCELLED,
        TradeState.FAILED,
    },
    TradeState.WAITING_COUNTERPARTY: {
        TradeState.WAITING_PAYMENT,
        TradeState.CANCELLED,
        TradeState.EXPIRED,
        TradeState.FAILED,
    },
    TradeState.WAITING_PAYMENT: {
        TradeState.PAYMENT_PENDING_CONFIRMATION,
        TradeState.EXPIRED,
        TradeState.CANCELLED,
        TradeState.DISPUTED,
        TradeState.FAILED,
    },
    TradeState.PAYMENT_PENDING_CONFIRMATION: {
        TradeState.FUNDS_RECEIVED,
        TradeState.EXPIRED,
        TradeState.DISPUTED,
        TradeState.FAILED,
    },
    TradeState.FUNDS_RECEIVED: {
        TradeState.WAITING_DELIVERY,
        TradeState.DISPUTED,
        TradeState.REFUND_REQUESTED,
        TradeState.FAILED,
    },
    TradeState.WAITING_DELIVERY: {
        TradeState.WAITING_BUYER_CONFIRMATION,
        TradeState.DISPUTED,
        TradeState.REFUND_REQUESTED,
        TradeState.FAILED,
    },
    TradeState.WAITING_BUYER_CONFIRMATION: {
        TradeState.RELEASE_REQUESTED,
        TradeState.DISPUTED,
        TradeState.REFUND_REQUESTED,
        TradeState.EXPIRED,
        TradeState.FAILED,
    },
    TradeState.DISPUTED: {
        TradeState.RELEASE_REQUESTED,
        TradeState.REFUND_REQUESTED,
        TradeState.CANCELLED,
        TradeState.FAILED,
    },
    TradeState.RELEASE_REQUESTED: {
        TradeState.RELEASED,
        TradeState.DISPUTED,
        TradeState.FAILED,
    },
    TradeState.RELEASED: set(),
    TradeState.REFUND_REQUESTED: {
        TradeState.REFUNDED,
        TradeState.DISPUTED,
        TradeState.FAILED,
    },
    TradeState.REFUNDED: set(),
    TradeState.CANCELLED: set(),
    TradeState.EXPIRED: set(),
    TradeState.FAILED: set(),
}


@dataclass(frozen=True)
class TransitionResult:
    old_state: TradeState
    new_state: TradeState
    changed: bool


def can_transition(current: TradeState, target: TradeState) -> bool:
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, set())


def ensure_transition(current: TradeState, target: TradeState) -> TransitionResult:
    if current == target:
        return TransitionResult(old_state=current, new_state=target, changed=False)

    if not can_transition(current, target):
        raise InvalidTradeTransition(f"Illegal transition from {current} to {target}")

    return TransitionResult(old_state=current, new_state=target, changed=True)

