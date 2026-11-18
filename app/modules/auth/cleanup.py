from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.db import utc_now
from app.settings import RetentionSettings


async def cleanup(session: AsyncSession) -> int:
    """Delete the accounts that never confirmed the email and never signed in, once the
    retention days have passed. One that changed its email is unconfirmed again, but it
    has signed in and may own data, so it stays."""
    days = settings.get(RetentionSettings).unverified_account_days
    if days <= 0:
        return 0
    before = utc_now() - timedelta(days=days)
    result = await session.execute(
        delete(User).where(
            User.is_verified.is_(False),
            User.role == Role.USER,
            User.last_login.is_(None),
            User.date_created < before,
        )
    )
    return result.rowcount
