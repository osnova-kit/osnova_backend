from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from app.config import config
from app.core.settings import Secret, SettingsGroup


class MailSettings(SettingsGroup):
    group = "mail"

    backend: Literal["console", "smtp"] = Field(default_factory=lambda: config.MAIL_BACKEND)
    from_address: str = Field(
        default_factory=lambda: config.MAIL_FROM, min_length=3, max_length=254
    )
    smtp_host: str = Field(default_factory=lambda: config.SMTP_HOST, max_length=253)
    smtp_port: int = Field(default_factory=lambda: config.SMTP_PORT, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = Field(
        default_factory=lambda: config.SMTP_SECURITY
    )
    smtp_username: str = Field(default_factory=lambda: config.SMTP_USERNAME or "", max_length=254)
    smtp_password: Secret = Field(default_factory=lambda: config.SMTP_PASSWORD or "")
    smtp_timeout: int = Field(default_factory=lambda: config.SMTP_TIMEOUT, ge=1, le=120)

    @field_validator("smtp_username")
    @classmethod
    def _login_needs_encryption(cls, value: str, info: ValidationInfo) -> str:
        if value and info.data.get("smtp_security") == "none":
            raise PydanticCustomError("smtp_login_unencrypted", "Login needs STARTTLS or SSL")
        return value


def check_mail_config() -> None:
    if config.SMTP_USERNAME and config.SMTP_SECURITY == "none":
        raise RuntimeError(
            "SMTP_USERNAME with SMTP_SECURITY=none would send the password unencrypted: "
            "set SMTP_SECURITY=starttls or ssl"
        )
