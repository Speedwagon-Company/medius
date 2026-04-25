from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _csv_ints(name: str) -> set[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return set()
    values: set[int] = set()
    for part in raw.split(","):
        cleaned = part.strip()
        if cleaned:
            values.add(int(cleaned))
    return values


@dataclass(frozen=True)
class Settings:
    app_env: str
    discord_token: str
    database_url: str
    payment_provider: str
    payment_timeout_minutes: int
    required_confirmations: int
    custodial_mode: bool
    custodial_mode_approved: bool
    payout_encryption_key: str
    admin_discord_ids: set[int]
    mock_webhook_secret: str
    mock_auto_complete_payout: bool

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_mock_provider(self) -> bool:
        return self.payment_provider.strip().lower() == "mock"

    def validate(self) -> None:
        if not self.discord_token:
            raise RuntimeError("DIS_BOT_TOKEN must be configured")

        if self.is_production and self.is_mock_provider:
            raise RuntimeError(
                "PAYMENT_PROVIDER=mock is not allowed in production. "
                "Configure a real provider before startup."
            )

        if self.custodial_mode and not self.custodial_mode_approved:
            raise RuntimeError(
                "CUSTODIAL_MODE is enabled but CUSTODIAL_MODE_APPROVED is false. "
                "Failing closed pending legal/compliance review."
            )

        if self.required_confirmations < 1:
            raise RuntimeError("REQUIRED_CONFIRMATIONS must be >= 1")

        if self.payment_timeout_minutes < 1:
            raise RuntimeError("PAYMENT_TIMEOUT_MINUTES must be >= 1")

        # We encrypt payout details whenever we store them.
        if not self.payout_encryption_key:
            raise RuntimeError(
                "PAYOUT_ENCRYPTION_KEY must be configured to store payout details safely"
            )


def load_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        discord_token=os.getenv("DIS_BOT_TOKEN", "").strip(),
        database_url=os.getenv("DATABASE_URL", "sqlite://bot.db").strip(),
        payment_provider=os.getenv("PAYMENT_PROVIDER", "mock").strip(),
        payment_timeout_minutes=_as_int("PAYMENT_TIMEOUT_MINUTES", 30),
        required_confirmations=_as_int("REQUIRED_CONFIRMATIONS", 3),
        custodial_mode=_as_bool("CUSTODIAL_MODE", False),
        custodial_mode_approved=_as_bool("CUSTODIAL_MODE_APPROVED", False),
        payout_encryption_key=os.getenv("PAYOUT_ENCRYPTION_KEY", "").strip(),
        admin_discord_ids=_csv_ints("ADMIN_DISCORD_IDS"),
        mock_webhook_secret=os.getenv("MOCK_WEBHOOK_SECRET", "replace-me"),
        mock_auto_complete_payout=_as_bool("MOCK_AUTO_COMPLETE_PAYOUT", True),
    )

