import json
import logging
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Literal

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from pydantic import Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from app.config import config
from app.core.errors import AppError
from app.core.rate_limit import RateLimit
from app.core.settings import Secret, SettingsGroup, settings

logger = logging.getLogger(__name__)

CAPTCHA_HEADER = "X-Captcha-Token"
TIMEOUT = 3
MAX_TOKEN_LENGTH = 2048
TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

Verifier = Callable[[str, str], bool]


def _turnstile(secret: str, token: str) -> bool:
    body = urllib.parse.urlencode({"secret": secret, "response": token}).encode()
    with urllib.request.urlopen(TURNSTILE_URL, data=body, timeout=TIMEOUT) as response:
        result = json.load(response)
    if not result.get("success"):
        codes = result.get("error-codes") or []
        level = logging.ERROR if "invalid-input-secret" in codes else logging.INFO
        logger.log(level, "Captcha refused: %s", ", ".join(codes) or "no reason given")
    return bool(result.get("success"))


PROVIDERS: dict[str, Verifier] = {"turnstile": _turnstile}


def _env_configured() -> bool:
    return bool(config.CAPTCHA_PROVIDER and config.CAPTCHA_SITE_KEY and config.CAPTCHA_SECRET_KEY)


class ProtectionSettings(SettingsGroup):
    group = "protection"

    captcha_provider: Literal[tuple(PROVIDERS)] = Field(  # type: ignore[valid-type]
        default_factory=lambda: config.CAPTCHA_PROVIDER or "turnstile"
    )
    captcha_site_key: str = Field(
        default_factory=lambda: config.CAPTCHA_SITE_KEY or "", max_length=200
    )
    captcha_secret_key: Secret = Field(default_factory=lambda: config.CAPTCHA_SECRET_KEY or "")
    captcha: bool = Field(default_factory=_env_configured)
    forms_rate_limit: RateLimit = Field(default_factory=lambda: config.FORMS_RATE_LIMIT)
    auth_rate_limit: RateLimit = Field(default_factory=lambda: config.AUTH_RATE_LIMIT)

    @field_validator("captcha")
    @classmethod
    def _needs_keys(cls, value: bool, info: ValidationInfo) -> bool:
        keys = info.data.get("captcha_site_key"), info.data.get("captcha_secret_key")
        if value and not all(keys):
            raise PydanticCustomError("captcha_not_configured", "Captcha keys are not set")
        return value


def captcha_active() -> bool:
    current = settings.get(ProtectionSettings)
    return current.captcha and bool(current.captcha_site_key and current.captcha_secret_key)


def check_captcha_config() -> None:
    if config.CAPTCHA_PROVIDER and not _env_configured():
        logger.warning(
            "CAPTCHA_PROVIDER=%s, but CAPTCHA_SITE_KEY or CAPTCHA_SECRET_KEY is not set: "
            "the captcha is off until the keys are set in Admin → Settings → Protection.",
            config.CAPTCHA_PROVIDER,
        )


async def require_captcha(request: Request) -> None:
    if not captcha_active():
        return
    token = request.headers.get(CAPTCHA_HEADER, "").strip()
    if not token or len(token) > MAX_TOKEN_LENGTH:
        raise AppError(400, "captcha_failed")
    current = settings.get(ProtectionSettings)
    verify = PROVIDERS[current.captcha_provider]
    try:
        accepted = await run_in_threadpool(verify, current.captcha_secret_key, token)
    except (OSError, ValueError):
        logger.warning("Captcha provider is unreachable, request let through", exc_info=True)
        return
    if not accepted:
        raise AppError(400, "captcha_failed")
