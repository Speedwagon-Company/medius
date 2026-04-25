from __future__ import annotations

import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import db
from payments.factory import get_payment_provider
from settings import load_settings

load_dotenv()
settings = load_settings()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="$", intents=intents)


@bot.event
async def on_ready():
    print(f"logged in as {bot.user}")

    for filename in os.listdir("./src/cogs"):
        if filename.endswith(".py") and filename != "__init__.py":
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"loaded cog: {filename}")
            except Exception as err:
                print(f"failed to load cog {filename}: {err}")

    print("ready")


async def main() -> None:
    settings.validate()
    get_payment_provider(settings)
    await db.init_db(settings.database_url)

    try:
        await bot.start(settings.discord_token)
    finally:
        await db.close_db()


if __name__ == "__main__":
    asyncio.run(main())
