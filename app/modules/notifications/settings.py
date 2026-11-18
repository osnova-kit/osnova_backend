from typing import Literal

from pydantic import Field

from app.config import config
from app.core.settings import SettingsGroup
from app.modules.notifications.channels import CHANNELS

ChannelName = Literal[tuple(CHANNELS)]  # type: ignore[valid-type]


def _from_env() -> list[str]:
    names = (name.strip() for name in config.NOTIFICATIONS_CHANNELS.split(","))
    return [name for name in names if name in CHANNELS]


class NotificationSettings(SettingsGroup):
    group = "notifications"

    channels: list[ChannelName] = Field(default_factory=_from_env)  # type: ignore[valid-type]


GROUPS = (NotificationSettings,)
