import discord
from cfg import *

def create_suc_embed(title=None, desc=None):
    embed = discord.Embed(title=title, description=desc, color=EMBED_SUC_COLOR)
    return embed
