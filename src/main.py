
from datetime import date
import discord
from discord.ext import commands
import os, logging, traceback
from dotenv import load_dotenv
from utils.crypto import init_w3, subscribe_to_blocks, context_manager_subscription_example
import asyncio, requests, db
#     level=logging.DEBUG,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)
load_dotenv()
# db = SessionLocal()
# user = User(
#     name="Just Felix",
# )
# db.add(user)
# db.commit()

# with SessionLocal() as db:

#     all_users = db.execute(select(User)).scalars().all()
#     for user in all_users:
#         print(f"{user.id}: {user.name}")
# before launching bot, turn on intents, read more https://docs.discord.com/developers/events/gateway
TOKEN = os.getenv("DIS_BOT_TOKEN")
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True

bot = commands.Bot(command_prefix='$', intents=intents)

@bot.event
async def on_ready():
    print(f'logged in as {bot.user}')

    for filename in os.listdir('./src/cogs'):
        if filename.endswith('.py') and filename != '__init__.py':
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'loaded cog: {filename}')
            except Exception as e:
                print(f'failed to load cog {filename}: {e}')
    
    try:
        synced = await bot.tree.sync()
        print(f"synced {len(synced)} slash commands")
        
    except Exception as e:
        print(f"failed to sync commands: {e}")
    
    print('ready')

async def main():
    await init_w3()
    await db.init_db()
    asyncio.create_task(bot.start(TOKEN))
    try:

        await context_manager_subscription_example()
    except Exception as e:
        print(e)
    # while True:
    #     pass
    # loop = asyncio.get_event_loop()
    # while True:
    # try:
    #     await handle_pending_transactions()
    # except Exception as e:
    #     print(e)
    # try:
    #     transaction: Transaction = await create_transaction("sender_wallet", "reciever_wallet", None, 1, 2, "уер", 1)
    #     print(transaction)
    # except Exception as e:
    #     print(e)

if __name__ == "__main__":
    asyncio.run(main())