from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.version import VERSION


class Settings(BaseSettings):
    APP_NAME: str = "Osnova Application"
    APP_VERSION: str = VERSION
    APP_PROFILE: Literal["minimal", "standard", "scalable"] = "minimal"
    APP_HOST: str = "localhost"
    APP_PORT: int = 8000
    DEBUG: bool = False
    LOG_FORMAT: Literal["text", "json"] = "text"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "production"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    AUTH_ENABLED: bool = False
    ADMIN_ENABLED: bool = False
    FILES_ENABLED: bool = False
    NOTIFICATIONS_ENABLED: bool = False
    BACKGROUND_TASKS_ENABLED: bool = False

    LANGUAGES: str = "en,ru"
    DEFAULT_LANGUAGE: str = "en"

    CORS_ORIGINS: str = "http://localhost:5173"

    FORMS_DELIVERY: Literal["log", "file"] = "log"
    FORMS_FILE: str = "data/forms.jsonl"
    FORMS_RATE_LIMIT: str = "5/minute"
    WEBHOOK_ALLOW_PRIVATE: bool = False

    CAPTCHA_PROVIDER: Literal["", "turnstile"] = ""
    CAPTCHA_SITE_KEY: str | None = None
    CAPTCHA_SECRET_KEY: str | None = None

    DATABASE_URL: str | None = None
    DB_ECHO: bool = False

    SECRET_KEY: str | None = None
    OLD_SECRET_KEYS: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    AUTH_STRATEGY: Literal["jwt", "redis"] = "jwt"
    COOKIE_SECURE: bool = False
    AUTH_RATE_LIMIT: str = "10/minute"
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    REDIS_URL: str | None = None
    RATE_LIMIT_STORAGE: Literal["memory", "redis"] = "memory"

    FRONTEND_URL: str = "http://localhost:5173"

    MAIL_BACKEND: Literal["console", "smtp"] = "console"
    MAIL_FROM: str = "Osnova <noreply@example.com>"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_SECURITY: Literal["starttls", "ssl", "none"] = "starttls"
    SMTP_TIMEOUT: int = 10

    NOTIFICATIONS_CHANNELS: str = "in_app"
    NOTIFICATIONS_KEEP_DAYS: int = 90
    UNVERIFIED_ACCOUNT_DAYS: int = 0
    AUDIT_KEEP_DAYS: int = 365

    SETTINGS_REFRESH_SECONDS: int = 30

    FILES_STORAGE: Literal["local", "s3"] = "local"
    FILES_DIR: str = "uploads"
    FILES_MAX_SIZE_MB: int = 10
    FILES_ALLOWED_TYPES: str = ""
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str | None = None
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_LINK_SECONDS: int = 300

    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @property
    def oauth_providers(self) -> list[str]:
        if not self.AUTH_ENABLED:
            return []
        keys = {"google": (self.GOOGLE_CLIENT_ID, self.GOOGLE_CLIENT_SECRET)}
        return [name for name, values in keys.items() if all(values)]


config = Settings()
