import pytest
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.core.i18n import translate
from app.core.languages import AVAILABLE_LANGUAGES
from app.modules.auth.manager import UserManager
from app.modules.auth.models import RoleRecord, User
from app.modules.auth.roles import Role
from app.modules.auth.schemas import MIN_PASSWORD_LENGTH
from tests.conftest import PRESENT, create_user, login, register

pytestmark = pytest.mark.modules("auth")


@pytest.mark.anyio
async def test_register_forces_user_role(auth_client):
    client, _ = auth_client

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "evil@example.com",
            "password": "password123",
            "role": "root",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "user"


@pytest.mark.anyio
async def test_login_and_current_user(auth_client):
    client, _ = auth_client

    await register(client, "user@example.com", "password123")
    signed_in = await login(client, "user@example.com", "password123")
    assert signed_in.status_code == 204, signed_in.text

    me = await client.get("/api/v1/auth/users/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "user@example.com"
    assert me.json()["role"] == "user"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("role", "areas", "admin_status"),
    [
        (Role.USER, ["user"], 403),
        (Role.MODERATOR, ["admin", "user"], 200),
        (Role.ROOT, ["admin", "user"], 200),
    ],
)
async def test_areas_by_role(auth_client, role, areas, admin_status):
    client, session_factory = auth_client
    await create_user(session_factory, "someone@example.com", role)
    await login(client, "someone@example.com", "password123")

    if "admin" not in PRESENT:
        areas = [area for area in areas if area != "admin"]
    me = await client.get("/api/v1/auth/users/me")
    assert me.json()["areas"] == areas

    assert (await client.get("/api/v1/user/summary")).status_code == 200
    if "admin" in PRESENT:
        for path in ("/api/v1/admin/overview", "/api/v1/admin/users"):
            assert (await client.get(path)).status_code == admin_status


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api/v1/admin/overview", marks=pytest.mark.modules("admin")),
        pytest.param("/api/v1/admin/users", marks=pytest.mark.modules("admin")),
        "/api/v1/user/summary",
    ],
)
async def test_guest_gets_401(auth_client, path):
    client, _ = auth_client
    assert (await client.get(path)).status_code == 401


@pytest.mark.anyio
@pytest.mark.modules("admin")
async def test_admin_overview_counts_users(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "root@example.com", Role.ROOT)
    await create_user(session_factory, "moderator@example.com", Role.MODERATOR)
    await register(client, "user@example.com", "password123")
    await login(client, "root@example.com", "password123")

    overview = (await client.get("/api/v1/admin/overview")).json()
    assert {key: overview[key] for key in ("users", "active_users", "users_by_role")} == {
        "users": 3,
        "active_users": 3,
        "users_by_role": {"root": 1, "moderator": 1, "user": 1},
    }


@pytest.mark.anyio
@pytest.mark.modules("admin")
async def test_admin_overview_shows_the_setup(auth_client, monkeypatch):
    from app.config import config
    from app.core.mail.settings import MailSettings
    from app.core.settings import settings

    client, session_factory = auth_client
    await create_user(session_factory, "root@example.com", Role.ROOT)
    await login(client, "root@example.com", "password123")

    system = (await client.get("/api/v1/admin/overview")).json()["system"]
    assert system == {
        "rate_limit_storage": "memory",
        "files_storage": "local" if "files" in PRESENT else None,
        "mail_backend": "console",
        "auth_strategy": "jwt",
        "error_tracking": False,
        "log_format": "text",
    }

    monkeypatch.setattr(config, "RATE_LIMIT_STORAGE", "redis")
    monkeypatch.setattr(config, "FILES_STORAGE", "s3")
    monkeypatch.setattr(config, "SENTRY_DSN", "https://public@sentry.example.invalid/1")
    monkeypatch.setattr(config, "LOG_FORMAT", "json")
    settings.set(MailSettings(backend="smtp"))
    system = (await client.get("/api/v1/admin/overview")).json()["system"]
    assert system["rate_limit_storage"] == "redis"
    assert system["files_storage"] == ("s3" if "files" in PRESENT else None)
    assert system["mail_backend"] == "smtp"
    assert system["error_tracking"] is True
    assert system["log_format"] == "json"


@pytest.mark.anyio
async def test_create_superuser_gets_root_role(auth_client):
    client, session_factory = auth_client

    async with session_factory() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        await manager.create_superuser({"email": "root@example.com", "password": "password123"})
        await session.commit()

    signed_in = await login(client, "root@example.com", "password123")
    assert signed_in.status_code == 204, signed_in.text
    assert (await client.get("/api/v1/auth/users/me")).json()["role"] == "root"


@pytest.mark.anyio
async def test_sign_in_is_rate_limited(auth_client):
    client, _ = auth_client
    for _ in range(10):
        assert (await login(client, "nobody@example.com", "password123")).status_code == 400
    response = await login(client, "nobody@example.com", "password123")
    assert response.status_code == 429
    assert response.json()["code"] == "too_many_requests"
    assert int(response.headers["Retry-After"]) > 0
    response = await client.post("/api/v1/auth/forgot-password", json={"email": "a@example.com"})
    assert response.status_code == 202


@pytest.mark.parametrize("value", [None, "", "change-me", "short-key"])
def test_weak_secret_key_stops_the_start(value):
    from app.modules.auth.backend import check_secret_key

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        check_secret_key(value)
    check_secret_key("x" * 32)


def test_manage_py_keeps_createroot_as_a_command():
    from typer.testing import CliRunner

    from manage import app as cli

    result = CliRunner().invoke(cli, ["createroot", "--help"])
    assert result.exit_code == 0, result.output


@pytest.mark.anyio
async def test_there_is_only_one_root(auth_client):
    _, session_factory = auth_client

    async with session_factory() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        await manager.create_superuser({"email": "root@example.com", "password": "password123"})
        with pytest.raises(ValueError, match="only one"):
            await manager.create_superuser({"email": "two@example.com", "password": "password123"})


@pytest.mark.anyio
async def test_users_by_id_are_not_exposed(auth_client):
    client, _ = auth_client

    other = "/api/v1/auth/users/00000000-0000-0000-0000-000000000001"
    for method in ("get", "patch", "delete"):
        assert (await client.request(method, other)).status_code == 404
    assert (await client.get("/api/v1/auth/users/me")).status_code == 401


@pytest.mark.anyio
async def test_password_rules(auth_client):
    client, _ = auth_client

    short = await register(client, "a@example.com", "x" * (MIN_PASSWORD_LENGTH - 1))
    assert short.status_code in (400, 422)
    with_email = await register(client, "Ann@Example.com", "ann@example.com-123")
    assert with_email.json()["code"] == "password_contains_email"


def test_password_length_in_the_messages():
    for code in AVAILABLE_LANGUAGES:
        assert str(MIN_PASSWORD_LENGTH) in translate("errors.password_too_short", code)


@pytest.mark.anyio
async def test_summary_of_a_user_with_a_role_made_in_the_admin(auth_client):
    client, session_factory = auth_client
    async with session_factory() as session:
        session.add(RoleRecord(slug="sales", name="Sales", permissions=[]))
        await session.commit()
    await create_user(session_factory, "sales@example.com", "sales")
    await login(client, "sales@example.com", "password123")

    summary = await client.get("/api/v1/user/summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["role"] == "sales"
