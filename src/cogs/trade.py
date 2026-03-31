import discord
from discord.ext import commands
from discord import app_commands
from components.buttons import Confirm
from components.dropdowns import CryptoValueDropdownView
from utils.dis import create_suc_embed


class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name="starttrade", description="latency check")
    async def start_trade(self, interaction: discord.Interaction, user: discord.Member):
        guild = interaction.guild

        try:
            pass
            view = CryptoValueDropdownView(user)
            await interaction.response.send_message(view=view, ephemeral=True)
            # chan = await self.create_ticket_channel(interaction,user)
            # view = Confirm()
            # embed = create_suc_embed("Select your role")
            # print(embed)
            # await chan.send(view=view,embed=embed)
            
        except Exception as err:
            print(err)
            await interaction.response.send_message("error", ephemeral=True)
        



async def setup(bot):
    await bot.add_cog(TradeCog(bot))