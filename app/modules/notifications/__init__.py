from fastapi import FastAPI


def register(app: FastAPI):
    from app.modules.auth.hooks import on_user_delete

    from .routes import notifications_router
    from .service import delete_user_notifications

    on_user_delete(delete_user_notifications)

    app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["Notifications"])
    return None
