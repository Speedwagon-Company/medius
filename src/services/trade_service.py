from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from db import (
    AuditEvent,
    Dispute,
    PaymentIntent,
    Payout,
    SellerPayoutProfile,
    Trade,
    User,
    WebhookEvent,
    create_trade_participant,
    get_or_create_user,
)
from domain.state_machine import InvalidTradeTransition, ensure_transition
from domain.trade_states import (
    AuditEventType,
    DisputeStatus,
    PaymentRecordStatus,
    PayoutRecordStatus,
    TradeState,
)
from payments import (
    MockPaymentProvider,
    PaymentProvider,
    PaymentStatusSnapshot,
    PayoutRequest,
    ProviderPaymentStatus,
    ProviderPayoutStatus,
)
from services.authz import is_admin_discord_user
from settings import Settings
from utils.security import decrypt_text, encrypt_text, mask_wallet
from utils.validation import validate_trade_amount, validate_trade_description


class TradeServiceError(RuntimeError):
    pass


class PermissionDenied(TradeServiceError):
    pass


class NotFoundError(TradeServiceError):
    pass


class ValidationError(TradeServiceError):
    pass


@dataclass
class PaymentRefreshResult:
    trade: Trade
    payment_intent: PaymentIntent
    provider_status: ProviderPaymentStatus
    trade_state_changed: bool


class TradeService:
    def __init__(self, *, settings: Settings, provider: PaymentProvider):
        self.settings = settings
        self.provider = provider

    async def create_trade(
        self,
        *,
        creator_discord_id: int,
        buyer_discord_id: int,
        seller_discord_id: int,
        description: str,
        amount: Decimal,
        asset: str,
        network: str,
    ) -> Trade:
        try:
            validate_trade_amount(amount)
            validate_trade_description(description)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        if buyer_discord_id == seller_discord_id:
            raise ValidationError("Buyer and seller must be different users")

        creator = await get_or_create_user(creator_discord_id)
        buyer = await get_or_create_user(buyer_discord_id)
        seller = await get_or_create_user(seller_discord_id)

        expires_at = await self._expires_at()

        trade = await Trade.create(
            creator=creator,
            buyer=buyer,
            seller=seller,
            description=description.strip(),
            amount=amount,
            asset=asset.upper().strip(),
            network=network.upper().strip(),
            state=TradeState.DRAFT,
            payment_provider=self.provider.name,
            expires_at=expires_at,
        )

        await create_trade_participant(trade, buyer, "buyer")
        await create_trade_participant(trade, seller, "seller")

        await self._transition(
            trade,
            TradeState.WAITING_COUNTERPARTY,
            actor=creator,
            reason_event=AuditEventType.TRADE_CREATED,
            reason_metadata={
                "creator_discord_id": creator_discord_id,
                "amount": str(amount),
                "asset": asset.upper(),
                "network": network.upper(),
            },
        )
        await self._transition(
            trade,
            TradeState.WAITING_PAYMENT,
            actor=creator,
            reason_event=AuditEventType.COUNTERPARTY_JOINED,
            reason_metadata={
                "buyer_discord_id": buyer_discord_id,
                "seller_discord_id": seller_discord_id,
            },
        )

        return trade

    async def set_seller_payout_details(
        self,
        *,
        trade_public_id: str,
        seller_discord_id: int,
        payout_wallet: str,
    ) -> SellerPayoutProfile:
        if not payout_wallet:
            raise ValidationError("Seller payout wallet is required")

        trade = await self._get_trade(trade_public_id)
        if not trade.seller:
            raise ValidationError("Trade seller is not configured")

        seller = await get_or_create_user(seller_discord_id)
        if trade.seller_id != seller.id:
            raise PermissionDenied("Only the trade seller can set payout details")

        encrypted = encrypt_text(payout_wallet, self.settings.payout_encryption_key)
        masked = mask_wallet(payout_wallet)

        existing = await SellerPayoutProfile.filter(
            seller=seller,
            provider=self.provider.name,
            is_active=True,
        ).first()

        if existing:
            existing.encrypted_payout_details = encrypted
            existing.payout_details_masked = masked
            await existing.save()
            profile = existing
        else:
            profile = await SellerPayoutProfile.create(
                seller=seller,
                provider=self.provider.name,
                encrypted_payout_details=encrypted,
                payout_details_masked=masked,
                is_active=True,
            )

        await self._audit(
            trade=trade,
            actor=seller,
            event_type=AuditEventType.ADMIN_MANUAL_ACTION,
            metadata={
                "action": "seller_payout_profile_upsert",
                "masked_destination": masked,
            },
        )
        return profile

    async def create_payment_intent(
        self,
        *,
        trade_public_id: str,
        actor_discord_id: int,
        idempotency_key: str,
    ) -> PaymentIntent:
        actor = await get_or_create_user(actor_discord_id)

        existing = await PaymentIntent.filter(create_idempotency_key=idempotency_key).first()
        if existing:
            return existing

        async with in_transaction() as connection:
            trade = (
                await Trade.filter(public_id=trade_public_id)
                .using_db(connection)
                .select_for_update()
                .first()
            )
            if not trade:
                raise NotFoundError(f"Trade {trade_public_id} was not found")

            trade_state = TradeState(str(trade.state))
            if trade_state not in {TradeState.WAITING_PAYMENT, TradeState.PAYMENT_PENDING_CONFIRMATION}:
                raise InvalidTradeTransition(
                    f"Cannot create payment intent from trade state {trade_state}"
                )

            instruction = await self.provider.create_payment_intent(
                amount=trade.amount,
                asset=trade.asset,
                network=trade.network,
                idempotency_key=idempotency_key,
                expires_at=trade.expires_at,
                context={"required_confirmations": self.settings.required_confirmations},
            )

            try:
                intent = await PaymentIntent.create(
                    trade=trade,
                    provider=self.provider.name,
                    provider_intent_id=instruction.provider_intent_id,
                    create_idempotency_key=idempotency_key,
                    status=PaymentRecordStatus.PENDING,
                    required_confirmations=self.settings.required_confirmations,
                    confirmations=0,
                    deposit_address=instruction.deposit_address,
                    qr_payload=instruction.qr_payload,
                    amount=instruction.amount,
                    asset=instruction.asset,
                    network=instruction.network,
                    metadata_json=instruction.metadata,
                    expires_at=instruction.expires_at,
                    using_db=connection,
                )
            except IntegrityError:
                intent = await PaymentIntent.filter(create_idempotency_key=idempotency_key).first()
                if not intent:
                    raise

        await self._audit(
            trade=trade,
            actor=actor,
            event_type=AuditEventType.INVOICE_CREATED,
            metadata={
                "provider_intent_id": intent.provider_intent_id,
                "asset": intent.asset,
                "network": intent.network,
                "amount": str(intent.amount),
                "expires_at": intent.expires_at.isoformat() if intent.expires_at else None,
            },
            idempotency_key=idempotency_key,
        )

        return intent

    async def refresh_payment_status(
        self,
        *,
        trade_public_id: str,
        actor_discord_id: int | None,
    ) -> PaymentRefreshResult:
        actor = await get_or_create_user(actor_discord_id) if actor_discord_id else None
        trade = await self._get_trade(trade_public_id)

        payment_intent = await self._get_latest_payment_intent(trade)
        snapshot = await self.provider.get_payment_status(payment_intent.provider_intent_id)

        trade_state_changed = False

        async with in_transaction() as connection:
            locked_trade = (
                await Trade.filter(id=trade.id).using_db(connection).select_for_update().first()
            )
            locked_intent = (
                await PaymentIntent.filter(id=payment_intent.id)
                .using_db(connection)
                .select_for_update()
                .first()
            )
            if not locked_trade or not locked_intent:
                raise NotFoundError("Trade or payment intent no longer exists")

            trade_state_changed = await self._apply_payment_snapshot(
                trade=locked_trade,
                payment_intent=locked_intent,
                snapshot=snapshot,
                actor=actor,
                using_db=connection,
            )

        updated_trade = await self._get_trade(trade_public_id)
        updated_intent = await self._get_latest_payment_intent(updated_trade)
        return PaymentRefreshResult(
            trade=updated_trade,
            payment_intent=updated_intent,
            provider_status=snapshot.status,
            trade_state_changed=trade_state_changed,
        )

    async def _apply_payment_snapshot(
        self,
        *,
        trade: Trade,
        payment_intent: PaymentIntent,
        snapshot: PaymentStatusSnapshot,
        actor: User | None,
        using_db=None,
    ) -> bool:
        payment_intent.status = PaymentRecordStatus(snapshot.status.value)
        payment_intent.confirmations = snapshot.confirmations
        payment_intent.required_confirmations = (
            snapshot.required_confirmations or payment_intent.required_confirmations
        )
        payment_intent.observed_tx_hash = snapshot.tx_hash
        payment_intent.observed_amount = snapshot.observed_amount
        payment_intent.failure_reason = snapshot.reason
        payment_intent.metadata_json = snapshot.metadata
        if hasattr(payment_intent, "save"):
            await payment_intent.save(using_db=using_db)

        trade_state_changed = False
        trade_state = TradeState(str(trade.state))
        payment_detected_metadata = {
            "provider_intent_id": payment_intent.provider_intent_id,
            "tx_hash": snapshot.tx_hash,
            "confirmations": snapshot.confirmations,
            "provider_status": snapshot.status.value,
        }

        if snapshot.status in {ProviderPaymentStatus.PENDING, ProviderPaymentStatus.CONFIRMING}:
            if trade_state == TradeState.WAITING_PAYMENT:
                await self._transition(
                    trade,
                    TradeState.PAYMENT_PENDING_CONFIRMATION,
                    actor=actor,
                    reason_event=AuditEventType.PAYMENT_DETECTED,
                    reason_metadata=payment_detected_metadata,
                    using_db=using_db,
                )
                trade_state_changed = True

        elif snapshot.status == ProviderPaymentStatus.CONFIRMED:
            if trade_state == TradeState.WAITING_PAYMENT:
                await self._transition(
                    trade,
                    TradeState.PAYMENT_PENDING_CONFIRMATION,
                    actor=actor,
                    reason_event=AuditEventType.PAYMENT_DETECTED,
                    reason_metadata=payment_detected_metadata,
                    using_db=using_db,
                )
                trade_state = TradeState.PAYMENT_PENDING_CONFIRMATION
                trade_state_changed = True

            if trade_state == TradeState.PAYMENT_PENDING_CONFIRMATION:
                await self._transition(
                    trade,
                    TradeState.FUNDS_RECEIVED,
                    actor=actor,
                    reason_event=AuditEventType.PAYMENT_DETECTED,
                    reason_metadata=payment_detected_metadata,
                    using_db=using_db,
                )
                await self._transition(
                    trade,
                    TradeState.WAITING_DELIVERY,
                    actor=actor,
                    using_db=using_db,
                )
                trade_state_changed = True

        elif snapshot.status == ProviderPaymentStatus.EXPIRED:
            if trade_state not in {
                TradeState.EXPIRED,
                TradeState.CANCELLED,
                TradeState.RELEASED,
                TradeState.REFUNDED,
            }:
                await self._transition(
                    trade,
                    TradeState.EXPIRED,
                    actor=actor,
                    using_db=using_db,
                )
                trade_state_changed = True

        elif snapshot.status in {
            ProviderPaymentStatus.UNDERPAID,
            ProviderPaymentStatus.OVERPAID,
            ProviderPaymentStatus.WRONG_ASSET,
            ProviderPaymentStatus.WRONG_NETWORK,
            ProviderPaymentStatus.DUPLICATE,
            ProviderPaymentStatus.FAILED,
        }:
            if trade_state not in {
                TradeState.FAILED,
                TradeState.CANCELLED,
                TradeState.RELEASED,
                TradeState.REFUNDED,
            }:
                await self._transition(
                    trade,
                    TradeState.FAILED,
                    actor=actor,
                    using_db=using_db,
                )
                trade_state_changed = True

        return trade_state_changed

    async def mark_delivery_ready(
        self,
        *,
        trade_public_id: str,
        seller_discord_id: int,
        delivery_note: str,
    ) -> Trade:
        seller = await get_or_create_user(seller_discord_id)
        trade = await self._get_trade(trade_public_id)
        if not trade.seller or trade.seller_id != seller.id:
            raise PermissionDenied("Only the seller can mark delivery")

        state = TradeState(str(trade.state))
        if state not in {TradeState.WAITING_DELIVERY, TradeState.WAITING_BUYER_CONFIRMATION}:
            raise InvalidTradeTransition(f"Cannot mark delivery from state {state}")

        if state == TradeState.WAITING_DELIVERY:
            await self._transition(
                trade,
                TradeState.WAITING_BUYER_CONFIRMATION,
                actor=seller,
                reason_event=AuditEventType.DELIVERY_MARKED,
                reason_metadata={"note": delivery_note[:500]},
            )
        else:
            await self._audit(
                trade=trade,
                actor=seller,
                event_type=AuditEventType.DELIVERY_MARKED,
                metadata={"note": delivery_note[:500], "idempotent": True},
            )

        return await self._get_trade(trade_public_id)

    async def buyer_confirm_and_release(
        self,
        *,
        trade_public_id: str,
        buyer_discord_id: int,
        idempotency_key: str,
    ) -> Payout:
        buyer = await get_or_create_user(buyer_discord_id)
        trade = await self._get_trade(trade_public_id)
        if not trade.buyer or trade.buyer_id != buyer.id:
            raise PermissionDenied("Only the buyer can confirm receipt")

        return await self._execute_release(
            trade=trade,
            actor=buyer,
            idempotency_key=idempotency_key,
            reason_event=AuditEventType.BUYER_CONFIRMED,
            reason_metadata={"buyer_discord_id": buyer_discord_id},
            allow_from_states={TradeState.WAITING_BUYER_CONFIRMATION, TradeState.RELEASE_REQUESTED, TradeState.RELEASED},
        )

    async def open_dispute(
        self,
        *,
        trade_public_id: str,
        opened_by_discord_id: int,
        reason: str,
    ) -> Dispute:
        opener = await get_or_create_user(opened_by_discord_id)
        trade = await self._get_trade(trade_public_id)

        if trade.buyer_id != opener.id and trade.seller_id != opener.id:
            raise PermissionDenied("Only trade participants can open disputes")

        state = TradeState(str(trade.state))
        if state not in {
            TradeState.FUNDS_RECEIVED,
            TradeState.WAITING_DELIVERY,
            TradeState.WAITING_BUYER_CONFIRMATION,
            TradeState.RELEASE_REQUESTED,
            TradeState.DISPUTED,
        }:
            raise InvalidTradeTransition(f"Cannot open dispute from state {state}")

        if state != TradeState.DISPUTED:
            await self._transition(
                trade,
                TradeState.DISPUTED,
                actor=opener,
                reason_event=AuditEventType.DISPUTE_OPENED,
                reason_metadata={"reason": reason[:500]},
            )

        dispute = await Dispute.filter(trade=trade, status=DisputeStatus.OPEN).first()
        if not dispute:
            dispute = await Dispute.create(
                trade=trade,
                opened_by=opener,
                reason=reason[:2000],
                status=DisputeStatus.OPEN,
            )

        return dispute

    async def admin_manual_action(
        self,
        *,
        trade_public_id: str,
        admin_discord_id: int,
        action: str,
        note: str,
    ) -> Trade:
        if not is_admin_discord_user(admin_discord_id, self.settings):
            raise PermissionDenied("Admin action denied")

        admin = await get_or_create_user(admin_discord_id)
        trade = await self._get_trade(trade_public_id)

        normalized_action = action.strip().lower()
        if normalized_action == "release":
            await self._execute_release(
                trade=trade,
                actor=admin,
                idempotency_key=f"admin-release:{trade.public_id}",
                reason_event=AuditEventType.ADMIN_MANUAL_ACTION,
                reason_metadata={"action": "release", "note": note[:500]},
                allow_from_states={
                    TradeState.DISPUTED,
                    TradeState.WAITING_BUYER_CONFIRMATION,
                    TradeState.RELEASE_REQUESTED,
                    TradeState.RELEASED,
                },
            )
            await self._resolve_open_disputes(trade, admin, f"release: {note[:500]}")

        elif normalized_action == "refund":
            await self._execute_refund(trade=trade, admin=admin, note=note)
            await self._resolve_open_disputes(trade, admin, f"refund: {note[:500]}")

        elif normalized_action == "cancel":
            state = TradeState(str(trade.state))
            if state in {TradeState.RELEASED, TradeState.REFUNDED, TradeState.CANCELLED}:
                raise InvalidTradeTransition(f"Cannot cancel trade from state {state}")
            await self._transition(
                trade,
                TradeState.CANCELLED,
                actor=admin,
                reason_event=AuditEventType.ADMIN_MANUAL_ACTION,
                reason_metadata={"action": "cancel", "note": note[:500]},
            )

        else:
            raise ValidationError("Unknown admin action")

        return await self._get_trade(trade_public_id)

    async def mock_mark_payment_received(
        self,
        *,
        trade_public_id: str,
        admin_discord_id: int,
        tx_hash: str,
    ) -> PaymentRefreshResult:
        if not is_admin_discord_user(admin_discord_id, self.settings):
            raise PermissionDenied("Admin action denied")
        if self.settings.is_production:
            raise ValidationError("Mock payment simulation is forbidden in production")
        if not isinstance(self.provider, MockPaymentProvider):
            raise ValidationError("Mock payment simulation is only supported by mock provider")

        trade = await self._get_trade(trade_public_id)
        intent = await self._get_latest_payment_intent(trade)
        await self.provider.mark_payment_confirmed(
            intent.provider_intent_id,
            tx_hash=tx_hash,
            confirmations=self.settings.required_confirmations,
        )

        admin = await get_or_create_user(admin_discord_id)
        await self._audit(
            trade=trade,
            actor=admin,
            event_type=AuditEventType.ADMIN_MANUAL_ACTION,
            metadata={
                "action": "mock_mark_payment_received",
                "provider_intent_id": intent.provider_intent_id,
                "tx_hash": tx_hash,
            },
        )

        return await self.refresh_payment_status(
            trade_public_id=trade_public_id,
            actor_discord_id=admin_discord_id,
        )

    async def handle_webhook(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> bool:
        if not self.provider.verify_webhook_signature(payload, signature):
            raise PermissionDenied("Invalid webhook signature")

        event_payload = json.loads(payload.decode("utf-8"))
        event_id = str(event_payload["event_id"])
        try:
            async with in_transaction() as connection:
                webhook_event = await WebhookEvent.create(
                    provider=self.provider.name,
                    event_id=event_id,
                    signature_valid=True,
                    processed=False,
                    payload_json=event_payload,
                    using_db=connection,
                )

                result = await self.provider.apply_webhook_event(event_payload)
                intent = (
                    await PaymentIntent.filter(provider_intent_id=result.provider_intent_id)
                    .using_db(connection)
                    .select_for_update()
                    .first()
                )
                if not intent:
                    raise NotFoundError("Webhook references unknown payment intent")

                intent.status = PaymentRecordStatus(result.status.value)
                intent.confirmations = result.confirmations
                intent.required_confirmations = (
                    result.required_confirmations or intent.required_confirmations
                )
                intent.observed_tx_hash = result.tx_hash
                intent.observed_amount = result.observed_amount
                intent.failure_reason = result.reason
                intent.metadata_json = result.metadata
                await intent.save(using_db=connection)

                trade = await Trade.filter(id=intent.trade_id).using_db(connection).first()
                if not trade:
                    raise NotFoundError("Webhook references unknown trade")

                webhook_event.payment_intent = intent
                webhook_event.trade = trade
                webhook_event.processed = True
                webhook_event.processed_at = await self._now_utc()
                await webhook_event.save(using_db=connection)
        except IntegrityError:
            existing = await WebhookEvent.filter(event_id=event_id).first()
            trade = await Trade.filter(id=existing.trade_id).first() if existing and existing.trade_id else None
            if trade:
                await self._audit(
                    trade=trade,
                    actor=None,
                    event_type=AuditEventType.WEBHOOK_REPLAY_DROPPED,
                    metadata={"event_id": event_id},
                    idempotency_key=f"webhook-replay:{event_id}",
                )
            return False

        await self._audit(
            trade=trade,
            actor=None,
            event_type=AuditEventType.WEBHOOK_PROCESSED,
            metadata={"event_id": event_id, "provider_intent_id": intent.provider_intent_id},
        )

        await self.refresh_payment_status(trade_public_id=trade.public_id, actor_discord_id=None)
        return True

    async def get_trade(self, trade_public_id: str) -> Trade:
        return await self._get_trade(trade_public_id)

    async def _execute_refund(self, *, trade: Trade, admin: User, note: str) -> None:
        state = TradeState(str(trade.state))
        if state == TradeState.REFUNDED:
            return

        if state not in {
            TradeState.DISPUTED,
            TradeState.FUNDS_RECEIVED,
            TradeState.WAITING_DELIVERY,
            TradeState.WAITING_BUYER_CONFIRMATION,
            TradeState.REFUND_REQUESTED,
        }:
            raise InvalidTradeTransition(f"Cannot refund trade from state {state}")

        if state != TradeState.REFUND_REQUESTED:
            await self._transition(
                trade,
                TradeState.REFUND_REQUESTED,
                actor=admin,
                using_db=None,
            )

        intent = await self._get_latest_payment_intent(trade)
        refund_result = await self.provider.refund(
            provider_intent_id=intent.provider_intent_id,
            amount=trade.amount,
            asset=trade.asset,
            network=trade.network,
            idempotency_key=f"refund:{trade.public_id}",
        )

        if refund_result.status == ProviderPayoutStatus.COMPLETED:
            await self._transition(
                trade,
                TradeState.REFUNDED,
                actor=admin,
                reason_event=AuditEventType.ADMIN_MANUAL_ACTION,
                reason_metadata={"action": "refund", "note": note[:500]},
            )
        else:
            await self._transition(
                trade,
                TradeState.FAILED,
                actor=admin,
                reason_event=AuditEventType.PAYOUT_FAILED,
                reason_metadata={"action": "refund", "reason": refund_result.reason},
            )

    async def _execute_release(
        self,
        *,
        trade: Trade,
        actor: User,
        idempotency_key: str,
        reason_event: AuditEventType,
        reason_metadata: dict[str, Any],
        allow_from_states: set[TradeState],
    ) -> Payout:
        state = TradeState(str(trade.state))
        if state not in allow_from_states:
            raise InvalidTradeTransition(f"Cannot release from state {state}")

        if state == TradeState.RELEASED:
            existing_completed = await Payout.filter(trade=trade, status=PayoutRecordStatus.COMPLETED).first()
            if existing_completed:
                return existing_completed

        profile = await SellerPayoutProfile.filter(
            seller_id=trade.seller_id,
            provider=self.provider.name,
            is_active=True,
        ).first()
        if not profile:
            raise ValidationError("Seller payout profile is missing")

        destination = decrypt_text(profile.encrypted_payout_details, self.settings.payout_encryption_key)

        existing_payout = await Payout.filter(release_idempotency_key=idempotency_key).first()
        if existing_payout:
            if existing_payout.status == PayoutRecordStatus.COMPLETED:
                if TradeState(str(trade.state)) != TradeState.RELEASED:
                    await self._transition(trade, TradeState.RELEASED, actor=actor)
            return existing_payout

        if TradeState(str(trade.state)) != TradeState.RELEASE_REQUESTED:
            await self._transition(
                trade,
                TradeState.RELEASE_REQUESTED,
                actor=actor,
                reason_event=reason_event,
                reason_metadata=reason_metadata,
            )

        await self._audit(
            trade=trade,
            actor=actor,
            event_type=AuditEventType.PAYOUT_REQUESTED,
            metadata={"idempotency_key": idempotency_key},
            idempotency_key=idempotency_key,
        )

        payout_result = await self.provider.create_payout(
            PayoutRequest(
                idempotency_key=idempotency_key,
                amount=trade.amount,
                asset=trade.asset,
                network=trade.network,
                destination=destination,
            )
        )

        payout = await Payout.create(
            trade=trade,
            provider=self.provider.name,
            provider_payout_id=payout_result.provider_payout_id,
            release_idempotency_key=idempotency_key,
            status=PayoutRecordStatus(payout_result.status.value),
            amount=trade.amount,
            asset=trade.asset,
            network=trade.network,
            destination_masked=profile.payout_details_masked,
            failure_reason=payout_result.reason,
            metadata_json=payout_result.metadata,
        )

        if payout_result.status == ProviderPayoutStatus.COMPLETED:
            await self._transition(trade, TradeState.RELEASED, actor=actor)
            await self._audit(
                trade=trade,
                actor=actor,
                event_type=AuditEventType.PAYOUT_COMPLETED,
                metadata={
                    "provider_payout_id": payout_result.provider_payout_id,
                    "destination_masked": profile.payout_details_masked,
                },
                idempotency_key=idempotency_key,
            )
        else:
            await self._transition(trade, TradeState.FAILED, actor=actor)
            await self._audit(
                trade=trade,
                actor=actor,
                event_type=AuditEventType.PAYOUT_FAILED,
                metadata={
                    "provider_payout_id": payout_result.provider_payout_id,
                    "reason": payout_result.reason,
                },
                idempotency_key=idempotency_key,
            )

        return payout

    async def _resolve_open_disputes(self, trade: Trade, resolver: User, resolution: str) -> None:
        disputes = await Dispute.filter(trade=trade, status=DisputeStatus.OPEN).all()
        for dispute in disputes:
            dispute.status = DisputeStatus.RESOLVED
            dispute.resolution = resolution[:2000]
            dispute.resolved_by = resolver
            dispute.resolved_at = await self._now_utc()
            await dispute.save()

    async def _transition(
        self,
        trade: Trade,
        target_state: TradeState,
        *,
        actor: User | None,
        reason_event: AuditEventType | None = None,
        reason_metadata: Mapping[str, Any] | None = None,
        using_db=None,
    ) -> None:
        current_state = TradeState(str(trade.state))
        transition = ensure_transition(current_state, target_state)

        if transition.changed:
            trade.state = target_state
            await trade.save(using_db=using_db)

        await self._audit(
            trade=trade,
            actor=actor,
            event_type=AuditEventType.TRADE_STATE_CHANGED,
            metadata={
                "from_state": transition.old_state.value,
                "to_state": transition.new_state.value,
                "changed": transition.changed,
            },
        )

        if reason_event:
            await self._audit(
                trade=trade,
                actor=actor,
                event_type=reason_event,
                metadata=dict(reason_metadata or {}),
            )

    async def _audit(
        self,
        *,
        trade: Trade,
        actor: User | None,
        event_type: AuditEventType,
        metadata: Mapping[str, Any],
        idempotency_key: str | None = None,
    ) -> None:
        if idempotency_key:
            duplicate = await AuditEvent.filter(
                trade=trade,
                event_type=event_type,
                idempotency_key=idempotency_key,
            ).exists()
            if duplicate:
                return

        await AuditEvent.create(
            trade=trade,
            actor=actor,
            event_type=event_type,
            metadata_json=dict(metadata),
            idempotency_key=idempotency_key,
        )

    async def _get_trade(self, trade_public_id: str) -> Trade:
        trade = (
            await Trade.filter(public_id=trade_public_id)
            .prefetch_related("buyer", "seller", "creator")
            .first()
        )
        if not trade:
            raise NotFoundError(f"Trade {trade_public_id} was not found")
        return trade

    async def _get_latest_payment_intent(self, trade: Trade) -> PaymentIntent:
        intent = await PaymentIntent.filter(trade=trade).order_by("-created_at").first()
        if not intent:
            raise NotFoundError("Payment intent not found for trade")
        return intent

    async def _expires_at(self):
        now = await self._now_utc()
        return now + timedelta(minutes=self.settings.payment_timeout_minutes)

    async def _now_utc(self):
        return datetime.now(UTC)
