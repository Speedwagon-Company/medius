import discord
from discord.ext import commands
from discord import app_commands

class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="latency check")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"ping {latency}ms хуйс")



async def setup(bot):
    await bot.add_cog(Commands(bot))