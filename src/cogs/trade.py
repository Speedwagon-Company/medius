import discord, traceback
from discord.ext import commands
from discord import app_commands
from components.buttons import TradeSelectRoles, Confirm, ReleaseTradeMoney
from components.dropdowns import CryptoValueDropdownView
from utils.dis import create_suc_embed
from enums import TradeRoles
from web3 import Web3
from cfg import SEND_WALLET_TRIES
from utils.crypto import wait_for_transaction, W3, sign_and_send, TRANSACTIONS
from db import create_trade, create_transaction, Transaction, update_transaction, update_transaction_status
import time, asyncio
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
            embed = await create_suc_embed(
                title="Is it correct?",
                desc=f"**Coin:** {selected_coin} \n **Selected user**: {user.mention}")
            
            view = Confirm(user) 
            await interaction.followup.send(embed=embed, ephemeral=True, view=view)
            await view.wait()
            if not view.confirmed:
                return
            chan = await self.create_ticket_channel(interaction,user)
            print(await create_trade(interaction.user.id, user.id))# create here
            view = TradeSelectRoles([interaction.user, user], selected_coin)
            desc = f"**Coin:** {selected_coin} \n **Sender:** Not selected yet \n **Reciever:** Not selected yet"
            embed = await create_suc_embed("Select your roles", desc)
            await chan.send(view=view,embed=embed)

            await view.wait()
            if view.canceled:
                await asyncio.sleep(10)
                await chan.delete()
            roles = view.roles
<<<<<<< HEAD
            await chan.send(embed=await create_suc_embed("All Roles Selected", f"Now {view.roles[TradeRoles.SENDER].mention} send your {selected_coin} wallet"))
=======
>>>>>>> main
            sender: discord.Member = roles[TradeRoles.SENDER]
            await chan.send(content=f"{sender.mention}", embed=create_suc_embed("All Roles Selected", f"Now sender ({sender.display_name}) send your {selected_coin} wallet"))
            reciever: discord.Member = roles[TradeRoles.RECIEVER]

            def sender_check(m):
                return m.author == view.roles[TradeRoles.SENDER]
            def reciever_check(m):
                return m.author == view.roles[TradeRoles.RECIEVER]

            sender_wallet = await self.get_wallet_in_tries(5, sender_check)

<<<<<<< HEAD
            m = await chan.send(embed=await create_suc_embed(f"Valid wallet", f"Now {view.roles[TradeRoles.RECIEVER].mention} \nsend your wallet  "))
            reciever_wallet = await self.get_wallet_in_tries(5, reciever_check)
            
            m = await chan.send(embed=await create_suc_embed(f"Valid wallet",f"Now waiting  for {view.roles[TradeRoles.SENDER].mention} to send money to mm \nwallet: 0x676320A4F2ccD0D6A8a56C0Ebf2AF1aa984A12fD"))
=======
            m = await chan.send(content=f"{reciever.mention}", embed=create_suc_embed(f"Valid wallet", f"Now reciever ({reciever.display_name}) \nsend your wallet  "))
            reciever_wallet = await self.get_wallet_in_tries(5, reciever_check)
            
            m = await chan.send(content=f"{sender.mention}", embed=create_suc_embed(f"Valid wallet",f"Now waiting  for sender ({sender.display_name}) to send money to mm \nwallet: ```0x676320A4F2ccD0D6A8a56C0Ebf2AF1aa984A12fD```"))
            tx = await wait_for_transaction(sender_wallet)
>>>>>>> main
            transaction: Transaction = await create_transaction(
                reciever_id=roles[TradeRoles.RECIEVER].id,
                sender_id=roles[TradeRoles.SENDER].id,
                sender_wallet=sender_wallet,
                reciever_wallet=reciever_wallet,
                coin=selected_coin,
                hash=tx["hash"].hex()
                )
<<<<<<< HEAD
            await send_transaction_log(guild, await create_suc_embed("Created transaction", f"Transaction id: {transaction.id}"))
            tx = await wait_for_transaction(sender_wallet)
            print("CONTINUE?")
            trans_msg = await m.channel.send(embed=await create_suc_embed(f"Got transaction",f"Now waiting for it to confirm \ntransaction hash: {tx["hash"].hex()} \nstatus: pending"))
=======
            await send_transaction_log(guild, create_suc_embed("Created transaction", f"Transaction id: {transaction.id} \nHash: ```{tx["hash"].hex()}```"))
            print("CONTINUE?")
            trans_msg = await m.channel.send(embed=create_suc_embed(f"Got transaction",f"Now waiting for it to confirm \ntransaction hash: ```{tx["hash"].hex()}``` \nstatus: pending"))
>>>>>>> main
            recipent = await W3.eth.wait_for_transaction_receipt(tx["hash"].hex())
            transaction_info = await W3.eth.get_transaction(tx["hash"].hex())
            print(transaction_info)
            value = Web3.from_wei(transaction_info["value"], "ether")
            # await update_transaction(transaction.id, recieved=value)
            if recipent["status"] == 1:
                await update_transaction_status(transaction.id, "CONFIRMED")
                release_money = ReleaseTradeMoney(view.roles[TradeRoles.RECIEVER])
<<<<<<< HEAD
                await send_transaction_log(guild, await create_suc_embed("Updated transaction", f"Transaction id: {transaction.id} \nTransaction hash: {transaction.hash} \nTransaction status: {transaction.status}"))
                await trans_msg.edit(embed=await create_suc_embed(f"Got transaction",f"Now waiting for it to confirm \ntransaction hash: {tx["hash"].hex()} \n{selected_coin} recieved: {value} \nstatus: success"), view=release_money)
=======
                await send_transaction_log(guild, create_suc_embed("Updated transaction", f"Transaction id: {transaction.id} \nTransaction hash: ```{transaction.hash}``` \nTransaction status: {transaction.status}"))
                await trans_msg.edit(embed=create_suc_embed(f"Got transaction",f"Now waiting for it to confirm \ntransaction hash: ```{tx["hash"].hex()}``` \n{selected_coin} recieved: {value} \nstatus: success"), view=release_money)
>>>>>>> main
                await release_money.wait()
                if not release_money.confirmed:
                    await self.handle_cancel_money(value, sender_wallet, chan)
                    return
                
                await self.handle_confirm_money(value,reciever_wallet, chan)
                # print("msg", reciever_wallet.content)
                # tx = sign_and_send(0.001, reciever_wallet.content)
                # msg = await chan.send(embed=await create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: pending"))
                # recip = W3.eth.wait_for_transaction_receipt(tx)
                # if recip["status"] == 1:
                #     await msg.edit(embed=await create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: Success"))
            else:
                # await update_transaction_status(transaction.id, "FAILED")
                await trans_msg.edit(content=f"Got transaction, now waiting for {view.roles[TradeRoles.RECIEVER].mention} to confirm \nstatus: failed")
            
        except Exception as err:
            print(f"Тип ошибки: {type(err).__name__}")
            print(f"Текст ошибки: {str(err)}")
            print(f"Где произошло: {traceback.extract_tb(err.__traceback__)[-1].name}")
            print("\nПолный traceback:")
            traceback.print_exc()
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

    async def handle_cancel_money(self, value,sender_wallet, chan: discord.TextChannel):
        await chan.send(embed=await create_suc_embed("Sender canceled deal, transfering money to him"))
        tx = await sign_and_send(value, sender_wallet)
        print("@@@", tx, value, sender_wallet)
<<<<<<< HEAD
        msg = await chan.send(embed=await create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: pending"))
        recip = await asyncio.wait_for(W3.eth.wait_for_transaction_receipt(tx), 120)
        print("after", recip)
        if recip["status"] == 1:
            await msg.edit(embed=await create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: Success"))
=======
        msg = await chan.send(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: ```{tx.hex()}``` \nStatus: pending"))
        recip = await asyncio.wait_for(W3.eth.wait_for_transaction_receipt(tx), 120)
        print("after", recip)
        if recip["status"] == 1:
            await msg.edit(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: ```{tx.hex()}``` \nStatus: Success"))
>>>>>>> main


    async def handle_confirm_money(self, value,reciever_wallet, chan):
        print("msg", reciever_wallet)
        tx = await sign_and_send(value, reciever_wallet)
<<<<<<< HEAD
        msg = await chan.send(embed=await create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: pending"))
        recip = await asyncio.wait_for(W3.eth.wait_for_transaction_receipt(tx), 120)
        if recip["status"] == 1:
            await msg.edit(embed=await create_suc_embed(f"Sent transaction", f"Transaction hash: {tx.hex()} \nStatus: Success"))
=======
        msg = await chan.send(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: ```{tx.hex()}``` \nStatus: pending"))
        recip = await asyncio.wait_for(W3.eth.wait_for_transaction_receipt(tx), 120)
        if recip["status"] == 1:
            await msg.edit(embed=create_suc_embed(f"Sent transaction", f"Transaction hash: ```{tx.hex()}``` \nStatus: Success"))
>>>>>>> main

async def setup(bot):
    await bot.add_cog(TradeCog(bot))