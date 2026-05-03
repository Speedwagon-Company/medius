import discord
from cfg import *
from db import get_embed_suc_color

def parse_color(color_str):
    if color_str.startswith('0x'):
        col = int(color_str, 16) 
    elif color_str.startswith('#'):
        col = int(color_str[1:], 16)  
    else:
        col = int(color_str, 16)
    return col

async def create_suc_embed(title=None, desc=None):
    col = parse_color(await get_embed_suc_color() )

    embed = discord.Embed(title=title, description=desc, color=col)
    return embed

