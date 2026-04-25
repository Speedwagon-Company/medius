from __future__ import annotations

from settings import Settings


def is_admin_discord_user(discord_user_id: int, settings: Settings) -> bool:
    return discord_user_id in settings.admin_discord_ids

