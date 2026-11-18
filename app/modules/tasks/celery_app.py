from importlib.util import find_spec

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging, task_prerun

from app.config import config
from app.core.modules import resolve_enabled

if not config.CELERY_BROKER_URL:
    raise RuntimeError("Background tasks module requires CELERY_BROKER_URL")


def _task_modules() -> list[str]:
    """The ``tasks`` modules of the enabled modules (e.g. app/modules/leads/tasks.py)."""
    names = (f"{spec.path}.tasks" for spec in resolve_enabled(config))
    return [name for name in names if find_spec(name)]


celery_app = Celery(
    "osnova",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND or config.CELERY_BROKER_URL,
    include=_task_modules(),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_transport_options={"max_retries": 0},
    # The default, set to keep Celery from warning about a coming change
    broker_connection_retry_on_startup=True,
    task_publish_retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 0.2},
)


@setup_logging.connect
def use_app_logging(**_) -> None:
    from app.core.logging_config import setup_logging as setup

    setup()


@task_prerun.connect
def load_admin_settings(**_) -> None:
    if "settings" in {spec.name for spec in resolve_enabled(config)}:
        from app.modules.settings.service import refresh_stored_settings

        refresh_stored_settings()


if config.DATABASE_URL:
    celery_app.conf.beat_schedule = {
        "cleanup": {"task": "maintenance.cleanup", "schedule": crontab(hour=3, minute=30)},
    }
