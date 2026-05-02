import asyncio
import sys
import unittest
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

IMPORT_ERROR: ModuleNotFoundError | None = None
try:
    from sqlalchemy import text

    from cogs import config as config_module
    from cogs.config_repository import CommandSettingsRepository, ensure_command_settings_table
    from db import AsyncSessionFactory, engine
except ModuleNotFoundError as exc:  # pragma: no cover
    IMPORT_ERROR = exc


def _deps_message() -> str:
    if IMPORT_ERROR is None:
        return ""
    return f"Missing runtime dependency: {IMPORT_ERROR}"


@unittest.skipIf(IMPORT_ERROR is not None, _deps_message())
class AsyncDatabaseSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_standalone_async_sqlalchemy_smoke(self):
        """Standalone async SQLAlchemy smoke test without cog code."""

        async def _engine_smoke():
            async with engine.begin() as conn:
                result = await conn.execute(text("select 1"))
                self.assertEqual(result.scalar_one(), 1)

        async def _session_smoke():
            async with AsyncSessionFactory() as session:
                result = await session.execute(text("select 1"))
                self.assertEqual(result.scalar_one(), 1)

        try:
            await asyncio.wait_for(_engine_smoke(), timeout=5)
            await asyncio.wait_for(_session_smoke(), timeout=5)
        except TimeoutError as exc:
            self.fail(
                "Async DB smoke timed out while connecting/executing query via SQLAlchemy "
                "(sqlite+aiosqlite backend appears unresponsive)."
            )
        finally:
            await asyncio.wait_for(engine.dispose(), timeout=5)


@unittest.skipIf(IMPORT_ERROR is not None, _deps_message())
class CommandSettingsRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        try:
            await asyncio.wait_for(ensure_command_settings_table(), timeout=5)
        except TimeoutError:
            self.fail(
                "ensure_command_settings_table() timed out. "
                "Async SQLite backend is unresponsive."
            )
        self.guild_id = uuid4().int % 10_000_000_000

    async def asyncTearDown(self):
        settings = await asyncio.wait_for(
            CommandSettingsRepository.list_guild_settings(self.guild_id),
            timeout=5,
        )
        for setting in settings:
            await asyncio.wait_for(
                CommandSettingsRepository.delete_command_setting(
                    self.guild_id,
                    setting.command_name,
                ),
                timeout=5,
            )

    async def test_create_and_get_setting(self):
        created = await asyncio.wait_for(
            CommandSettingsRepository.create_command_setting(
                guild_id=self.guild_id,
                command_name="starttrade",
                enabled=True,
                extra_settings={"cooldown": 10},
            ),
            timeout=5,
        )
        fetched = await asyncio.wait_for(
            CommandSettingsRepository.get_command_setting(
                self.guild_id,
                "starttrade",
            ),
            timeout=5,
        )

        self.assertIsNotNone(created.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.command_name, "starttrade")
        self.assertTrue(fetched.enabled)
        self.assertEqual(fetched.extra_settings, {"cooldown": 10})

    async def test_update_enabled(self):
        await asyncio.wait_for(
            CommandSettingsRepository.create_command_setting(
                guild_id=self.guild_id,
                command_name="transaction",
                enabled=True,
            ),
            timeout=5,
        )
        updated = await asyncio.wait_for(
            CommandSettingsRepository.update_enabled(
                self.guild_id,
                "transaction",
                False,
            ),
            timeout=5,
        )
        self.assertIsNotNone(updated)
        self.assertFalse(updated.enabled)

    async def test_update_extra_settings(self):
        await asyncio.wait_for(
            CommandSettingsRepository.create_command_setting(
                guild_id=self.guild_id,
                command_name="profile",
                enabled=True,
                extra_settings={},
            ),
            timeout=5,
        )
        updated = await asyncio.wait_for(
            CommandSettingsRepository.update_extra_settings(
                self.guild_id,
                "profile",
                {"allowed_roles": ["mod"], "cooldown": 30},
            ),
            timeout=5,
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.extra_settings["cooldown"], 30)
        self.assertEqual(updated.extra_settings["allowed_roles"], ["mod"])

    async def test_list_disabled_commands(self):
        await asyncio.wait_for(
            CommandSettingsRepository.create_command_setting(
                guild_id=self.guild_id,
                command_name="ping",
                enabled=True,
            ),
            timeout=5,
        )
        await asyncio.wait_for(
            CommandSettingsRepository.create_command_setting(
                guild_id=self.guild_id,
                command_name="starttrade",
                enabled=False,
            ),
            timeout=5,
        )
        await asyncio.wait_for(
            CommandSettingsRepository.create_command_setting(
                guild_id=self.guild_id,
                command_name="transaction",
                enabled=False,
            ),
            timeout=5,
        )
        disabled = await asyncio.wait_for(
            CommandSettingsRepository.list_disabled_commands(self.guild_id),
            timeout=5,
        )
        self.assertEqual(
            [item.command_name for item in disabled],
            ["starttrade", "transaction"],
        )

    async def test_delete_setting(self):
        await asyncio.wait_for(
            CommandSettingsRepository.create_command_setting(
                guild_id=self.guild_id,
                command_name="profile",
                enabled=False,
            ),
            timeout=5,
        )
        deleted = await asyncio.wait_for(
            CommandSettingsRepository.delete_command_setting(
                self.guild_id,
                "profile",
            ),
            timeout=5,
        )
        fetched = await asyncio.wait_for(
            CommandSettingsRepository.get_command_setting(
                self.guild_id,
                "profile",
            ),
            timeout=5,
        )
        self.assertTrue(deleted)
        self.assertIsNone(fetched)

    async def test_upsert_setting(self):
        first = await asyncio.wait_for(
            CommandSettingsRepository.upsert_command_setting(
                guild_id=self.guild_id,
                command_name="trade",
                enabled=True,
                extra_settings={"step": 1},
            ),
            timeout=5,
        )
        second = await asyncio.wait_for(
            CommandSettingsRepository.upsert_command_setting(
                guild_id=self.guild_id,
                command_name="trade",
                enabled=False,
                extra_settings={"step": 2},
            ),
            timeout=5,
        )
        self.assertEqual(first.id, second.id)
        self.assertFalse(second.enabled)
        self.assertEqual(second.extra_settings, {"step": 2})


@unittest.skipIf(IMPORT_ERROR is not None, _deps_message())
class ConfigSetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_calls_add_cog(self):
        class FakeBot:
            def __init__(self):
                self.added_cog = None

            async def add_cog(self, cog):
                self.added_cog = cog

        bot = FakeBot()
        try:
            await asyncio.wait_for(config_module.setup(bot), timeout=5)
        except TimeoutError:
            self.fail(
                "config.setup(bot) timed out; ensure_command_settings_table() likely "
                "blocked on async SQLite connect."
            )

        self.assertIsNotNone(bot.added_cog)
        self.assertEqual(bot.added_cog.__class__.__name__, "ConfigCog")


if __name__ == "__main__":
    unittest.main()
