from __future__ import annotations

import discord


class CryptoValueDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="USDT", description="Tether USD"),
            discord.SelectOption(label="ETH", description="Ether"),
            discord.SelectOption(label="USDC", description="USD Coin"),
        ]
        super().__init__(
            placeholder="Choose payment asset",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.stop()


class CryptoValueDropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(CryptoValueDropdown())
