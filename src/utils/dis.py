import discord

import cfg


def create_suc_embed(title=None, desc=None):
    embed = discord.Embed(title=title, description=desc, color=cfg.EMBED_SUC_COLOR)
    return embed
