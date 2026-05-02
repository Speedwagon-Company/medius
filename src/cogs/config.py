import discord
from discord import app_commands
from discord.ext import commands

from db import get_command_setting, upsert_command_setting


class ConfigCog(commands.Cog):
    config = app_commands.Group(
        name="config",
        description="Commands for bot configuration",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @config.command(name="command", description="Enable or disable a command for this server")
    @app_commands.describe(
        command_name="Command name, for example: starttrade",
        enabled="True to enable, False to disable",
    )
    async def command(
        self,
        interaction: discord.Interaction,
        command_name: str,
        enabled: bool,
    ):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command is available only in server channels.",
                ephemeral=True,
            )
            return

        setting = await upsert_command_setting(
            guild_id=guild.id,
            command_name=command_name,
            enabled=enabled,
        )

        state = "enabled" if setting.enabled else "disabled"
        await interaction.response.send_message(
            f"Command `{setting.command_name}` is now **{state}** for this server.",
            ephemeral=True,
        )

    @config.command(name="status", description="Show current command config in this server")
    @app_commands.describe(command_name="Command name, for example: starttrade")
    async def status(self, interaction: discord.Interaction, command_name: str):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command is available only in server channels.",
                ephemeral=True,
            )
            return

        setting = await get_command_setting(guild.id, command_name)
        if setting is None:
            await interaction.response.send_message(
                "No config found for this command in current server.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            (
                f"Command: `{setting.command_name}`\n"
                f"Enabled: `{setting.enabled}`\n"
                f"Extra settings: `{setting.extra_settings}`"
            ),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
