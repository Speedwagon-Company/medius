from __future__ import annotations

from payments.base import PaymentProvider
from payments.mock import MockPaymentProvider
from settings import Settings

_provider_singleton: PaymentProvider | None = None


def get_payment_provider(settings: Settings) -> PaymentProvider:
    global _provider_singleton
    if _provider_singleton is not None:
        return _provider_singleton

    provider_name = settings.payment_provider.strip().lower()

    if provider_name == "mock":
        if settings.is_production:
            raise RuntimeError(
                "PAYMENT_PROVIDER=mock is not allowed in production. "
                "Configure a real provider before startup."
            )
        _provider_singleton = MockPaymentProvider(
            webhook_secret=settings.mock_webhook_secret,
            auto_complete_payout=settings.mock_auto_complete_payout,
        )
        return _provider_singleton

    raise RuntimeError(
        f"Unsupported PAYMENT_PROVIDER '{settings.payment_provider}'. "
        "No real provider is configured yet. Failing closed."
    )


def reset_payment_provider_for_tests() -> None:
    global _provider_singleton
    _provider_singleton = None

