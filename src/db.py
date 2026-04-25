from __future__ import annotations

import os
import uuid
from datetime import datetime
from decimal import Decimal

from tortoise import Tortoise, fields
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.models import Model

from domain.trade_states import (
    AuditEventType,
    DisputeStatus,
    PaymentRecordStatus,
    PayoutRecordStatus,
    TradeState,
)


def _new_trade_public_id() -> str:
    return f"TRD-{uuid.uuid4().hex[:12].upper()}"


class User(Model):
    id = fields.IntField(pk=True)
    discord_id = fields.BigIntField(unique=True, description="Discord user id")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"


class SellerPayoutProfile(Model):
    id = fields.IntField(pk=True)
    seller = fields.ForeignKeyField("models.User", related_name="payout_profiles")
    provider = fields.CharField(max_length=32)
    encrypted_payout_details = fields.TextField()
    payout_details_masked = fields.CharField(max_length=128)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "seller_payout_profiles"


class Trade(Model):
    id = fields.IntField(pk=True)
    public_id = fields.CharField(max_length=24, unique=True, default=_new_trade_public_id)

    creator = fields.ForeignKeyField("models.User", related_name="created_trades")
    buyer = fields.ForeignKeyField("models.User", related_name="buyer_trades", null=True)
    seller = fields.ForeignKeyField("models.User", related_name="seller_trades", null=True)

    description = fields.TextField()
    amount = fields.DecimalField(max_digits=20, decimal_places=8)
    asset = fields.CharField(max_length=16)
    network = fields.CharField(max_length=32)

    state = fields.CharEnumField(TradeState, max_length=40, default=TradeState.DRAFT)
    payment_provider = fields.CharField(max_length=32)
    expires_at = fields.DatetimeField(null=True)
    last_error = fields.TextField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "trades"


class TradeParticipant(Model):
    id = fields.IntField(pk=True)
    trade = fields.ForeignKeyField("models.Trade", related_name="participants")
    user = fields.ForeignKeyField("models.User", related_name="trade_participations")
    role = fields.CharField(max_length=16)  # buyer | seller
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "trade_participants"
        unique_together = (("trade", "role"), ("trade", "user"))


class PaymentIntent(Model):
    id = fields.IntField(pk=True)
    trade = fields.ForeignKeyField("models.Trade", related_name="payment_intents")

    provider = fields.CharField(max_length=32)
    provider_intent_id = fields.CharField(max_length=128, unique=True)
    create_idempotency_key = fields.CharField(max_length=128, unique=True)

    status = fields.CharEnumField(
        PaymentRecordStatus,
        max_length=32,
        default=PaymentRecordStatus.PENDING,
    )
    required_confirmations = fields.IntField(default=0)
    confirmations = fields.IntField(default=0)

    deposit_address = fields.CharField(max_length=255)
    qr_payload = fields.TextField()

    amount = fields.DecimalField(max_digits=20, decimal_places=8)
    observed_amount = fields.DecimalField(max_digits=20, decimal_places=8, null=True)
    asset = fields.CharField(max_length=16)
    network = fields.CharField(max_length=32)

    observed_tx_hash = fields.CharField(max_length=255, null=True)
    failure_reason = fields.TextField(null=True)
    metadata_json = fields.JSONField(default=dict)

    expires_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "payment_intents"


class Payout(Model):
    id = fields.IntField(pk=True)
    trade = fields.ForeignKeyField("models.Trade", related_name="payouts")

    provider = fields.CharField(max_length=32)
    provider_payout_id = fields.CharField(max_length=128, unique=True, null=True)
    release_idempotency_key = fields.CharField(max_length=128, unique=True)

    status = fields.CharEnumField(PayoutRecordStatus, max_length=16, default=PayoutRecordStatus.REQUESTED)
    amount = fields.DecimalField(max_digits=20, decimal_places=8)
    asset = fields.CharField(max_length=16)
    network = fields.CharField(max_length=32)

    destination_masked = fields.CharField(max_length=128)
    failure_reason = fields.TextField(null=True)
    metadata_json = fields.JSONField(default=dict)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "payouts"


class Dispute(Model):
    id = fields.IntField(pk=True)
    trade = fields.ForeignKeyField("models.Trade", related_name="disputes")
    opened_by = fields.ForeignKeyField("models.User", related_name="opened_disputes", null=True)

    reason = fields.TextField()
    status = fields.CharEnumField(DisputeStatus, max_length=16, default=DisputeStatus.OPEN)

    resolution = fields.TextField(null=True)
    resolved_by = fields.ForeignKeyField("models.User", related_name="resolved_disputes", null=True)
    resolved_at = fields.DatetimeField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "disputes"


class AuditEvent(Model):
    id = fields.IntField(pk=True)
    trade = fields.ForeignKeyField("models.Trade", related_name="audit_events", null=True)
    actor = fields.ForeignKeyField("models.User", related_name="audit_events", null=True)

    event_type = fields.CharEnumField(AuditEventType, max_length=64)
    idempotency_key = fields.CharField(max_length=128, null=True)
    metadata_json = fields.JSONField(default=dict)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "audit_events"


class WebhookEvent(Model):
    id = fields.IntField(pk=True)
    provider = fields.CharField(max_length=32)
    event_id = fields.CharField(max_length=128, unique=True)

    payment_intent = fields.ForeignKeyField("models.PaymentIntent", related_name="webhook_events", null=True)
    trade = fields.ForeignKeyField("models.Trade", related_name="webhook_events", null=True)

    signature_valid = fields.BooleanField(default=False)
    processed = fields.BooleanField(default=False)
    payload_json = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)
    processed_at = fields.DatetimeField(null=True)

    class Meta:
        table = "webhook_events"


# Legacy model kept for compatibility with old code paths and existing sqlite data.
class Transaction(Model):
    id = fields.IntField(pk=True)
    sender = fields.ForeignKeyField("models.User", related_name="sent_transactions", null=True)
    receiver = fields.ForeignKeyField("models.User", related_name="received_transactions", null=True)

    sender_wallet = fields.CharField(max_length=100)
    receiver_wallet = fields.CharField(max_length=100)
    channel_id = fields.IntField()

    payment_status = fields.CharField(max_length=20, default="pending")
    transaction_hash = fields.CharField(max_length=255, unique=True, null=True)
    amount = fields.DecimalField(max_digits=20, decimal_places=8, null=True)
    currency = fields.CharField(max_length=10, default="USDT")

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "transactions"


async def init_db(db_url: str | None = None) -> None:
    if not db_url:
        db_url = os.getenv("DATABASE_URL", "sqlite://bot.db")

    os.environ["TZ"] = "UTC"

    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["db"]},
        use_tz=True,
        timezone="UTC",
    )
    await Tortoise.generate_schemas()


async def close_db() -> None:
    await Tortoise.close_connections()


async def get_or_create_user(discord_id: int) -> User:
    user, _created = await User.get_or_create(discord_id=discord_id)
    return user


async def get_user(discord_id: int) -> User | None:
    return await User.filter(discord_id=discord_id).first()


async def get_user_by_id(user_id: int) -> User | None:
    return await User.filter(id=user_id).first()


async def delete_user(discord_id: int) -> bool:
    user = await get_user(discord_id)
    if not user:
        return False
    await user.delete()
    return True


# Legacy helpers retained for backward compatibility.
async def create_transaction(
    sender_wallet: str,
    receiver_wallet: str,
    amount: float | Decimal | None = None,
    sender_discord_id: int | None = None,
    receiver_discord_id: int | None = None,
    currency: str = "USDT",
    chan_id: int | None = None,
) -> Transaction:
    sender_user = await get_or_create_user(sender_discord_id) if sender_discord_id else None
    receiver_user = await get_or_create_user(receiver_discord_id) if receiver_discord_id else None

    normalized_amount = Decimal(str(amount)) if amount is not None else None

    return await Transaction.create(
        sender=sender_user,
        receiver=receiver_user,
        sender_wallet=sender_wallet,
        receiver_wallet=receiver_wallet,
        amount=normalized_amount,
        currency=currency,
        payment_status="pending",
        channel_id=chan_id or 0,
    )


async def update_transaction_status(
    transaction_id: int,
    status: str,
    transaction_hash: str | None = None,
) -> Transaction | None:
    transaction = await Transaction.filter(id=transaction_id).first()
    if not transaction:
        return None

    transaction.payment_status = status
    if transaction_hash:
        transaction.transaction_hash = transaction_hash
    await transaction.save()
    return transaction


async def get_transaction(transaction_id: int) -> Transaction | None:
    return await Transaction.filter(id=transaction_id).first()


async def get_user_transactions(discord_id: int, status: str | None = None, limit: int = 50) -> list[Transaction]:
    user = await get_user(discord_id)
    if not user:
        return []

    query = Transaction.filter(Q(sender=user) | Q(receiver=user))
    if status:
        query = query.filter(payment_status=status)

    return await query.order_by("-created_at").limit(limit).prefetch_related("sender", "receiver")


async def get_user_sent_transactions(discord_id: int, limit: int = 50) -> list[Transaction]:
    user = await get_user(discord_id)
    if not user:
        return []

    return await (
        Transaction.filter(sender=user)
        .order_by("-created_at")
        .limit(limit)
        .prefetch_related("receiver")
    )


async def get_user_received_transactions(discord_id: int, limit: int = 50) -> list[Transaction]:
    user = await get_user(discord_id)
    if not user:
        return []

    return await (
        Transaction.filter(receiver=user)
        .order_by("-created_at")
        .limit(limit)
        .prefetch_related("sender")
    )


async def get_transactions_by_wallet(
    wallet_address: str,
    status: str | None = None,
    limit: int = 50,
) -> list[Transaction]:
    query = Transaction.filter(Q(sender_wallet=wallet_address) | Q(receiver_wallet=wallet_address))
    if status:
        query = query.filter(payment_status=status)

    return await query.order_by("-created_at").limit(limit).prefetch_related("sender", "receiver")


async def get_pending_transactions(limit: int = 100) -> list[Transaction]:
    return await (
        Transaction.filter(payment_status="pending")
        .order_by("created_at")
        .limit(limit)
        .prefetch_related("sender", "receiver")
    )


async def cancel_transaction(transaction_id: int) -> bool:
    transaction = await get_transaction(transaction_id)
    if not transaction or transaction.payment_status != "pending":
        return False

    transaction.payment_status = "cancelled"
    await transaction.save()
    return True


async def create_trade_participant(trade: Trade, user: User, role: str) -> TradeParticipant:
    try:
        participant = await TradeParticipant.create(trade=trade, user=user, role=role)
    except IntegrityError:
        participant = await TradeParticipant.get(trade=trade, user=user)
    return participant


async def now_utc() -> datetime:
    return datetime.utcnow()
