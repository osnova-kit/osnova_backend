import uuid
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import translate_optional
from app.core.rate_limit import client_address
from app.core.settings import SECRET_MASK
from app.modules.admin.models import AuditRecord
from app.modules.auth.dependencies import current_user, require
from app.modules.auth.models import User
from app.modules.auth.permissions import permission
from app.modules.db import get_async_session
from app.modules.db.query import contains, listed, ordered, sort_options

AUDIT_READ = permission("audit.read")

_actions: set[str] = set()


def audit_action(name: str) -> str:
    """Declare an action of the audit log, e.g. "users.block"; returns the name."""
    _actions.add(name)
    return name


def all_actions() -> set[str]:
    return set(_actions)


def diff(
    before: dict[str, Any], after: dict[str, Any], secret: Iterable[str] = ()
) -> dict[str, list[Any]]:
    """Fields that differ, as ``{field: [before, after]}``; secret ones are masked."""
    hidden = set(secret)
    return {
        key: [SECRET_MASK, SECRET_MASK] if key in hidden else [before.get(key), after.get(key)]
        for key in sorted(before.keys() | after.keys())
        if before.get(key) != after.get(key)
    }


class Audit:
    """Dependency that adds a record of the signed-in user's action to the request session."""

    def __init__(
        self,
        request: Request,
        actor: User = Depends(current_user),
        session: AsyncSession = Depends(get_async_session),
    ):
        self.actor = actor
        self.session = session
        address = client_address(request)
        self.ip = None if address == "unknown" else address

    def __call__(
        self,
        action: str,
        *,
        target_id: Any = None,
        target: str | None = None,
        changes: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            AuditRecord(
                actor_id=self.actor.id,
                actor_email=self.actor.email,
                ip=self.ip,
                action=action,
                target_id=None if target_id is None else str(target_id),
                target=target,
                changes=changes or None,
            )
        )


class AuditRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_id: uuid.UUID | None
    actor_email: str
    ip: str | None
    action: str
    title: str
    target_id: str | None
    target: str | None
    changes: dict[str, Any] | None


class AuditPage(BaseModel):
    items: list[AuditRead]
    total: int


class AuditAction(BaseModel):
    name: str
    title: str


def _title(action: str) -> str:
    return translate_optional(f"audit.{action}") or action


def _read(record: AuditRecord) -> AuditRead:
    fields = {name: getattr(record, name) for name in AuditRead.model_fields if name != "title"}
    return AuditRead(**fields, title=_title(record.action))


SORT_COLUMNS = {
    "created_at": AuditRecord.created_at,
    "action": AuditRecord.action,
    "actor_email": AuditRecord.actor_email,
}
AuditSort = sort_options(SORT_COLUMNS)

audit_router = APIRouter(prefix="/audit", dependencies=[Depends(require(AUDIT_READ))])


@audit_router.get("/actions")
async def list_actions() -> list[AuditAction]:
    return [AuditAction(name=name, title=_title(name)) for name in sorted(_actions)]


def _conditions(
    q: str,
    action: str | None,
    actor: uuid.UUID | None,
    since: date | None,
    until: date | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if search := q.strip():
        conditions.append(
            or_(contains(AuditRecord.actor_email, search), contains(AuditRecord.target, search))
        )
    if actions := listed(action):
        conditions.append(AuditRecord.action.in_(actions))
    if actor is not None:
        conditions.append(AuditRecord.actor_id == actor)
    if since is not None:
        conditions.append(AuditRecord.created_at >= datetime.combine(since, time()))
    if until is not None:
        conditions.append(AuditRecord.created_at < datetime.combine(until + timedelta(1), time()))
    return conditions


@audit_router.get("")
async def list_audit(
    q: str = Query("", max_length=100, description="Part of the actor email or the target"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: AuditSort = "-created_at",  # type: ignore[valid-type]
    action: str | None = Query(None, description="Comma-separated actions"),
    actor: uuid.UUID | None = Query(None, description="The id of who acted"),
    since: date | None = Query(None, description="From this day (UTC)"),
    until: date | None = Query(None, description="Up to and including this day (UTC)"),
    session: AsyncSession = Depends(get_async_session),
) -> AuditPage:
    conditions = _conditions(q, action, actor, since, until)
    total = await session.scalar(select(func.count()).select_from(AuditRecord).where(*conditions))
    rows = await session.scalars(
        select(AuditRecord)
        .where(*conditions)
        .order_by(ordered(SORT_COLUMNS, sort))
        .order_by(AuditRecord.created_at.desc(), AuditRecord.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    return AuditPage(
        items=[_read(record) for record in rows],
        total=total or 0,
    )
