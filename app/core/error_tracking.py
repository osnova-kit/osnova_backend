import logging

from app.config import config


def setup_error_tracking() -> None:
    if not config.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError as exc:
        raise RuntimeError(
            "SENTRY_DSN requires sentry-sdk: pip install -r requirements/sentry.txt "
            "(Docker: EXTRA_REQUIREMENTS=sentry)"
        ) from exc

    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        environment=config.SENTRY_ENVIRONMENT,
        release=f"osnova-backend@{config.APP_VERSION}",
        # No user data by default (send_default_pii and data_collection left unset turn
        # on the SDK's own scrubber); bodies and frame variables are left out on top
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR)],
    )
