from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import user_router

    app.include_router(user_router, prefix="/api/v1/user", tags=["User"])
    return None
