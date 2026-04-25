from __future__ import annotations

import uuid
from decimal import Decimal
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands
from web3 import Web3

from components.buttons import (
    BuyerConfirmationView,
    PaymentStatusView,
    SellerDeliveryView,
    TradeSelectRoles,
)
from domain.state_machine import InvalidTradeTransition
from domain.trade_states import TradeState
from enums import TradeRoles
from services import NotFoundError, PermissionDenied, ValidationError, get_trade_service
from settings import load_settings
from utils.dis import create_suc_embed
from utils.qr import build_qr_png

ALLOWED_ASSETS = {"USDT", "USDC", "ETH"}


class TradeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = load_settings()
        self.trade_service = get_trade_service()

    @app_commands.command(name="starttrade", description="Create a protected escrow trade")
    @app_commands.describe(
        user="Counterparty",
        amount="Trade amount",
        description="Trade description",
        asset="Payment asset",
        network="Network (e.g. ETH, ARB, BSC)",
    )
    @app_commands.checks.cooldown(2, 60.0)
    async def start_trade(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[float, 0.00000001, 1000000000.0],
        description: str,
        asset: str = "USDT",
        network: str = "ETH",
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Trades can only be started inside a server.",
                ephemeral=True,
            )
            return

        if user.bot:
            await interaction.response.send_message(
                "Counterparty must be a human user.",
                ephemeral=True,
            )
            return

        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You cannot start a trade with yourself.",
                ephemeral=True,
            )
            return

        selected_asset = asset.upper().strip()
        if selected_asset not in ALLOWED_ASSETS:
            await interaction.response.send_message(
                f"Unsupported asset '{selected_asset}'. Allowed: {', '.join(sorted(ALLOWED_ASSETS))}",
                ephemeral=True,
            )
            return

        selected_network = network.upper().strip()
        if len(description.strip()) < 5:
            await interaction.response.send_message(
                "Description must be at least 5 characters long.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        channel = await self.create_ticket_channel(interaction, user)
        await interaction.followup.send(
            f"Trade channel created: {channel.mention}",
            ephemeral=True,
        )

        role_view = TradeSelectRoles([interaction.user, user], selected_asset)
        role_embed = create_suc_embed(
            "Select trade roles",
            (
                f"**Description:** {description.strip()}\n"
                f"**Amount:** {amount}\n"
                f"**Asset/Network:** {selected_asset}/{selected_network}\n"
                f"Choose buyer and seller roles to continue."
            ),
        )
        await channel.send(embed=role_embed, view=role_view)

        await role_view.wait()
        if not role_view.roles_complete:
            await channel.send("Role selection timed out. Trade cancelled.")
            return

        buyer_member = role_view.roles.get(TradeRoles.BUYER)
        seller_member = role_view.roles.get(TradeRoles.SELLER)

        if buyer_member is None or seller_member is None:
            await channel.send("Could not determine buyer/seller roles. Trade cancelled.")
            return

        await channel.send(
            embed=create_suc_embed(
                "Seller payout details",
                (
                    f"{seller_member.mention}, send your payout wallet address now. "
                    "Only valid addresses are accepted."
                ),
            )
        )

        seller_wallet = await self.get_wallet_in_tries(channel, seller_member, tries=3)
        if not seller_wallet:
            await channel.send("Seller payout wallet collection failed. Trade cancelled.")
            return

        trade = await self.trade_service.create_trade(
            creator_discord_id=interaction.user.id,
            buyer_discord_id=buyer_member.id,
            seller_discord_id=seller_member.id,
            description=description.strip(),
            amount=Decimal(str(amount)),
            asset=selected_asset,
            network=selected_network,
        )

        await self.trade_service.set_seller_payout_details(
            trade_public_id=trade.public_id,
            seller_discord_id=seller_member.id,
            payout_wallet=seller_wallet,
        )

        payment_intent = await self.trade_service.create_payment_intent(
            trade_public_id=trade.public_id,
            actor_discord_id=interaction.user.id,
            idempotency_key=f"payment-intent:{trade.public_id}",
        )

        payment_embed = create_suc_embed(
            "Payment instructions",
            (
                f"**Trade ID:** `{trade.public_id}`\n"
                f"**Buyer:** {buyer_member.mention}\n"
                f"**Seller:** {seller_member.mention}\n"
                f"**Amount:** {payment_intent.amount} {payment_intent.asset}\n"
                f"**Network:** {payment_intent.network}\n"
                f"**Deposit address:** `{payment_intent.deposit_address}`\n"
                f"**Expires:** {payment_intent.expires_at}\n\n"
                "Send only the exact asset/network above. Wrong asset/network may be unrecoverable."
            ),
        )

        qr_bytes = build_qr_png(payment_intent.qr_payload)
        qr_file = discord.File(BytesIO(qr_bytes), filename=f"{trade.public_id}_payment_qr.png")

        payment_view = PaymentStatusView(
            on_check=self._build_payment_check_handler(trade.public_id),
            on_simulate=self._build_mock_paid_handler(trade.public_id),
        )

        await channel.send(embed=payment_embed, file=qr_file, view=payment_view)

    @start_trade.error
    async def on_start_trade_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"Rate limit: try again in {error.retry_after:.1f}s",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"Rate limit: try again in {error.retry_after:.1f}s",
                    ephemeral=True,
                )
            return

        if interaction.response.is_done():
            await interaction.followup.send(
                f"Failed to start trade: {error}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"Failed to start trade: {error}",
                ephemeral=True,
            )

    @app_commands.command(name="tradeadmin", description="Manual review action for escrow trades")
    @app_commands.describe(
        trade_id="Trade public ID (e.g. TRD-XXXXXXXXXXXX)",
        action="Manual action",
        note="Reason/note",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Release funds", value="release"),
            app_commands.Choice(name="Refund buyer", value="refund"),
            app_commands.Choice(name="Cancel trade", value="cancel"),
            app_commands.Choice(name="Mock: mark paid", value="mock_paid"),
        ]
    )
    async def trade_admin(
        self,
        interaction: discord.Interaction,
        trade_id: str,
        action: app_commands.Choice[str],
        note: str = "",
    ):
        if not self._is_strict_admin(interaction):
            await interaction.response.send_message(
                "Forbidden: admin authorization failed.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            if action.value == "mock_paid":
                result = await self.trade_service.mock_mark_payment_received(
                    trade_public_id=trade_id.strip(),
                    admin_discord_id=interaction.user.id,
                    tx_hash=f"mocktx-{uuid.uuid4().hex[:16]}",
                )
                await interaction.followup.send(
                    (
                        f"Mock payment applied. Provider status: {result.provider_status.value}. "
                        f"Trade state: {result.trade.state.value}"
                    ),
                    ephemeral=True,
                )
                if result.trade.state == TradeState.WAITING_DELIVERY:
                    await self._post_delivery_prompt(interaction.channel, result.trade.public_id)
                return

            updated_trade = await self.trade_service.admin_manual_action(
                trade_public_id=trade_id.strip(),
                admin_discord_id=interaction.user.id,
                action=action.value,
                note=note,
            )
            await interaction.followup.send(
                f"Admin action '{action.value}' applied. Trade state: {updated_trade.state.value}",
                ephemeral=True,
            )

        except (PermissionDenied, ValidationError, NotFoundError, InvalidTradeTransition) as err:
            await interaction.followup.send(f"Admin action failed: {err}", ephemeral=True)

    async def create_ticket_channel(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> discord.TextChannel:
        guild = interaction.guild
        if guild is None:
            raise RuntimeError("Guild is required")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel_name = f"escrow-{interaction.user.name[:10]}-{user.name[:10]}"
        return await guild.create_text_channel(channel_name, overwrites=overwrites)

    async def get_wallet_in_tries(
        self,
        channel: discord.TextChannel,
        member: discord.Member,
        *,
        tries: int,
    ) -> str | None:
        attempts = 0

        def check(message: discord.Message) -> bool:
            return message.channel.id == channel.id and message.author.id == member.id

        while attempts < tries:
            message = await self.bot.wait_for("message", check=check)
            content = message.content.strip()
            if Web3.is_address(content):
                return content

            attempts += 1
            await message.reply(f"Invalid wallet address. Remaining attempts: {tries - attempts}")

        await channel.send("Too many invalid attempts. Trade cancelled.")
        return None

    def _build_payment_check_handler(self, trade_public_id: str):
        async def _handler(interaction: discord.Interaction) -> str:
            result = await self.trade_service.refresh_payment_status(
                trade_public_id=trade_public_id,
                actor_discord_id=interaction.user.id,
            )

            if result.trade.state == TradeState.WAITING_DELIVERY and result.trade_state_changed:
                await self._post_delivery_prompt(interaction.channel, trade_public_id)
                return (
                    f"Payment confirmed with status {result.provider_status.value}. "
                    "Funds are locked. Seller has been asked to deliver."
                )

            return (
                f"Payment status: {result.provider_status.value}. "
                f"Current trade state: {result.trade.state.value}"
            )

        return _handler

    def _build_mock_paid_handler(self, trade_public_id: str):
        async def _handler(interaction: discord.Interaction) -> str:
            if not self._is_strict_admin(interaction):
                return "Forbidden: admin authorization failed."

            result = await self.trade_service.mock_mark_payment_received(
                trade_public_id=trade_public_id,
                admin_discord_id=interaction.user.id,
                tx_hash=f"mocktx-{uuid.uuid4().hex[:16]}",
            )

            if result.trade.state == TradeState.WAITING_DELIVERY:
                await self._post_delivery_prompt(interaction.channel, trade_public_id)

            return (
                f"Mock payment processed. Provider status: {result.provider_status.value}. "
                f"Trade state: {result.trade.state.value}"
            )

        return _handler

    async def _post_delivery_prompt(self, channel: discord.abc.Messageable | None, trade_public_id: str) -> None:
        if channel is None:
            return

        trade = await self.trade_service.get_trade(trade_public_id)
        if trade.seller_id is None or trade.buyer_id is None:
            return

        seller_view = SellerDeliveryView(
            seller_id=trade.seller.discord_id,
            on_delivered=self._build_seller_delivered_handler(trade_public_id),
        )
        await channel.send(
            embed=create_suc_embed(
                "Delivery step",
                (
                    f"Trade `{trade_public_id}`: Seller should deliver the item/service now.\n"
                    "After delivery, seller must click the button below."
                ),
            ),
            view=seller_view,
        )

    def _build_seller_delivered_handler(self, trade_public_id: str):
        async def _handler(interaction: discord.Interaction) -> str:
            trade = await self.trade_service.mark_delivery_ready(
                trade_public_id=trade_public_id,
                seller_discord_id=interaction.user.id,
                delivery_note="Seller marked delivered from Discord UI",
            )

            buyer_view = BuyerConfirmationView(
                buyer_id=trade.buyer.discord_id,
                on_confirm=self._build_buyer_confirm_handler(trade_public_id),
                on_dispute=self._build_buyer_dispute_handler(trade_public_id),
            )

            if interaction.channel is None:
                return "Delivery marked, but channel context is unavailable."

            await interaction.channel.send(
                embed=create_suc_embed(
                    "Buyer confirmation",
                    (
                        f"Trade `{trade_public_id}`: Buyer must confirm receipt before payout.\n"
                        "If there is a problem, buyer should open a dispute."
                    ),
                ),
                view=buyer_view,
            )

            return "Delivery marked. Buyer has been asked to confirm or dispute."

        return _handler

    def _build_buyer_confirm_handler(self, trade_public_id: str):
        async def _handler(interaction: discord.Interaction) -> str:
            payout = await self.trade_service.buyer_confirm_and_release(
                trade_public_id=trade_public_id,
                buyer_discord_id=interaction.user.id,
                idempotency_key=f"release:{trade_public_id}",
            )

            if payout.status.value == "COMPLETED":
                return "Receipt confirmed. Payout completed successfully."
            return f"Receipt confirmed. Payout status: {payout.status.value}"

        return _handler

    def _build_buyer_dispute_handler(self, trade_public_id: str):
        async def _handler(interaction: discord.Interaction) -> str:
            await self.trade_service.open_dispute(
                trade_public_id=trade_public_id,
                opened_by_discord_id=interaction.user.id,
                reason="Opened by buyer from Discord UI",
            )
            return "Dispute opened. Funds remain locked pending manual review."

        return _handler

    def _is_strict_admin(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in self.settings.admin_discord_ids:
            return False

        if interaction.guild is None:
            return True

        member = interaction.user
        return bool(getattr(member.guild_permissions, "administrator", False))


async def setup(bot):
    await bot.add_cog(TradeCog(bot))
