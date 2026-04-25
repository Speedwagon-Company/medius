from __future__ import annotations

from decimal import Decimal


def validate_trade_amount(amount: Decimal) -> None:
    if amount <= 0:
        raise ValueError("Amount must be positive")


def validate_trade_description(description: str) -> None:
    if len(description.strip()) < 5:
        raise ValueError("Description must be at least 5 characters long")

