from fastapi import FastAPI


def register(app: FastAPI):
    from fastapi.concurrency import run_in_threadpool

    from app.core.mail import EmailMessage, use_dispatcher
    from app.core.readiness import add_check

    from .celery_app import celery_app
    from .tasks import send_mail_task

    def connect_to_broker() -> None:
        with celery_app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=1)

    async def broker() -> None:
        await run_in_threadpool(connect_to_broker)

    add_check("broker", broker)

    async def queue_mail(message: EmailMessage) -> None:
        # delay() talks to the broker synchronously: keep it off the event loop
        await run_in_threadpool(send_mail_task.delay, message.to_dict())

    use_dispatcher(queue_mail)
    return None
