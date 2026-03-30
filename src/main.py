from sqlalchemy import select
from models.User import User
from db import engine, SessionLocal
from datetime import date
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv


load_dotenv()
User.metadata.create_all(bind=engine)
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


bot.run(TOKEN)