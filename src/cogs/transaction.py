import discord
from discord import app_commands
from discord.ext import commands

from db import get_transaction_by_hash


class TransactionCog(commands.Cog):
    transaction = app_commands.Group(
        name="transaction",
        description="Transaction-related commands",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _build_explorer_url(tx_hash: str, network: str | None, coin: str | None) -> str:
        network_key = (network or "").strip().lower()
        coin_key = (coin or "").strip().lower()

        # Keep this map small and explicit for current coin labels used in the project.
        if network_key in {"eth", "ethereum", "erc20"} or coin_key in {"eth", "ethereum", "erc20", "usdt", "usdc"}:
            return f"https://etherscan.io/tx/{tx_hash}"
        if network_key in {"bnb", "bsc"} or coin_key in {"bnb", "bsc"}:
            return f"https://bscscan.com/tx/{tx_hash}"
        if network_key in {"matic", "polygon"} or coin_key in {"matic", "polygon"}:
            return f"https://polygonscan.com/tx/{tx_hash}"

        # Fallback: still provide a clickable URL even if network is unknown.
        return f"https://etherscan.io/tx/{tx_hash}"

    @staticmethod
    def _format_party(wallet: str | None, user_id: int | None) -> str:
        wallet_part = wallet or "N/A"
        mention_part = f"<@{user_id}>" if user_id else "N/A"
        return f"Wallet: `{wallet_part}`\nDiscord: {mention_part}"

    @transaction.command(name="info", description="Show transaction details by hash")
    @app_commands.describe(tx_hash="Blockchain transaction hash")
    async def info(self, interaction: discord.Interaction, tx_hash: str):
        normalized_hash = tx_hash.strip()
        transaction = await get_transaction_by_hash(normalized_hash)

        if not transaction:
            await interaction.response.send_message(
                "Transaction with this hash was not found in our database.",
                ephemeral=True,
            )
            return

        explorer_url = self._build_explorer_url(transaction.hash, transaction.network, transaction.coin)
        status = (transaction.status or "UNKNOWN").title()
        network_value = transaction.network or "Unknown"

        embed = discord.Embed(
            title="Transaction Info",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Transaction Hash",
            value=f"[{transaction.hash}]({explorer_url})",
            inline=False,
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(
            name="Crypto Details",
            value=(
                f"Amount: `{transaction.recieved}`\n"
                f"Network/Coin: `{network_value}` / `{transaction.coin}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="Sender & Receiver",
            value=(
                f"**Sender**\n{self._format_party(transaction.sender_wallet, transaction.sender_id)}\n\n"
                f"**Receiver**\n{self._format_party(transaction.reciever_wallet, transaction.reciever_id)}"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(TransactionCog(bot))
