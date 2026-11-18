from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.core.bootstrap import BootstrapResponse, get_bootstrap_config
from app.core.forms.routes import forms_router
from app.core.readiness import run_checks

core_router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: dict[str, bool]


@core_router.get("/bootstrap", tags=["System"])
async def bootstrap() -> BootstrapResponse:
    return get_bootstrap_config()


@core_router.get("/health", tags=["System"])
async def health() -> HealthResponse:
    """Liveness: the process is running."""
    return HealthResponse(status="ok")


@core_router.get(
    "/ready",
    tags=["System"],
    responses={503: {"model": ReadyResponse, "description": "A dependency is down"}},
)
async def ready(response: Response) -> ReadyResponse:
    """Readiness: the dependencies of the enabled modules answer (503 if one does not)."""
    results = await run_checks()
    if all(results.values()):
        return ReadyResponse(status="ok", checks=results)
    response.status_code = 503
    return ReadyResponse(status="unavailable", checks=results)


core_router.include_router(forms_router)
