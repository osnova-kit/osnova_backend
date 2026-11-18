from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User

DeleteHook = Callable[[AsyncSession, User], Awaitable[None]]

delete_hooks: list[DeleteHook] = []


def on_user_delete(hook: DeleteHook) -> None:
    """Run ``hook`` before an account is deleted (e.g. to remove its files).

    A hook added again (the app is created more than once in tests) is kept once."""
    if hook not in delete_hooks:
        delete_hooks.append(hook)
