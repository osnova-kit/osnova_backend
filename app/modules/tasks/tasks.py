import asyncio
import logging
import smtplib

from app.core.mail import EmailMessage, deliver
from app.modules.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# Bound to celery_app (not shared_task): calls from other threads use its settings
@celery_app.task(
    name="mail.send",
    ignore_result=True,
    autoretry_for=(OSError, smtplib.SMTPException),
    retry_backoff=True,
    max_retries=5,
)
def send_mail_task(message: dict[str, str | None]) -> None:
    """Example task: send an email built with app.core.mail, retrying while the server is down."""
    deliver(EmailMessage(**message))


@celery_app.task(name="maintenance.cleanup", ignore_result=True)
def cleanup_task() -> None:
    """Example scheduled task: remove old rows every night (app/modules/db/cleanup.py)."""
    # Imported here: the tasks module also works without a database
    from app.modules.db.cleanup import run_cleanup

    asyncio.run(run_cleanup())
