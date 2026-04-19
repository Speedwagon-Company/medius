import discord
from discord.ext import commands
from discord import app_commands
from components.buttons import TradeSelectRoles, Confirm, ReleaseTradeMoney
from components.dropdowns import CryptoValueDropdownView
from utils.dis import create_suc_embed
from enums import TradeRoles
from web3 import Web3
from cfg import SEND_WALLET_TRIES
from utils.crypto import wait_for_transaction, W3, sign_and_send
import time


class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # TODO: refactor this piece of shit
    @app_commands.command(name="starttrade", description="latency check")
    async def start_trade(self, interaction: discord.Interaction, user: discord.Member):
        guild = interaction.guild

        try:
            pass
            view = CryptoValueDropdownView(user)
            msg = await interaction.response.send_message(view=view, ephemeral=True)
            await view.wait()
            dropdown = view.children[0]
            selected_coin = dropdown.values[0]
            embed = create_suc_embed(
                title="Is it correct?",
                desc=f"**Coin:** {selected_coin} \n **Selected user**: {user.mention}")
            
            view = Confirm(user) 
            await interaction.followup.send(embed=embed, ephemeral=True, view=view)
            # await interaction.followup.edit_message(message_id=msg.id embed=embed, view=view)
            await view.wait()
            chan = await self.create_ticket_channel(interaction,user)

            view = TradeSelectRoles([interaction.user, user], selected_coin)
            desc = f"**Coin:** {selected_coin} \n **Sender:** Not selected yet \n **Reciever:** Not selected yet"
            embed = create_suc_embed("Select your roles", desc)
            await chan.send(view=view,embed=embed)

            await view.wait()
            await chan.send(embed=create_suc_embed("All Roles Selected", f"Now {view.roles[TradeRoles.SENDER].mention} send your {selected_coin} wallet"))
            def sender_check(m):
                return m.author == view.roles[TradeRoles.SENDER]
            i = 0
            sender_wallet = None
            while i < SEND_WALLET_TRIES:
                msg = await self.bot.wait_for("message", check=sender_check)
                if Web3.is_address(msg.content):
                    sender_wallet = msg.content
                    break
                else:
                    await msg.reply("This is not correct wallet")
                    i += 1
            
            if sender_wallet is None:
                await chan.send("Too many mistakes trade is cancelled")
                time.sleep(5)
                chan.delete()
                return

            m = await chan.send(embed=create_suc_embed(f"Valid wallet", f"Now {view.roles[TradeRoles.RECIEVER].mention} \nsend your wallet  "))
            def reciever_check(m):
                return m.author == view.roles[TradeRoles.RECIEVER]
            reciever_wallet = await self.bot.wait_for("message", check=reciever_check)
            m = await chan.send(embed=create_suc_embed(f"Valid wallet",f"Now waiting  for {view.roles[TradeRoles.SENDER].mention} to send money to mm \nwallet: 0x676320A4F2ccD0D6A8a56C0Ebf2AF1aa984A12fD"))
            tx = await wait_for_transaction(sender_wallet)
            trans_msg = await m.channel.send(embed=create_suc_embed(f"Got transaction",f"Now waiting for it to confirm \ntransaction hash: {tx["hash"].hex()} \nstatus: pending"))
            recipent = W3.eth.wait_for_transaction_receipt(tx["hash"].hex())
            if recipent["status"] == 1:
                release_money = ReleaseTradeMoney(view.roles[TradeRoles.RECIEVER])
                await trans_msg.edit(embed=create_suc_embed(f"Got transaction",f"Now waiting for it to confirm \ntransaction hash: {tx["hash"].hex()} \nstatus: success"), view=release_money)
                await release_money.wait()
                print("msg", reciever_wallet.content)
                tx = sign_and_send(0.001, reciever_wallet.content)
                msg = await chan.send(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: pending"))
                recip = W3.eth.wait_for_transaction_receipt(tx)
                if recip["status"] == 1:
                    await msg.edit(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: Success"))
            else:
                await trans_msg.edit(content=f"Got transaction, now waiting for {view.roles[TradeRoles.RECIEVER].mention} to confirm \nstatus: failed")
            
        except Exception as err:
            print(err)
            # await interaction.response.send_message("error", ephemeral=True)
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


async def setup(bot):
    await bot.add_cog(TradeCog(bot))