from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord

from enums import TradeRoles
from utils.dis import create_suc_embed


class TradeSelectRoles(discord.ui.View):
    def __init__(self, members: list[discord.Member], selected_coin: str):
        super().__init__(timeout=300)
        self.selected_coin = selected_coin
        self.roles: dict[TradeRoles, discord.Member] = {}
        self.members = members

    @property
    def roles_complete(self) -> bool:
        return TradeRoles.BUYER in self.roles and TradeRoles.SELLER in self.roles

    @discord.ui.button(label="Buyer", style=discord.ButtonStyle.blurple)
    async def buyer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.members:
            await interaction.response.send_message("You are not part of this trade", ephemeral=True)
            return

        if self.roles.get(TradeRoles.SELLER) and self.roles[TradeRoles.SELLER].id == interaction.user.id:
            await interaction.response.send_message(
                "You already selected seller role", ephemeral=True
            )
            return

        self.roles[TradeRoles.BUYER] = interaction.user
        button.disabled = True
        await self._render(interaction)

    @discord.ui.button(label="Seller", style=discord.ButtonStyle.green)
    async def seller_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.members:
            await interaction.response.send_message("You are not part of this trade", ephemeral=True)
            return

        if self.roles.get(TradeRoles.BUYER) and self.roles[TradeRoles.BUYER].id == interaction.user.id:
            await interaction.response.send_message(
                "You already selected buyer role", ephemeral=True
            )
            return

        self.roles[TradeRoles.SELLER] = interaction.user
        button.disabled = True
        await self._render(interaction)

    async def _render(self, interaction: discord.Interaction) -> None:
        buyer = self.roles.get(TradeRoles.BUYER, "Not selected")
        seller = self.roles.get(TradeRoles.SELLER, "Not selected")
        embed = create_suc_embed(
            "Select roles",
            f"**Asset:** {self.selected_coin}\n**Buyer:** {buyer}\n**Seller:** {seller}",
        )
        await interaction.response.edit_message(embed=embed, view=self)

        if self.roles_complete:
            self.stop()


class PaymentStatusView(discord.ui.View):
    def __init__(
        self,
        *,
        on_check: Callable[[discord.Interaction], Awaitable[str]],
        on_simulate: Callable[[discord.Interaction], Awaitable[str]] | None = None,
    ):
        super().__init__(timeout=900)
        self._on_check = on_check
        self._on_simulate = on_simulate

    @discord.ui.button(label="Check payment", style=discord.ButtonStyle.blurple)
    async def check_payment_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        message = await self._on_check(interaction)
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="Admin: mark paid (mock)", style=discord.ButtonStyle.gray)
    async def simulate_paid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._on_simulate is None:
            await interaction.response.send_message(
                "Manual simulation is disabled for this provider", ephemeral=True
            )
            return

        message = await self._on_simulate(interaction)
        await interaction.response.send_message(message, ephemeral=True)


class SellerDeliveryView(discord.ui.View):
    def __init__(
        self,
        *,
        seller_id: int,
        on_delivered: Callable[[discord.Interaction], Awaitable[str]],
    ):
        super().__init__(timeout=900)
        self._seller_id = seller_id
        self._on_delivered = on_delivered

    @discord.ui.button(label="Seller: mark delivered", style=discord.ButtonStyle.green)
    async def delivered_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self._seller_id:
            await interaction.response.send_message("Only seller can use this button", ephemeral=True)
            return

        message = await self._on_delivered(interaction)
        await interaction.response.send_message(message, ephemeral=True)


class BuyerConfirmationView(discord.ui.View):
    def __init__(
        self,
        *,
        buyer_id: int,
        on_confirm: Callable[[discord.Interaction], Awaitable[str]],
        on_dispute: Callable[[discord.Interaction], Awaitable[str]],
    ):
        super().__init__(timeout=900)
        self._buyer_id = buyer_id
        self._on_confirm = on_confirm
        self._on_dispute = on_dispute

    @discord.ui.button(label="Buyer: confirm receipt", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self._buyer_id:
            await interaction.response.send_message("Only buyer can confirm receipt", ephemeral=True)
            return

        message = await self._on_confirm(interaction)
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="Buyer: open dispute", style=discord.ButtonStyle.red)
    async def dispute_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self._buyer_id:
            await interaction.response.send_message("Only buyer can open dispute", ephemeral=True)
            return

        message = await self._on_dispute(interaction)
        await interaction.response.send_message(message, ephemeral=True)
