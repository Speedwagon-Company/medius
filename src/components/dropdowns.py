import discord
from components.buttons import ConfirmStartTrade
from utils.dis import create_suc_embed


class CryptoValueDropdown(discord.ui.Select):
    def __init__(self, user):
        self.user = user 
        # Set the options that will be presented inside the dropdown
        options = [
            discord.SelectOption(label='BTC', description='', emoji='🟥'),
            discord.SelectOption(label='Litecoin', description='', emoji='🟩'),
            discord.SelectOption(label='Ton', description='', emoji='🟦'),
        ]

        super().__init__(placeholder='Choose coin', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view = ConfirmStartTrade(self.user) 
        embed = create_suc_embed(
            title="Is it correct?",
            desc=f"**Coin:** {self.values[0]} \n **Selected user**: {self.user.mention}")
 
        await interaction.response.send_message(embed=embed, view=view,ephemeral=True)


class CryptoValueDropdownView(discord.ui.View):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.add_item(CryptoValueDropdown(user))