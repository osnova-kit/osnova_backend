import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.core.errors import error_response
from app.core.i18n import LanguageMiddleware
from app.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware, current_request_id

logger = logging.getLogger(__name__)


def add_middlewares(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error: %s %s", request.method, request.url.path)
            response = error_response(500, "internal_error", request_id=current_request_id.get())
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "%s %s %s %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms),
            },
        )
        return response

    # Around the error handler above, so a 500 also carries the CORS headers and the
    # frontend on another origin (development) sees the message, not a network error
    origins = [o.strip() for o in config.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(LanguageMiddleware)
    app.add_middleware(RequestIdMiddleware)
