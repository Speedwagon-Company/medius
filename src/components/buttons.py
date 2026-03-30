# This example requires the 'message_content' privileged intent to function.

from discord.ext import commands
from enums import TradeRoles
import discord



class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.roles = {}

    @discord.ui.button(label='Receiver', style=discord.ButtonStyle.green)
    async def receiver_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.roles[TradeRoles.RECIEVER] = interaction.user
        button.disabled = True
        sender = self.roles.get(TradeRoles.SENDER, None)
        if sender and sender.id == interaction.user.id:
            return await interaction.response.send_message("You alreade choose your role", ephemeral=True)
        await self.handle_inter(interaction)


    @discord.ui.button(label='Sender', style=discord.ButtonStyle.blurple)
    async def sender_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.roles[TradeRoles.SENDER] = interaction.user
        button.disabled = True
        reciever = self.roles.get(TradeRoles.RECIEVER, None)
        if reciever and reciever.id == interaction.user.id:
            return await interaction.response.send_message("You already choose your role", ephemeral=True)
        await self.handle_inter(interaction)

    
    async def handle_inter(self, interaction: discord.Interaction):
        sender = self.roles.get(TradeRoles.SENDER, 'Not selected')
        receiver = self.roles.get(TradeRoles.RECIEVER, 'Not selected')

        if self.roles.get(TradeRoles.SENDER) and self.roles.get(TradeRoles.RECIEVER):
            await interaction.channel.send("All roles selected, now continue to payment \n status: waiting")

        await interaction.response.edit_message(
            content=f"Reciever = {receiver}\nSender = {sender}", 
            view=self
        )
