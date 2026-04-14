import discord
from components.buttons import Confirm
from utils.dis import create_suc_embed


class CryptoValueDropdown(discord.ui.Select):
    def __init__(self, user):
        self.user = user 

        options = [
            discord.SelectOption(label='BTC', description='', emoji='🟥'),
            discord.SelectOption(label='Litecoin', description='', emoji='🟩'),
            discord.SelectOption(label='Ton', description='', emoji='🟦'),
        ]

        super().__init__(placeholder='Choose coin', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.stop()
        # await interaction.response.send_message(embed=embed, view=view,ephemeral=True)


class CryptoValueDropdownView(discord.ui.View):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.add_item(CryptoValueDropdown(user))