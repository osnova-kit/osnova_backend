import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import Depends
from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Table
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.modules.auth.encryption import EncryptedText
from app.modules.auth.permissions import all_permissions, everyone_permissions
from app.modules.auth.roles import Role
from app.modules.db import Base, get_async_session, utc_now


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    __tablename__ = "oauth_accounts"

    access_token: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)

    @declared_attr
    def user_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
        )


class RoleRecord(Base):
    __tablename__ = "roles"

    slug: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    system: Mapped[bool] = mapped_column(default=False)


def role_permissions(role: RoleRecord) -> set[str]:
    """What a role gives, as stored (also of modules switched off now). The role of
    every new account gives only permissions meant for everyone: staff permissions
    stored there by mistake do nothing."""
    if role.slug == Role.USER:
        return set(everyone_permissions().intersection(role.permissions))
    return set(role.permissions)


group_roles = Table(
    "group_roles",
    Base.metadata,
    Column("group_id", GUID, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(50), ForeignKey("roles.slug", ondelete="CASCADE"), primary_key=True),
)

user_groups = Table(
    "user_groups",
    Base.metadata,
    Column("user_id", GUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "group_id",
        GUID,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    roles: Mapped[list[RoleRecord]] = relationship(
        secondary=group_roles, lazy="selectin", order_by=RoleRecord.slug
    )


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    role: Mapped[str] = mapped_column(
        String(50), ForeignKey("roles.slug"), default=Role.USER.value, index=True
    )
    role_record: Mapped[RoleRecord] = relationship(lazy="selectin")
    groups: Mapped[list[Group]] = relationship(
        secondary=user_groups, lazy="selectin", order_by=Group.name
    )
    date_created: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=utc_now,
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sessions_valid_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    has_password: Mapped[bool] = mapped_column(default=True)
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def held_permissions(self) -> frozenset[str]:
        """Every permission of their role and of the roles of their groups, also those
        of modules switched off now (they work again when the module is on)."""
        held = role_permissions(self.role_record)
        for group in self.groups:
            for role in group.roles:
                held.update(role_permissions(role))
        return frozenset(held)

    @property
    def permissions(self) -> frozenset[str]:
        """What the user may do now: the held permissions of the enabled modules; root
        may do everything."""
        if self.role == Role.ROOT:
            return all_permissions()
        return all_permissions().intersection(self.held_permissions)


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase]:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)
