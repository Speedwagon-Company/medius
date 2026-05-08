import asyncio
import traceback

import discord
from discord import app_commands
from discord.ext import commands
from web3 import Web3

import utils.crypto as crypto
from cfg import SEND_WALLET_TRIES
from components.buttons import Confirm, ReleaseTradeMoney, TradeSelectRoles
from components.dropdowns import CryptoValueDropdownView
from db import (
    Transaction,
    attach_deposit_if_waiting,
    create_trade,
    create_transaction,
    get_transaction,
    list_transactions_by_statuses,
    try_update_transaction_status,
)
from enums import TradeRoles
from utils.dis import create_suc_embed
from utils.logs import send_transaction_log

WAITING_DEPOSIT = "WAITING_DEPOSIT"
DEPOSIT_SEEN = "DEPOSIT_SEEN"
READY_TO_RELEASE = "READY_TO_RELEASE"
RELEASING = "RELEASING"
RELEASED = "RELEASED"
CANCELED = "CANCELED"
FAILED = "FAILED"
EXPIRED = "EXPIRED"
NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"

WATCHER_RECOVERY_STATUSES = [WAITING_DEPOSIT, DEPOSIT_SEEN]
DEPOSIT_WAIT_TIMEOUT_SECONDS = 1800
DEPOSIT_CONFIRM_TIMEOUT_SECONDS = 300
WALLET_INPUT_TIMEOUT_SECONDS = 180

def _normalize_wallet(wallet: str) -> str:
    return wallet.strip().lower()


def _normalize_tx_hash(tx_hash: object) -> str:
    if hasattr(tx_hash, "hex"):
        return tx_hash.hex().strip().lower()
    return str(tx_hash).strip().lower()


class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.trade_tasks: dict[int, asyncio.Task] = {}

    async def cog_load(self):
        await self._recover_stale_releasing_transactions()
        await self._restore_pending_watchers()

    def cog_unload(self):
        for task in tuple(self.trade_tasks.values()):
            task.cancel()

    async def _restore_pending_watchers(self) -> None:
        pending_transactions = await list_transactions_by_statuses(WATCHER_RECOVERY_STATUSES)
        for transaction in pending_transactions:
            self._schedule_deposit_watcher(transaction.id)

    async def _recover_stale_releasing_transactions(self) -> None:
        releasing_transactions = await list_transactions_by_statuses([RELEASING])
        for transaction in releasing_transactions:
            moved = await try_update_transaction_status(transaction.id, RELEASING, NEEDS_RECONCILIATION)
            if not moved:
                continue

            warning = (
                f"[trade] transaction {transaction.id} recovered from {RELEASING} "
                f"to {NEEDS_RECONCILIATION}. Payout will NOT be retried automatically."
            )
            print(warning)

            channel = await self._resolve_text_channel(transaction.channel_id)
            if channel is None:
                continue

            try:
                await channel.send(
                    embed=create_suc_embed(
                        "Manual reconciliation required",
                        (
                            f"Transaction id: {transaction.id}\n"
                            f"State moved: {RELEASING} -> {NEEDS_RECONCILIATION}\n"
                            "Bot restarted during release flow. Automatic payout retry is disabled to avoid double-send."
                        ),
                    )
                )
                await send_transaction_log(
                    channel.guild,
                    create_suc_embed(
                        "Trade reconciliation alert",
                        (
                            f"Transaction id: {transaction.id}\n"
                            f"status: {NEEDS_RECONCILIATION}\n"
                            "Verify on-chain payout status before manual resolution."
                        ),
                    ),
                )
            except Exception as notify_error:
                print(
                    f"[trade] failed to notify reconciliation for transaction {transaction.id}: "
                    f"{type(notify_error).__name__}: {notify_error}"
                )

    def _schedule_deposit_watcher(self, transaction_id: int) -> None:
        existing = self.trade_tasks.get(transaction_id)
        if existing and not existing.done():
            return

        task = asyncio.create_task(self._watch_trade_transaction(transaction_id))
        self.trade_tasks[transaction_id] = task
        task.add_done_callback(lambda t, tx_id=transaction_id: self._on_trade_task_done(tx_id, t))

    def _on_trade_task_done(self, transaction_id: int, task: asyncio.Task) -> None:
        self.trade_tasks.pop(transaction_id, None)
        if task.cancelled():
            return
        err = task.exception()
        if err:
            traceback_text = "".join(traceback.format_exception(type(err), err, err.__traceback__))
            print(f"[trade] watcher failed for transaction {transaction_id}\n{traceback_text}")

    async def _resolve_text_channel(self, channel_id: int | None) -> discord.TextChannel | None:
        if channel_id is None:
            return None

        channel = self.bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel

        try:
            fetched = await self.bot.fetch_channel(channel_id)
        except Exception:
            return None
        return fetched if isinstance(fetched, discord.TextChannel) else None

    async def _watch_trade_transaction(self, transaction_id: int) -> None:
        transaction = await get_transaction(transaction_id)
        if transaction is None:
            return

        channel = await self._resolve_text_channel(transaction.channel_id)
        if channel is None:
            print(f"[trade] channel not found for transaction {transaction_id}")
            return

        try:
            tx_hash = transaction.hash
            if transaction.status == WAITING_DEPOSIT:
                expected_amount = transaction.expected_amount or crypto.AMOUNT_ETH
                min_value_wei = Web3.to_wei(expected_amount, "ether")
                tx = await asyncio.wait_for(
                    crypto.wait_for_transaction(
                        sender_wallet=transaction.sender_wallet,
                        recipient_wallet=transaction.escrow_wallet or crypto.RECIPIENT,
                        min_value_wei=min_value_wei,
                    ),
                    timeout=DEPOSIT_WAIT_TIMEOUT_SECONDS,
                )
                tx_hash = _normalize_tx_hash(tx.get("hash"))
                recieved = float(Web3.from_wei(tx["value"], "ether"))
                attached = await attach_deposit_if_waiting(transaction_id, tx_hash, recieved)
                if not attached:
                    await channel.send(
                        embed=create_suc_embed(
                            "Deposit ignored",
                            "Transaction was already processed or belongs to another trade.",
                        )
                    )
                    return
                transaction = await get_transaction(transaction_id)
                await channel.send(
                    embed=create_suc_embed(
                        "Deposit detected",
                        f"transaction hash: ```{tx_hash}```\nstatus: {DEPOSIT_SEEN}",
                    )
                )

            if transaction is None or transaction.status != DEPOSIT_SEEN:
                return

            if not tx_hash:
                await try_update_transaction_status(transaction_id, DEPOSIT_SEEN, FAILED)
                await channel.send(
                    embed=create_suc_embed("Deposit watcher failed", "Missing transaction hash in persisted state.")
                )
                return

            receipt = await asyncio.wait_for(
                crypto.W3.eth.wait_for_transaction_receipt(tx_hash),
                timeout=DEPOSIT_CONFIRM_TIMEOUT_SECONDS,
            )
            if receipt["status"] != 1:
                await try_update_transaction_status(transaction_id, DEPOSIT_SEEN, FAILED)
                await channel.send(
                    embed=create_suc_embed(
                        "Deposit failed",
                        f"transaction hash: ```{tx_hash}```\nstatus: failed",
                    )
                )
                return

            became_ready = await try_update_transaction_status(transaction_id, DEPOSIT_SEEN, READY_TO_RELEASE)
            if not became_ready:
                refreshed = await get_transaction(transaction_id)
                if not refreshed or refreshed.status != READY_TO_RELEASE:
                    return
                transaction = refreshed
            else:
                transaction = await get_transaction(transaction_id)
                if transaction is None:
                    return

            release_money = ReleaseTradeMoney(transaction.reciever_id)
            release_msg = await channel.send(
                embed=create_suc_embed(
                    "Deposit confirmed",
                    (
                        f"transaction hash: ```{tx_hash}```\n"
                        f"status: {READY_TO_RELEASE}\n"
                        f"{transaction.coin} recieved: {transaction.recieved}"
                    ),
                ),
                view=release_money,
            )
            release_money.message = release_msg
            await release_money.wait()

            if release_money.confirmed:
                await self.handle_confirm_money(transaction.id, transaction.recieved, transaction.reciever_wallet, channel)
                return

            if release_money.canceled:
                await self.handle_cancel_money(transaction.id, transaction.recieved, transaction.sender_wallet, channel)
                return

            expired = await try_update_transaction_status(transaction.id, READY_TO_RELEASE, EXPIRED)
            if expired:
                await channel.send(
                    embed=create_suc_embed(
                        "Release expired",
                        "Release window timed out. Trade was moved to EXPIRED.",
                    )
                )
        except asyncio.TimeoutError:
            expired = await try_update_transaction_status(transaction_id, WAITING_DEPOSIT, EXPIRED)
            if expired:
                await channel.send(
                    embed=create_suc_embed(
                        "Deposit timeout",
                        "No deposit detected within 30 minutes. Trade moved to EXPIRED.",
                    )
                )
        except asyncio.CancelledError:
            print(f"[trade] deposit watcher cancelled for transaction {transaction_id}")
            raise
        except Exception as err:
            await channel.send(embed=create_suc_embed("Deposit watcher failed", str(err)))
            await try_update_transaction_status(transaction_id, WAITING_DEPOSIT, FAILED)
            await try_update_transaction_status(transaction_id, DEPOSIT_SEEN, FAILED)
            try:
                await send_transaction_log(
                    channel.guild,
                    create_suc_embed(
                        "Watcher exception",
                        f"Transaction id: {transaction_id}\nError: {type(err).__name__}: {err}",
                    ),
                )
            except Exception:
                pass
            raise

    # TODO: refactor this piece of shit
    @app_commands.command(name="starttrade", description="latency check")
    async def start_trade(self, interaction: discord.Interaction, user: discord.Member):
        guild = interaction.guild

        try:
            view = CryptoValueDropdownView(user)
            await interaction.response.send_message(view=view, ephemeral=True)
            await view.wait()
            dropdown = view.children[0]
            selected_coin = dropdown.values[0]
            embed = create_suc_embed(
                title="Is it correct?",
                desc=f"**Coin:** {selected_coin} \n **Selected user**: {user.mention}",
            )

            view = Confirm(user)
            await interaction.followup.send(embed=embed, ephemeral=True, view=view)
            await view.wait()
            if not view.confirmed:
                return
            chan = await self.create_ticket_channel(interaction, user)
            trade = await create_trade(interaction.user.id, user.id)
            view = TradeSelectRoles([interaction.user, user], selected_coin)
            desc = f"**Coin:** {selected_coin} \n **Sender:** Not selected yet \n **Reciever:** Not selected yet"
            embed = create_suc_embed("Select your roles", desc)
            await chan.send(view=view, embed=embed)

            await view.wait()
            if view.canceled:
                await asyncio.sleep(10)
                await chan.delete()
                return
            roles = view.roles
            sender: discord.Member = roles[TradeRoles.SENDER]
            await chan.send(
                content=f"{sender.mention}",
                embed=create_suc_embed(
                    "All Roles Selected",
                    f"Now sender ({sender.display_name}) send your {selected_coin} wallet",
                ),
            )
            reciever: discord.Member = roles[TradeRoles.RECIEVER]

            def sender_check(m):
                return m.author == view.roles[TradeRoles.SENDER]

            def reciever_check(m):
                return m.author == view.roles[TradeRoles.RECIEVER]

            sender_wallet = await self.get_wallet_in_tries(SEND_WALLET_TRIES, sender_check)
            if not sender_wallet:
                return

            m = await chan.send(
                content=f"{reciever.mention}",
                embed=create_suc_embed(
                    "Valid wallet",
                    f"Now reciever ({reciever.display_name}) \nsend your wallet",
                ),
            )
            reciever_wallet = await self.get_wallet_in_tries(SEND_WALLET_TRIES, reciever_check)
            if not reciever_wallet:
                return

            escrow_wallet = _normalize_wallet(crypto.RECIPIENT)
            sender_wallet_norm = _normalize_wallet(sender_wallet)
            reciever_wallet_norm = _normalize_wallet(reciever_wallet)
            transaction: Transaction = await create_transaction(
                trade_id=trade.id,
                reciever_id=reciever.id,
                sender_id=sender.id,
                channel_id=chan.id,
                sender_wallet=sender_wallet_norm,
                reciever_wallet=reciever_wallet_norm,
                escrow_wallet=escrow_wallet,
                expected_amount=float(crypto.AMOUNT_ETH),
                recieved=0.0,
                coin=selected_coin,
                status=WAITING_DEPOSIT,
                hash=None,
            )

            await m.channel.send(
                content=f"{sender.mention}",
                embed=create_suc_embed(
                    "Deposit watcher started",
                    (
                        f"Trade command finished quickly.\n"
                        f"Trade id: {trade.id}\nTransaction id: {transaction.id}\n"
                        f"Now waiting for sender ({sender.display_name}) to send money to escrow\n"
                        f"wallet: ```{crypto.RECIPIENT}```\nstatus: {WAITING_DEPOSIT}"
                    ),
                ),
            )
            self._schedule_deposit_watcher(transaction.id)
            return

        except Exception as err:
            print(f"Тип ошибки: {type(err).__name__}")
            print(f"Текст ошибки: {str(err)}")
            print(f"Где произошло: {traceback.extract_tb(err.__traceback__)[-1].name}")
            print("\nПолный traceback:")
            traceback.print_exc()

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
        msg = None
        while i < tries:
            try:
                msg = await self.bot.wait_for("message", check=checker, timeout=WALLET_INPUT_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                return None

            if Web3.is_address(msg.content):
                wallet = msg.content
                return wallet
            i += 1
            await msg.reply(f"This is not correct wallet \nLeft tries {tries - i}")

        if wallet is None and msg is not None:
            await msg.reply("Too many mistakes trade is cancelled")
            await asyncio.sleep(5)
            await msg.channel.delete()
        return None

    async def handle_cancel_money(self, transaction_id: int, value, sender_wallet, chan: discord.TextChannel):
        locked = await try_update_transaction_status(transaction_id, READY_TO_RELEASE, RELEASING)
        if not locked:
            await chan.send("Payout state changed, refund was not started.")
            return

        try:
            await chan.send(embed=create_suc_embed("Sender canceled deal, transfering money to him"))
            tx = await crypto.sign_and_send(value, sender_wallet)
            msg = await chan.send(
                embed=create_suc_embed(
                    "Sent transaction",
                    f"Transaction hash: ```{tx.hex()}``` \nStatus: pending",
                )
            )
            recip = await asyncio.wait_for(crypto.W3.eth.wait_for_transaction_receipt(tx), 120)
            if recip["status"] == 1:
                await try_update_transaction_status(transaction_id, RELEASING, CANCELED)
                await msg.edit(
                    embed=create_suc_embed(
                        "Sent transaction",
                        f"Transaction hash: ```{tx.hex()}``` \nStatus: Success",
                    )
                )
                return
            await try_update_transaction_status(transaction_id, RELEASING, FAILED)
        except Exception:
            await try_update_transaction_status(transaction_id, RELEASING, FAILED)
            raise

    async def handle_confirm_money(self, transaction_id: int, value, reciever_wallet, chan):
        locked = await try_update_transaction_status(transaction_id, READY_TO_RELEASE, RELEASING)
        if not locked:
            await chan.send("Release already processed or no longer available.")
            return

        try:
            tx = await crypto.sign_and_send(value, reciever_wallet)
            msg = await chan.send(
                embed=create_suc_embed(
                    "Sent transaction",
                    f"Transaction hash: ```{tx.hex()}``` \nStatus: pending",
                )
            )
            recip = await asyncio.wait_for(crypto.W3.eth.wait_for_transaction_receipt(tx), 120)
            if recip["status"] == 1:
                await try_update_transaction_status(transaction_id, RELEASING, RELEASED)
                await msg.edit(
                    embed=create_suc_embed(
                        "Sent transaction",
                        f"Transaction hash: ```{tx.hex()}``` \nStatus: Success",
                    )
                )
                return
            await try_update_transaction_status(transaction_id, RELEASING, FAILED)
        except Exception:
            await try_update_transaction_status(transaction_id, RELEASING, FAILED)
            raise


async def setup(bot):
    await bot.add_cog(TradeCog(bot))
