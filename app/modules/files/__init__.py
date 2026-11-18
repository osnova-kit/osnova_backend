from fastapi import FastAPI


def register(app: FastAPI):
    from app.config import config
    from app.modules.auth.hooks import on_user_delete

    if config.APP_PROFILE == "scalable" and config.FILES_STORAGE == "local":
        raise RuntimeError(
            "APP_PROFILE=scalable needs FILES_STORAGE=s3: local files stay in one replica"
        )

    from .routes import delete_user_files, files_router
    from .storage import get_storage

    get_storage()
    on_user_delete(delete_user_files)

    app.include_router(files_router, prefix="/api/v1/files", tags=["Files"])
    return None
