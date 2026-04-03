import discord
from discord.ext import commands
from discord import app_commands
from utils.html2p import render_profile
import os


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="get your profile info")
    async def profile(self, interaction: discord.Interaction):
        member = interaction.user
        if member.avatar:
            filename = f"{member.id}_avatar.png"
            filepath = f"users_pfp/{filename}"
            await member.avatar.save(filepath)
            profile_file_path = render_profile(filename, member.id)
            await interaction.response.send_message(file=discord.File(profile_file_path))
            os.remove(filepath)
            os.remove(profile_file_path)



async def setup(bot):
    await bot.add_cog(Profile(bot))