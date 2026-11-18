from typing import Literal

from pydantic import BaseModel

from app.config import config
from app.core.captcha import ProtectionSettings, captcha_active
from app.core.languages import get_languages
from app.core.settings import settings
from app.settings import SiteSettings


class BootstrapApplication(BaseModel):
    name: str
    version: str
    contact_email: str
    contact_phone: str


class BootstrapLanguage(BaseModel):
    code: str
    name: str


class BootstrapI18n(BaseModel):
    languages: list[BootstrapLanguage]
    default: str


class BootstrapFeatures(BaseModel):
    authentication: bool
    admin: bool
    files: bool
    notifications: bool
    background_tasks: bool


class BootstrapCaptcha(BaseModel):
    provider: Literal["turnstile"]
    site_key: str


class BootstrapResponse(BaseModel):
    application: BootstrapApplication
    profile: Literal["minimal", "standard", "scalable"]
    i18n: BootstrapI18n
    features: BootstrapFeatures
    auth_providers: list[str]
    api_docs: bool
    captcha: BootstrapCaptcha | None = None


def get_bootstrap_config() -> BootstrapResponse:
    site = settings.get(SiteSettings)
    protection = settings.get(ProtectionSettings)
    languages = get_languages()
    return BootstrapResponse(
        application=BootstrapApplication(
            name=site.name,
            version=config.APP_VERSION,
            contact_email=site.contact_email,
            contact_phone=site.contact_phone,
        ),
        profile=config.APP_PROFILE,
        i18n=BootstrapI18n(
            languages=[
                BootstrapLanguage(code=lang.code, name=lang.name) for lang in languages.enabled
            ],
            default=languages.default,
        ),
        features=BootstrapFeatures(
            authentication=config.AUTH_ENABLED,
            admin=config.ADMIN_ENABLED,
            files=config.FILES_ENABLED,
            notifications=config.NOTIFICATIONS_ENABLED,
            background_tasks=config.BACKGROUND_TASKS_ENABLED,
        ),
        auth_providers=config.oauth_providers,
        api_docs=config.DEBUG,
        captcha=(
            BootstrapCaptcha(
                provider=protection.captcha_provider, site_key=protection.captcha_site_key
            )
            if captcha_active()
            else None
        ),
    )
