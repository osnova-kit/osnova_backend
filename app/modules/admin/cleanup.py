from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.modules.admin.models import AuditRecord
from app.modules.db import utc_now
from app.settings import RetentionSettings


async def cleanup(session: AsyncSession) -> int:
    days = settings.get(RetentionSettings).audit_days
    if days <= 0:
        return 0
    before = utc_now() - timedelta(days=days)
    result = await session.execute(delete(AuditRecord).where(AuditRecord.created_at < before))
    return result.rowcount
