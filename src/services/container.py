from __future__ import annotations

from payments.factory import get_payment_provider
from services.trade_service import TradeService
from settings import load_settings

_trade_service_singleton: TradeService | None = None


def get_trade_service() -> TradeService:
    global _trade_service_singleton
    if _trade_service_singleton is not None:
        return _trade_service_singleton

    settings = load_settings()
    provider = get_payment_provider(settings)
    _trade_service_singleton = TradeService(settings=settings, provider=provider)
    return _trade_service_singleton


def reset_trade_service_for_tests() -> None:
    global _trade_service_singleton
    _trade_service_singleton = None

