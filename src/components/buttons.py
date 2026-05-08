
from enums import TradeRoles
import discord
from utils.dis import *


class Confirm(discord.ui.View):
    def __init__(self, selected_user):
        super().__init__()
        self.selected_user = selected_user
        self.confirmed = False

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # chan = await self.create_ticket_channel(interaction,self.selected_user)
        # view = TradeSelectRoles()
        # embed = create_suc_embed("Select your role")
        # await chan.send(view=view,embed=embed)
        await interaction.response.send_message(embed=create_suc_embed("Success"), ephemeral=True)
        self.confirmed = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=create_suc_embed("Canceled"), ephemeral=True)
        self.stop()



class TradeSelectRoles(discord.ui.View):
    def __init__(self, members, selectedCoin):
        super().__init__()
        self.value = None
        self.selectedCoin = selectedCoin
        self.roles = {}
        self.members = members
        self.canceled = False

    @discord.ui.button(label='Receiver', style=discord.ButtonStyle.green)
    async def receiver_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user in self.members:
            return await interaction.response.send_message("Youre not in this trade", ephemeral=True)
        self.roles[TradeRoles.RECIEVER] = interaction.user
        button.disabled = True
        sender = self.roles.get(TradeRoles.SENDER, None)
        if sender and sender.id == interaction.user.id:
            return await interaction.response.send_message("You alreade choose your role", ephemeral=True)
        await self.handle_inter(interaction)


    @discord.ui.button(label='Sender', style=discord.ButtonStyle.blurple)
    async def sender_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user in self.members:
            return await interaction.response.send_message("Youre not in this trade", ephemeral=True)
        self.roles[TradeRoles.SENDER] = interaction.user
        button.disabled = True
        reciever = self.roles.get(TradeRoles.RECIEVER, None)
        if reciever and reciever.id == interaction.user.id:
            return await interaction.response.send_message("You already choose your role", ephemeral=True)
        await self.handle_inter(interaction)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.canceled = True
        self.stop()
        await interaction.message.reply("Processing")
        await interaction.channel.send(embed=create_suc_embed(f"Trade canceled by {interaction.user.mention}", "Deleting channel in 10 seconds"))

    async def handle_inter(self, interaction: discord.Interaction):
        sender = self.roles.get(TradeRoles.SENDER, 'Not selected')
        receiver = self.roles.get(TradeRoles.RECIEVER, 'Not selected')

        if self.roles.get(TradeRoles.SENDER) and self.roles.get(TradeRoles.RECIEVER):
            # msg: discord.Message = await interaction.channel.send(embed=create_suc_embed("All roles selected, now continue to payment", "Status: waiting"))
            self.stop()

        embed = create_suc_embed("Select your role", f"**Coin:** {self.selectedCoin} \n **Sender:** {sender} \n **Reciever:** {receiver}")
        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

class ReleaseTradeMoney(discord.ui.View):
    def __init__(self, reciever_id: int):
        super().__init__(timeout=900)
        self.value = None
        self.reciever_id = reciever_id
        self.confirmed = False
        self.canceled = False
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    @discord.ui.button(label='Release', style=discord.ButtonStyle.green)
    async def release_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.reciever_id:
            if self.confirmed:
                await interaction.response.send_message("Release is already processing.", ephemeral=True)
                return

            self.confirmed = True
            for item in self.children:
                item.disabled = True
            self.stop()
            await interaction.response.send_message("Processing", ephemeral=True)
            if self.message:
                await self.message.edit(view=self)
            return await interaction.channel.send(embed=create_suc_embed("Realeasing money"))

        await interaction.response.send_message("You're not a reciever", ephemeral=True) 
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.canceled = True
        await interaction.response.send_message("Processing", ephemeral=True)
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)
        self.stop()
