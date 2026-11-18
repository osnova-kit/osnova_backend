from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.core.mail.settings import MailSettings
from app.core.settings import settings
from app.modules.admin.access import access_router
from app.modules.admin.audit import audit_router
from app.modules.admin.users import users_router
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import RoleRecord, User
from app.modules.db import get_async_session

admin_router = APIRouter(dependencies=[Depends(require_admin)])


class AdminSystem(BaseModel):
    rate_limit_storage: Literal["memory", "redis"]
    files_storage: Literal["local", "s3"] | None
    mail_backend: Literal["console", "smtp"]
    auth_strategy: Literal["jwt", "redis"]
    error_tracking: bool
    log_format: Literal["text", "json"]


class AdminOverview(BaseModel):
    users: int
    active_users: int
    users_by_role: dict[str, int]
    system: AdminSystem


def system_info(modules: list[str]) -> AdminSystem:
    return AdminSystem(
        rate_limit_storage=config.RATE_LIMIT_STORAGE,
        files_storage=config.FILES_STORAGE if "files" in modules else None,
        mail_backend=settings.get(MailSettings).backend,
        auth_strategy=config.AUTH_STRATEGY,
        error_tracking=bool(config.SENTRY_DSN),
        log_format=config.LOG_FORMAT,
    )


@admin_router.get("/overview")
async def admin_overview(
    request: Request, session: AsyncSession = Depends(get_async_session)
) -> AdminOverview:
    rows = await session.execute(select(User.role, func.count()).group_by(User.role))
    by_role = dict(rows.all())
    roles = await session.scalars(
        select(RoleRecord.slug).order_by(RoleRecord.system.desc(), RoleRecord.name)
    )
    active = await session.scalar(select(func.count()).where(User.is_active.is_(True)))
    return AdminOverview(
        users=sum(by_role.values()),
        active_users=active or 0,
        users_by_role={slug: by_role.get(slug, 0) for slug in roles},
        system=system_info(request.app.state.modules),
    )


admin_router.include_router(users_router)
admin_router.include_router(access_router)
admin_router.include_router(audit_router)
