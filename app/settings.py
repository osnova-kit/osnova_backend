from pydantic import Field

from app.config import config
from app.core.captcha import ProtectionSettings
from app.core.languages import LanguageSettings
from app.core.mail.settings import MailSettings
from app.core.settings import OptionalEmail, OptionalPhone, SettingsGroup

MAX_DAYS = 3650


class SiteSettings(SettingsGroup):
    group = "site"

    name: str = Field(default_factory=lambda: config.APP_NAME, min_length=1, max_length=100)
    contact_email: OptionalEmail = ""
    contact_phone: OptionalPhone = ""


class RetentionSettings(SettingsGroup):
    group = "retention"

    notifications_days: int = Field(
        default_factory=lambda: config.NOTIFICATIONS_KEEP_DAYS, ge=0, le=MAX_DAYS
    )
    unverified_account_days: int = Field(
        default_factory=lambda: config.UNVERIFIED_ACCOUNT_DAYS, ge=0, le=MAX_DAYS
    )
    audit_days: int = Field(default_factory=lambda: config.AUDIT_KEEP_DAYS, ge=0, le=MAX_DAYS)


GROUPS: tuple[type[SettingsGroup], ...] = (
    SiteSettings,
    LanguageSettings,
    MailSettings,
    ProtectionSettings,
    RetentionSettings,
)
