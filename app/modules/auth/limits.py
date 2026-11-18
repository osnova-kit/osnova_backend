from fastapi import Depends, Request

from app.core.captcha import ProtectionSettings
from app.core.rate_limit import LimitFromSetting, check_limit, client_address
from app.core.settings import settings

limiter = LimitFromSetting(lambda: settings.get(ProtectionSettings).auth_rate_limit, "auth")


async def limit_by_ip(request: Request) -> None:
    await check_limit(limiter, f"{request.url.path}:{client_address(request)}")


limited = [Depends(limit_by_ip)]
