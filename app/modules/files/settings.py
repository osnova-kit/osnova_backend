from pydantic import Field

from app.config import config
from app.core.settings import SettingsGroup


class FilesSettings(SettingsGroup):
    """Behind nginx a request is also limited by client_max_body_size."""

    group = "files"

    max_size_mb: int = Field(default_factory=lambda: config.FILES_MAX_SIZE_MB, ge=1, le=1024)
    allowed_types: str = Field(default_factory=lambda: config.FILES_ALLOWED_TYPES, max_length=500)

    @property
    def allowed(self) -> tuple[str, ...]:
        return tuple(item.strip() for item in self.allowed_types.split(",") if item.strip())


GROUPS = (FilesSettings,)
