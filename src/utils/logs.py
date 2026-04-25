import discord

import cfg


async def send_log(guild: discord.Guild, chan_id: int, embed: discord.Embed):
    if not chan_id:
        return
    chan = guild.get_channel(chan_id)
    if chan is None:
        return
    await chan.send(embed=embed)

async def send_transaction_log(guild, embed):
    await send_log(guild, cfg.TRANSACTIONS_LOG_CHAN_ID, embed)
