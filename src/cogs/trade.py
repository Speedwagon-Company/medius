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
from db import create_trade, create_transaction, Transaction
import time
from utils.logs import send_transaction_log


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
            await view.wait()
            chan = await self.create_ticket_channel(interaction,user)
            print(await create_trade(interaction.user.id, user.id))# create here
            view = TradeSelectRoles([interaction.user, user], selected_coin)
            desc = f"**Coin:** {selected_coin} \n **Sender:** Not selected yet \n **Reciever:** Not selected yet"
            embed = create_suc_embed("Select your roles", desc)
            await chan.send(view=view,embed=embed)

            await view.wait()
            roles = view.roles
            await chan.send(embed=create_suc_embed("All Roles Selected", f"Now {view.roles[TradeRoles.SENDER].mention} send your {selected_coin} wallet"))
            sender: discord.Member = roles[TradeRoles.SENDER]
            reciever: discord.Member = roles[TradeRoles.RECIEVER]

            def sender_check(m):
                return m.author == view.roles[TradeRoles.SENDER]
            def reciever_check(m):
                return m.author == view.roles[TradeRoles.RECIEVER]

            sender_wallet = await self.get_wallet_in_tries(5, sender_check)

            m = await chan.send(embed=create_suc_embed(f"Valid wallet", f"Now {view.roles[TradeRoles.RECIEVER].mention} \nsend your wallet  "))
            reciever_wallet = await self.get_wallet_in_tries(5, reciever_check)
            
            m = await chan.send(embed=create_suc_embed(f"Valid wallet",f"Now waiting  for {view.roles[TradeRoles.SENDER].mention} to send money to mm \nwallet: 0x676320A4F2ccD0D6A8a56C0Ebf2AF1aa984A12fD"))
            transaction: Transaction = await create_transaction(
                reciever_id=roles[TradeRoles.RECIEVER].id,
                sender_id=roles[TradeRoles.SENDER].id,
                coin=selected_coin
                )
            await send_transaction_log(guild, create_suc_embed("Created transaction", f"Transaction id: {transaction.id}"))
            tx = await wait_for_transaction(sender_wallet)
            print("CONTINUE?")
            trans_msg = await m.channel.send(embed=create_suc_embed(f"Got transaction",f"Now waiting for it to confirm \ntransaction hash: {tx["hash"].hex()} \nstatus: pending"))
            recipent = W3.eth.wait_for_transaction_receipt(tx["hash"].hex())
            
            if recipent["status"] == 1:
                # await update_transaction_status(transaction.id, "CONFIRMED")
                release_money = ReleaseTradeMoney(view.roles[TradeRoles.RECIEVER])
                await send_transaction_log(guild, create_suc_embed("Updated transaction", f"Transaction id: {transaction.id} \nTransaction hash: {transaction.hash} \nTransaction status: {transaction.status}"))
                await trans_msg.edit(embed=create_suc_embed(f"Got transaction",f"Now waiting for it to confirm \ntransaction hash: {tx["hash"].hex()} \nstatus: success"), view=release_money)
                await release_money.wait()
                if not release_money.confirmed:
                    self.handle_cancel_money()
                    return
                
                await self.handle_confirm_money(reciever_wallet, chan)
                # print("msg", reciever_wallet.content)
                # tx = sign_and_send(0.001, reciever_wallet.content)
                # msg = await chan.send(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: pending"))
                # recip = W3.eth.wait_for_transaction_receipt(tx)
                # if recip["status"] == 1:
                #     await msg.edit(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: Success"))
            else:
                # await update_transaction_status(transaction.id, "FAILED")
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

    async def get_wallet_in_tries(self, tries, checker):
        i = 0
        wallet = None
        while i < tries:
            msg = await self.bot.wait_for("message", check=checker)
            if Web3.is_address(msg.content):
                wallet = msg.content
                return wallet
            else:
                i += 1
                await msg.reply(f"This is not correct wallet \nLeft tries {tries - i}")
            
        if wallet is None:
            await msg.reply("Too many mistakes trade is cancelled")
            time.sleep(5)
            await msg.channel.delete()
            return

    async def handle_cancel_money(self, sender_wallet, chan: discord.TextChannel):
        await chan.send(embed=create_suc_embed("Sender canceled deal, transfering money to him"))


    async def handle_confirm_money(self, reciever_wallet, chan):
        print("msg", reciever_wallet)
        tx = sign_and_send(0.001, reciever_wallet)
        msg = await chan.send(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: pending"))
        recip = W3.eth.wait_for_transaction_receipt(tx)
        if recip["status"] == 1:
            await msg.edit(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: Success"))

async def setup(bot):
    await bot.add_cog(TradeCog(bot))