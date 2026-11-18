from fastapi import FastAPI


def register(app: FastAPI):
    from .refresh import SettingsRefreshMiddleware
    from .routes import settings_router

    app.include_router(settings_router, prefix="/api/v1/admin/settings", tags=["Admin"])
    app.add_middleware(SettingsRefreshMiddleware)
    return None
