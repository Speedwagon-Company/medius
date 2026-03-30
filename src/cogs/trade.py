import discord
from discord.ext import commands
from discord import app_commands
from components.buttons import Confirm



class Trade(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name="starttrade", description="latency check")
    async def start_trade(self, interaction: discord.Interaction, user_id: str):
        guild = interaction.guild

        try:
            chan = await self.create_ticket_channel(interaction,user_id)
            view = Confirm()
            await chan.send("Select your role", view=view)
            
        except Exception as err:
            print(err)
            await interaction.response.send_message("error", ephemeral=True)
        

    async def create_ticket_channel(self, interaction: discord.Interaction, user_id: int) -> discord.TextChannel:
        guild = interaction.guild      
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False), 
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),

        }
        user = await self.bot.fetch_user(user_id)
        if user:
            overwrites[user] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        chan: discord.TextChannel = await guild.create_text_channel("test-chan", overwrites=overwrites)
        return chan

async def setup(bot):
    await bot.add_cog(Trade(bot))