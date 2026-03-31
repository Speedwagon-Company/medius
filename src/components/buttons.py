
from enums import TradeRoles
import discord
from utils.dis import *


class ConfirmStartTrade(discord.ui.View):
    def __init__(self, selected_user):
        super().__init__()
        self.selected_user = selected_user

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        chan = await self.create_ticket_channel(interaction,self.selected_user)
        view = Confirm()
        embed = create_suc_embed("Select your role")
        await chan.send(view=view,embed=embed)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    async def create_ticket_channel(self, interaction: discord.Interaction, user: discord.Member) -> discord.TextChannel:
        guild = interaction.guild      
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False), 
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),

        }
        
        if user:
            overwrites[user] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        chan: discord.TextChannel = await guild.create_text_channel("test-chan", overwrites=overwrites)
        return chan

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
            await interaction.channel.send(embed=create_suc_embed("All roles selected, now continue to payment", "Status: waiting"))

        embed = create_suc_embed("Select your role", f"Sender: {sender} \n Reciever: {receiver}")
        await interaction.response.edit_message(
            embed=embed,
            view=self
        )
