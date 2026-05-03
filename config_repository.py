from typing import Any

from sqlalchemy import Boolean, JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from db import AsyncSessionFactory, Base, engine


class CommandSetting(Base):
    __tablename__ = "command_settings"
    __table_args__ = (
        UniqueConstraint("guild_id", "command_name", name="uq_command_settings_guild_command"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(index=True)
    command_name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


def _normalize_command_name(command_name: str) -> str:
    return command_name.strip().lower()


async def ensure_command_settings_table() -> None:
    """Create the table if it does not exist yet."""
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: CommandSetting.__table__.create(bind=sync_conn, checkfirst=True)
        )


class CommandSettingsRepository:
    """Async CRUD helpers for per-guild command settings."""

    @staticmethod
    async def create_command_setting(
        guild_id: int,
        command_name: str,
        enabled: bool = True,
        extra_settings: dict[str, Any] | None = None,
    ) -> CommandSetting:
        """Create a new setting row for a guild command."""
        normalized_name = _normalize_command_name(command_name)
        payload = extra_settings or {}

        async with AsyncSessionFactory() as session:
            try:
                setting = CommandSetting(
                    guild_id=guild_id,
                    command_name=normalized_name,
                    enabled=enabled,
                    extra_settings=payload,
                )
                session.add(setting)
                await session.commit()
                await session.refresh(setting)
                return setting
            except Exception:
                await session.rollback()
                raise

    @staticmethod
    async def get_command_setting(guild_id: int, command_name: str) -> CommandSetting | None:
        """Read one setting by (guild_id, command_name)."""
        normalized_name = _normalize_command_name(command_name)
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(CommandSetting).where(
                    CommandSetting.guild_id == guild_id,
                    CommandSetting.command_name == normalized_name,
                )
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def update_enabled(
        guild_id: int,
        command_name: str,
        enabled: bool,
    ) -> CommandSetting | None:
        """Update only the enabled/disabled flag for a command."""
        normalized_name = _normalize_command_name(command_name)
        async with AsyncSessionFactory() as session:
            try:
                result = await session.execute(
                    select(CommandSetting).where(
                        CommandSetting.guild_id == guild_id,
                        CommandSetting.command_name == normalized_name,
                    )
                )
                setting = result.scalar_one_or_none()
                if setting is None:
                    return None

                setting.enabled = enabled
                await session.commit()
                await session.refresh(setting)
                return setting
            except Exception:
                await session.rollback()
                raise

    @staticmethod
    async def update_extra_settings(
        guild_id: int,
        command_name: str,
        extra_settings: dict[str, Any],
    ) -> CommandSetting | None:
        """Update only extra JSON settings for a command."""
        normalized_name = _normalize_command_name(command_name)
        async with AsyncSessionFactory() as session:
            try:
                result = await session.execute(
                    select(CommandSetting).where(
                        CommandSetting.guild_id == guild_id,
                        CommandSetting.command_name == normalized_name,
                    )
                )
                setting = result.scalar_one_or_none()
                if setting is None:
                    return None

                setting.extra_settings = extra_settings
                await session.commit()
                await session.refresh(setting)
                return setting
            except Exception:
                await session.rollback()
                raise

    @staticmethod
    async def delete_command_setting(guild_id: int, command_name: str) -> bool:
        """Delete a command setting row. Returns True if deleted."""
        normalized_name = _normalize_command_name(command_name)
        async with AsyncSessionFactory() as session:
            try:
                result = await session.execute(
                    select(CommandSetting).where(
                        CommandSetting.guild_id == guild_id,
                        CommandSetting.command_name == normalized_name,
                    )
                )
                setting = result.scalar_one_or_none()
                if setting is None:
                    return False

                await session.delete(setting)
                await session.commit()
                return True
            except Exception:
                await session.rollback()
                raise

    @staticmethod
    async def list_guild_settings(guild_id: int) -> list[CommandSetting]:
        """List all settings rows for a guild."""
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(CommandSetting)
                .where(CommandSetting.guild_id == guild_id)
                .order_by(CommandSetting.command_name.asc())
            )
            return list(result.scalars().all())

    @staticmethod
    async def list_disabled_commands(guild_id: int) -> list[CommandSetting]:
        """List only disabled commands for a guild."""
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(CommandSetting)
                .where(
                    CommandSetting.guild_id == guild_id,
                    CommandSetting.enabled.is_(False),
                )
                .order_by(CommandSetting.command_name.asc())
            )
            return list(result.scalars().all())

    @staticmethod
    async def upsert_command_setting(
        guild_id: int,
        command_name: str,
        enabled: bool,
        extra_settings: dict[str, Any] | None = None,
    ) -> CommandSetting:
        """Create or update a setting; used by the /config command flow."""
        normalized_name = _normalize_command_name(command_name)
        payload = extra_settings or {}

        async with AsyncSessionFactory() as session:
            try:
                result = await session.execute(
                    select(CommandSetting).where(
                        CommandSetting.guild_id == guild_id,
                        CommandSetting.command_name == normalized_name,
                    )
                )
                setting = result.scalar_one_or_none()

                if setting is None:
                    setting = CommandSetting(
                        guild_id=guild_id,
                        command_name=normalized_name,
                        enabled=enabled,
                        extra_settings=payload,
                    )
                    session.add(setting)
                else:
                    setting.enabled = enabled
                    setting.extra_settings = payload

                await session.commit()
                await session.refresh(setting)
                return setting
            except Exception:
                await session.rollback()
                raise
