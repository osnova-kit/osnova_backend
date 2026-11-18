from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import entities_router

    app.include_router(entities_router, prefix="/api/v1/admin/entities", tags=["Admin"])
    return None
