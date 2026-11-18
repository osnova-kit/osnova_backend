from fastapi import FastAPI


def register(app: FastAPI):
    import logging

    from httpx_oauth.exceptions import HTTPXOAuthError

    from app.core.errors import error_response

    from .backend import redis_client
    from .routes import auth_router

    async def oauth_provider_error(request, exc: HTTPXOAuthError):
        response = getattr(exc, "response", None)
        detail = response.text[:300] if response is not None else ""
        logging.getLogger(__name__).warning("OAuth provider error: %s %s", exc, detail)
        return error_response(400, "oauth_provider_error")

    app.add_exception_handler(HTTPXOAuthError, oauth_provider_error)

    if redis_client is not None:
        from app.core.readiness import add_check

        async def redis_sessions() -> None:
            await redis_client.ping()

        add_check("redis", redis_sessions)

    app.include_router(auth_router, prefix="/api/v1/auth")
    return None
