from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import admin_router

    app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
    return None
