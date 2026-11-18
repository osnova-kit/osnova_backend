from fastapi import FastAPI


def register(app: FastAPI):
    from app.core.forms.delivery import add_receiver

    from . import channels  # noqa: F401  registers the channel types
    from .routes import leads_router
    from .service import store_lead

    add_receiver(store_lead)
    app.include_router(leads_router, prefix="/api/v1/admin/leads", tags=["Admin"])
    return None
