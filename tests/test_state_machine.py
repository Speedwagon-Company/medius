from __future__ import annotations

import unittest

from domain.state_machine import InvalidTradeTransition, can_transition, ensure_transition
from domain.trade_states import TradeState


class TradeStateMachineTests(unittest.TestCase):
    def test_valid_transition(self) -> None:
        self.assertTrue(can_transition(TradeState.WAITING_PAYMENT, TradeState.PAYMENT_PENDING_CONFIRMATION))
        result = ensure_transition(
            TradeState.WAITING_PAYMENT, TradeState.PAYMENT_PENDING_CONFIRMATION
        )
        self.assertTrue(result.changed)
        self.assertEqual(result.old_state, TradeState.WAITING_PAYMENT)
        self.assertEqual(result.new_state, TradeState.PAYMENT_PENDING_CONFIRMATION)

    def test_idempotent_transition_same_state(self) -> None:
        result = ensure_transition(TradeState.RELEASED, TradeState.RELEASED)
        self.assertFalse(result.changed)

    def test_invalid_transition_raises(self) -> None:
        with self.assertRaises(InvalidTradeTransition):
            ensure_transition(TradeState.DRAFT, TradeState.RELEASED)
