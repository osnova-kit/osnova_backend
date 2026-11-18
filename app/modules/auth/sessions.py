import secrets
import time
import uuid
from datetime import UTC, datetime

import jwt
from fastapi_users import BaseUserManager, exceptions
from fastapi_users.authentication import JWTStrategy, RedisStrategy
from fastapi_users.jwt import decode_jwt, generate_jwt

from app.modules.auth.models import User
from app.modules.db import utc_now

UserManager = BaseUserManager[User, uuid.UUID]


def now_for_sessions() -> datetime:
    """The moment to store in `sessions_valid_after` (whole seconds, like `iat`)."""
    return utc_now().replace(microsecond=0)


async def _get_user(user_manager: UserManager, user_id: str | None) -> User | None:
    if user_id is None:
        return None
    try:
        return await user_manager.get(user_manager.parse_id(user_id))
    except (exceptions.UserNotExists, exceptions.InvalidID):
        return None


def session_is_valid(user: User, issued_at: int | None) -> bool:
    if user.sessions_valid_after is None:
        return True
    if issued_at is None:
        return False
    return issued_at >= int(user.sessions_valid_after.replace(tzinfo=UTC).timestamp())


class SessionJWTStrategy(JWTStrategy):
    async def write_token(self, user: User) -> str:
        data = {"sub": str(user.id), "aud": self.token_audience, "iat": int(time.time())}
        return generate_jwt(data, self.encode_key, self.lifetime_seconds, algorithm=self.algorithm)

    async def read_token(self, token: str | None, user_manager: UserManager) -> User | None:
        if token is None:
            return None
        try:
            data = decode_jwt(
                token, self.decode_key, self.token_audience, algorithms=[self.algorithm]
            )
        except jwt.PyJWTError:
            return None
        user = await _get_user(user_manager, data.get("sub"))
        return user if user and session_is_valid(user, data.get("iat")) else None


class SessionRedisStrategy(RedisStrategy):
    """Stores "<user id>:<issued at>" under the token."""

    async def write_token(self, user: User) -> str:
        token = secrets.token_urlsafe()
        await self.redis.set(
            f"{self.key_prefix}{token}", f"{user.id}:{int(time.time())}", ex=self.lifetime_seconds
        )
        return token

    async def read_token(self, token: str | None, user_manager: UserManager) -> User | None:
        if token is None:
            return None
        value = await self.redis.get(f"{self.key_prefix}{token}")
        if value is None:
            return None
        user_id, _, issued = value.partition(":")
        user = await _get_user(user_manager, user_id)
        return user if user and session_is_valid(user, int(issued) if issued else None) else None
