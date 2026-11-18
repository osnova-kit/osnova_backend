# Osnova documentation

The developer guide of Osnova: how the template is built, how to run it, and how to add
your own code to it. This file covers the backend and the whole stack; the interface has
its own guide in [osnova_frontend/DOCUMENTATION.md](https://github.com/osnova-kit/osnova_frontend/blob/main/DOCUMENTATION.md).

## Contents

1. [Overview](#1-overview)
2. [Getting started](#2-getting-started)
3. [Profiles](#3-profiles)
4. [Modules and capabilities](#4-modules-and-capabilities)
5. [Configuration](#5-configuration)
6. [API](#6-api)
7. [Users and access](#7-users-and-access)
8. [Building blocks](#8-building-blocks)
9. [Docker](#9-docker)
10. [Deployment](#10-deployment)
11. [Backups](#11-backups)
12. [Upgrading and versions](#12-upgrading-and-versions)

---

## 1. Overview

Osnova is a **template**, not a product. A developer takes two repositories, picks a
profile, switches capabilities on in `.env` and writes the project's own pages and
endpoints on day one, without spending the first weeks on layout, languages, forms,
sign-in, the admin, Docker and CI.

It is made for a developer or a small team building sites and web applications: a landing
page or a company site, an internal tool, a client portal, a SaaS with an admin area.

| Repository | Purpose | Stack |
|---|---|---|
| **osnova_backend** | API, business logic, data | Python 3.13 · FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · Alembic · fastapi-users · Celery · Redis |
| **osnova_frontend** | Web interface (SPA) | React 19 · TypeScript · Vite · Ant Design · Zustand · React Router · react-i18next |

The two talk only through the API. Infrastructure: Docker Compose, nginx for the site and
as the API proxy, Caddy for HTTPS, GitHub Actions for CI.

### Principles

- **Start small, grow without rewriting.** Moving from `minimal` to `standard` to
  `scalable` changes configuration and infrastructure, not the architecture.
- **Module = folder.** Each optional capability is one folder on the backend and one on
  the frontend, loaded only when enabled; `make strip` and `npm run strip` delete the ones
  a project does not use.
- **The backend is the source of truth.** Capabilities, languages, forms, settings and
  permissions come from the backend; the frontend builds its routes and UI from
  `GET /api/v1/bootstrap`.
- **Foundations, not full integrations.** Every tool (email, OAuth, files, tasks,
  notifications, leads) gets a working base with one simple implementation and a place for
  others.
- **Lightweight.** A disabled module is not imported, and its dependencies
  (`requirements/<module>.txt`) need not be installed.
- **Production-ready from the start.** Docker images, health and readiness checks, request
  ids, JSON logs, security headers, HTTPS, backups, error tracking, CI.


---

## 2. Getting started

### In Docker

The whole standard stack: PostgreSQL, Redis, the Celery worker and beat, the site and its
admin. Requirements: Docker with the Compose plugin, `git`, `make`, `python3`.

```bash
git clone https://github.com/osnova-kit/osnova_backend.git
git clone https://github.com/osnova-kit/osnova_frontend.git   # next to it
cd osnova_backend
make init          # .env: standard profile, every capability on, random secrets
make up-standard   # builds and starts everything, applies the migrations
make createroot    # the first user (asks for an email and a password)
```

Open `http://localhost:8080`, sign in, and the admin is at `/admin`. `make init` never
overwrites an existing `.env`; edit it to turn capabilities off
([Configuration](#5-configuration)). `make down` stops the stack. A server with HTTPS:
[Deployment](#10-deployment).

### Local development

Requirements: Python 3.13; Node.js 24 for the frontend; PostgreSQL only for modules that
need a database.

```bash
make install              # venv + requirements/dev.txt (all modules + tools)
cp .env.example .env      # optional: an empty .env runs the minimal profile
make dev-all              # API + frontend dev server; Ctrl+C stops both
```

- Frontend: `http://localhost:5173`
- API: `http://localhost:8000/api/v1`, docs at `http://localhost:8000/docs` (with
  `DEBUG=true`)

`make dev` starts only the API (host and port from `APP_HOST` / `APP_PORT`). For the
minimal profile alone `pip install -r requirements/base.txt` is enough.

With a database and users:

```bash
# .env: DATABASE_URL=postgresql+asyncpg://osnova:osnova@localhost:5432/osnova
#       AUTH_ENABLED=true, SECRET_KEY=<long random value>
alembic upgrade head          # every migration in migrations/versions
python manage.py createroot   # the first user with the root role
```

---

## 3. Profiles

The same code runs in three profiles; moving between them changes configuration and the
services around the app. `APP_PROFILE` is checked at start: a mismatch with the setup
(e.g. `minimal` with a `DATABASE_URL`) is logged as a warning.

### Minimal

```
Frontend ──▶ FastAPI
```

Sites, landing pages, small services and simple APIs. No database, Redis or workers; only
`requirements/base.txt` is installed. Included: languages, forms with validation, rate
limit and honeypot, unified errors, request ids, OpenAPI for the frontend. Every optional
module needs a database, so all of them are off.

### Standard

```
                 ┌───── PostgreSQL
Frontend ──▶ FastAPI
                 ├───── Redis
                 └───── Celery worker and beat
```

The main profile for full applications. Each tool is a working foundation:

| Tool | What you get |
|---|---|
| Users | sign-up, sign-in (JWT cookie or Redis sessions), email confirmation, password reset, Google, a profile that manages the account |
| Areas | public, user (any signed-in user) and admin (the `admin.access` permission) with guards on both sides |
| Permissions | named actions (`leads.read`, `users.block`) checked by `require(...)`; roles and groups edited in the admin; `root` has all |
| Admin | overview, users, roles, groups, audit log, leads, delivery channels, settings |
| Settings | typed groups edited in the admin, no migration per field |
| Leads | form submissions stored, delivered to email / Telegram / webhook by a task |
| Files | private uploads, local disk or any S3-compatible bucket |
| Notifications | in-app bell, email as a second channel |
| Tasks | Celery worker and beat; email and lead delivery retried while a service is down; a nightly cleanup |

### Scalable

```
                Frontend (nginx) or Caddy
                 /          \
            FastAPI        FastAPI    (replicas)
                 \          /
             PostgreSQL · Redis
```

`standard` with several backend replicas: the backend publishes no host port, and the
frontend nginx (or Caddy with HTTPS) spreads requests over the replicas through Docker
DNS. What changes with replicas:

| | Behaviour with several replicas |
|---|---|
| Sessions | JWT cookies are stateless; Redis sessions are shared. A password change or reset and **Sign out everywhere** end every session of the user (`sessions_valid_after`); a single sign-out ends one JWT only when it expires, a Redis session at once |
| Settings | each replica reloads them every `SETTINGS_REFRESH_SECONDS` (30 s) |
| Background work | the Celery worker is a separate service; tasks go through Redis |
| Readiness | `GET /api/v1/ready` checks the database, Redis sessions and the task broker of the enabled modules: route traffic by it |
| Rate limits | count in Redis with `RATE_LIMIT_STORAGE=redis` (Docker Compose sets it), shared by every replica; while Redis is down requests are let through and each replica counts on its own |
| Migrations | `make migrate`, or `RUN_MIGRATIONS=true`: replicas that start together take a PostgreSQL lock and migrate one after another |
| **Files** | `FILES_STORAGE=s3`: with `APP_PROFILE=scalable` local files are refused at start |
| **Lead delivery without tasks** | runs in the replica that got the form; turn background tasks on for retries |

---

## 4. Modules and capabilities

### Capabilities

Each capability is an environment flag. The backend collects them and sends them to the
frontend in `/bootstrap`; when one is off, the frontend creates none of its routes or UI.

```
.env flags                 app/core/bootstrap.py        GET /api/v1/bootstrap      Frontend
AUTH_ENABLED          ──▶  BootstrapFeatures       ──▶  { application, profile, ──▶ routes + UI
ADMIN_ENABLED                                             i18n, features }
FILES_ENABLED
NOTIFICATIONS_ENABLED
BACKGROUND_TASKS_ENABLED
```

| Capability | Off: the frontend has no |
|---|---|
| `authentication` | `/login`, `/register`, protected routes (every page is public) |
| `admin` | `/admin` and its menu items |
| `files` | My files |
| `notifications` | the bell; admins hear about new leads only by email |
| `background_tasks` | nothing visible |

| Flag | Minimal | Standard | Scalable |
|---|:---:|:---:|:---:|
| `AUTH_ENABLED` | ✕ | ✓ | ✓ |
| `ADMIN_ENABLED` | ✕ | ✓ | ✓ |
| `FILES_ENABLED` | ✕ | optional | optional |
| `NOTIFICATIONS_ENABLED` | ✕ | optional | optional |
| `BACKGROUND_TASKS_ENABLED` | ✕ | ✓ | ✓ |
| PostgreSQL / Redis | ✕ | ✓ | ✓ |
| Several backend replicas | ✕ | ✕ | ✓ |

A module that lacks what it needs stops the start with a clear message, e.g.
`AUTH_ENABLED=true` without `DATABASE_URL`.

### The module registry

Every optional capability is a package `app/modules/<name>/` that exposes
`register(app)`. The registry in `app/core/modules.py` imports it only when it is enabled
and checks the modules it needs (`requires`): `auth` needs `db`; `admin`, `files` and
`notifications` need `auth`. The core never imports a module, so a disabled one costs
nothing at runtime. In the minimal profile no SQLAlchemy, fastapi-users, Celery or Redis is
imported; `tests/test_modules.py` checks it.

### Project layout

```
osnova_backend/
├── app/
│   ├── core/              # always loaded: bootstrap, health, readiness, languages,
│   │                      # errors, forms, mail, rate limit, request id, module registry
│   ├── modules/           # optional modules, one folder each
│   │   ├── db/            # SQLAlchemy (async) sessions, nightly cleanup ← DATABASE_URL
│   │   ├── auth/          # fastapi-users, permissions, roles            ← AUTH_ENABLED
│   │   ├── admin/         # admin API: users, roles, groups, audit log   ← ADMIN_ENABLED
│   │   ├── settings/      # settings stored in the database              ← ADMIN_ENABLED
│   │   ├── entities/      # configurable entities (one table)            ← ADMIN_ENABLED
│   │   ├── leads/         # submissions, delivery channels               ← ADMIN_ENABLED
│   │   ├── files/         # files: local or S3 storage                   ← FILES_ENABLED
│   │   ├── notifications/ # in-app notifications, channels               ← NOTIFICATIONS_ENABLED
│   │   └── tasks/         # Celery app, tasks, schedule                  ← BACKGROUND_TASKS_ENABLED
│   ├── user/              # user area API (any signed-in user)
│   ├── forms.py           # the project's forms
│   ├── settings.py        # settings groups edited in the admin (site, languages, retention)
│   ├── config.py          # settings from .env (every value has a default)
│   └── __init__.py        # application factory
├── migrations/            # Alembic migrations
├── requirements/          # per module: base, db, auth, files, tasks, redis;
│                          # standard (all modules), sentry (optional), dev (all + tools)
├── scripts/               # openapi.py, init_env.py, strip.py, upgrade.py, check_stack.py,
│                          # backup.sh, restore.sh
├── deploy/Caddyfile       # the HTTPS proxy (docker-compose.https.yml)
├── tests/
├── openapi.json           # API schema, committed (the frontend generates types from it)
├── Dockerfile             # backend image (ARG REQUIREMENTS=base|standard)
├── docker-compose.yml     # base compose, enough for minimal
├── docker-compose.datastores.yml  # PostgreSQL, Redis, worker, beat (standard / scalable)
├── docker-compose.https.yml       # Caddy with Let's Encrypt (HTTPS=1)
├── Makefile               # every command: make help
└── manage.py              # CLI: createroot, cleanup, rotate-secrets
```

### Removing the modules a project does not use

Turn their flags off in `.env`, then `make strip` lists what goes and
`make strip ARGS=--apply` removes it (it asks first and runs only on a clean git working
tree, so `git checkout . && git clean -fd` undoes it). Or name them:
`make strip ARGS="files tasks --apply"`. A module goes with the modules that need it
(`auth` takes everything but `db`, which always stays).

Removed: the packages, their entries in `MODULES`, their requirements files, the test files
marked with them, the `strip:begin` / `strip:end` blocks of compose and CI (the worker and
beat go with `tasks`); a new migration drops their tables with the data, and
`openapi.json` is written again. Settings in `app/config.py` and `.env.example` and the
docs stay. The frontend has the same command (`npm run strip`).

### Adding a capability

1. A flag in `app/config.py` and `.env.example`.
2. A package `app/modules/<name>/` with `register(app)` and an entry in `MODULES`.
3. Dependencies in `requirements/<name>.txt`, included from `standard.txt`.
4. A field in `BootstrapFeatures` (`app/core/bootstrap.py`).
5. Its routes and UI in the frontend, by the flag.

A test file of a module has `pytestmark = pytest.mark.modules("<name>")`; a test that also
needs another module has its own `@pytest.mark.modules(...)` and imports it inside, so it
is skipped once that module is gone.

---

## 5. Configuration

`.env` holds infrastructure, secrets and capability flags. Every setting has a default in
`app/config.py` and is described in [`.env.example`](.env.example). What the site owner
changes at runtime (site name, languages, mail, captcha, limits, retention, file limits,
notification channels) lives in Admin → Settings; the values in `.env` are the initial ones.

| Variable | Purpose |
|---|---|
| `APP_NAME`, `APP_PROFILE` | Name; profile (`minimal` / `standard` / `scalable`) |
| `APP_HOST`, `APP_PORT`, `DEBUG` | Local server address; `DEBUG=true` serves `/docs`, `/redoc` and `/openapi.json` (off in production) |
| `LOG_FORMAT`, `LOG_LEVEL` | Logs to stdout: `text` or `json` (one object per line: time, level, logger, message, `request_id`, extra fields, traceback); the worker and beat log the same way |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE` | Error tracking, off while the DSN is empty ([Error tracking](#error-tracking)) |
| `AUTH_ENABLED`, `ADMIN_ENABLED`, `FILES_ENABLED`, `NOTIFICATIONS_ENABLED`, `BACKGROUND_TASKS_ENABLED` | [Capabilities](#capabilities) |
| `LANGUAGES`, `DEFAULT_LANGUAGE` | Enabled interface languages and the default; Admin → Settings → Languages |
| `CORS_ORIGINS` | Allowed origins for local development, comma-separated |
| `FORMS_DELIVERY`, `FORMS_FILE` | Where submissions go without the admin: `log`, or `file` (also JSON lines in `FORMS_FILE`); with the admin they are stored as leads too |
| `FORMS_RATE_LIMIT`, `AUTH_RATE_LIMIT` | Submissions per IP and form; requests per IP to sign-in, sign-up, password reset and email confirmation (e.g. `5/minute`, empty: no limit); Admin → Settings → Protection |
| `WEBHOOK_ALLOW_PRIVATE` | Lead webhooks may reach the private network (off: public addresses only) |
| `CAPTCHA_PROVIDER`, `CAPTCHA_SITE_KEY`, `CAPTCHA_SECRET_KEY` | Captcha on forms and sign-up ([Captcha](#captcha)) |
| `DATABASE_URL`, `DB_ECHO` | Database (turns on the `db` module), SQL logging |
| `SECRET_KEY`, `OLD_SECRET_KEYS` | Signs sessions and links and derives the key of stored secrets (at least 32 characters, not the example value, or the app does not start); previous keys while secrets are moved ([Stored secrets](#stored-secrets)) |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `AUTH_STRATEGY`, `COOKIE_SECURE` | Token signing and lifetime; `jwt` or `redis` sessions; `Secure` cookie (HTTPS only) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Sign-in with Google ([Google](#sign-in-with-google)) |
| `REDIS_URL`, `RATE_LIMIT_STORAGE` | Redis; where rate limits count: `memory` (each process) or `redis` (shared) |
| `FRONTEND_URL` | Public address of the frontend, for links in emails |
| `MAIL_BACKEND`, `MAIL_FROM`, `SMTP_*` | `console` (the log) or `smtp`; Admin → Settings → Mail |
| `NOTIFICATIONS_CHANNELS` | Where notifications go besides the bell (`in_app`, `in_app,email`); Admin → Settings → Notifications |
| `NOTIFICATIONS_KEEP_DAYS`, `UNVERIFIED_ACCOUNT_DAYS`, `AUDIT_KEEP_DAYS` | [Nightly cleanup](#nightly-cleanup); Admin → Settings → Data retention |
| `SETTINGS_REFRESH_SECONDS` | How often each process reloads settings changed in the admin |
| `FILES_STORAGE`, `FILES_DIR`, `FILES_MAX_SIZE_MB`, `FILES_ALLOWED_TYPES` | `local` or `s3`; size and type limits; Admin → Settings → Files |
| `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_LINK_SECONDS` | The bucket for `FILES_STORAGE=s3`; lifetime of download links |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Celery (a broker is required with background tasks) |

Docker Compose only: `FRONTEND_PORT`, `SITE_URL` (public origin for canonical links, link
previews and `sitemap.xml`; with `HTTPS=1` the certificate's host), `ANALYTICS_SCRIPT`,
`CSP_EXTRA_ORIGINS`, `FRONTEND_SENTRY_DSN`, `EXTRA_REQUIREMENTS`, `HTTP_PORT` /
`HTTPS_PORT`, `POSTGRES_*`, `RUN_MIGRATIONS`, `FORWARDED_ALLOW_IPS`.

---

## 6. API

Prefix `/api/v1`. The full schema is in [`openapi.json`](openapi.json) and at `/docs`
(`DEBUG=true`). Errors share one format: `{ code, message, fields?, request_id? }`, with
`message` in the user's language (`Accept-Language`). Every response carries
`X-Request-ID`.

| Method | Path | Purpose | When |
|---|---|---|---|
| GET | `/bootstrap` | Site name and contacts, version, profile, capabilities, languages, sign-in providers, captcha | always |
| GET | `/health` | Liveness: the process runs | always |
| GET | `/ready` | Readiness: the database, Redis sessions and the task broker of the enabled modules answer; 503 otherwise | always |
| GET / POST | `/forms/{name}` | Form description for the frontend; validate and deliver a form (`422` with per-field errors) | always |
| — | `/auth/*` | Sign-up, sign-in, sign-out, password reset, verification; `PATCH /auth/users/me` changes only the name and the `language` | `AUTH_ENABLED` |
| — | `/auth/me/*` | The user's own account, each with the current password: `POST password` (other sessions end), `POST email` (confirmed again, the old address is told), `POST sign-out-everywhere`, `DELETE` (with files and notifications; root cannot) | `AUTH_ENABLED` |
| GET | `/auth/google/authorize`, `/auth/google/callback` | Sign-in with Google | `GOOGLE_CLIENT_*` set |
| GET | `/user/*` | User area: any signed-in user (example: `/user/summary`) | `AUTH_ENABLED` |
| GET | `/admin/overview` | Counters and how the installation is set up (no secrets) | `ADMIN_ENABLED` |
| GET / PATCH | `/admin/users`, `/admin/users/{id}`, `/admin/users/export` | Users: search, filters, sort, pages, CSV; block, role and groups | `ADMIN_ENABLED` |
| GET / POST / PUT / DELETE | `/admin/roles`, `/admin/groups`, `/admin/permissions` | Roles, groups and the permissions with their texts | `ADMIN_ENABLED` |
| GET | `/admin/audit`, `/admin/audit/actions` | Audit log of admin actions | `ADMIN_ENABLED` |
| GET / PATCH / DELETE | `/admin/leads`, `/admin/leads/{id}`, `/admin/leads/forms`, `/admin/leads/export` | Form submissions: search, filters, status, delete, CSV | `ADMIN_ENABLED` |
| GET / POST / PUT / DELETE | `/admin/entities`, `/admin/entities/types`, `/admin/leads/channels/{id}/test` | Configurable entities (lead channels) with form descriptions; a test message | `ADMIN_ENABLED` |
| GET / PUT / POST | `/admin/settings`, `/admin/settings/{group}`, `/admin/settings/mail/test` | Settings groups with form descriptions; a test email | `ADMIN_ENABLED` |
| GET / POST / DELETE | `/notifications`, `/notifications/unread`, `/notifications/read`, `/notifications/{id}/read`, `/notifications/{id}` | The user's notifications, unread count, mark read, delete | `NOTIFICATIONS_ENABLED` |
| POST / GET / DELETE | `/files`, `/files/{id}` | The user's files: upload, list, download (S3: a redirect to a short-lived link), delete | `FILES_ENABLED` |

Lists of the admin (`users`, `leads`, `audit`) take the same query as the frontend
tables: `q` (search), filters by column, `sort` (`field` or `-field`), `page`, `size`. Their
`/export` endpoints answer a CSV of everything the list shows with the same query;
`delimiter=comma` or `semicolon`, by the request language when not given.

After an API change run `make openapi` and, in the frontend, `npm run generate:client`;
the tests fail while `openapi.json` is out of date.

---

## 7. Users and access

### Accounts

Sign-up sends a confirmation link; `forgot-password` sends a reset link; both open
frontend pages (`/verify-email`, `/reset-password`) in the user's language. Sessions are a
JWT cookie by default (`AUTH_STRATEGY=redis` keeps them in Redis). The user's own account
is managed under `/auth/me/*`, each change with the current password: a new password ends
the other sessions, a new email is confirmed again and the old address gets a notice,
**Sign out everywhere** ends every session, and deleting the account removes its files and
notifications for good. An account made through Google has no password of its own
(`has_password` is false) and confirms the deletion with its email until it sets one with
`forgot-password`. Root cannot delete itself: the site needs one.

Sessions in the database (a list of devices, signing out of one) are not built in, and are
a small change: an `AccessToken` model from fastapi-users'
`SQLAlchemyBaseAccessTokenTableUUID` and its migration, a `database` value of
`AUTH_STRATEGY` with a branch in `get_strategy()` (`app/modules/auth/backend.py`) that
returns a subclass of `DatabaseStrategy`, and a `cleanup.py` for expired tokens. The
subclass's `read_token` has to check `session_is_valid` (`app/modules/auth/sessions.py`)
like the two built-in strategies do, or a new password and **Sign out everywhere** do not
end those sessions.

Every user has a `language`: emails and notifications go in it, also those caused by
someone else's request. It is chosen in the profile or with the header switcher.

### Sign-in with Google

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → OAuth
   consent screen: create it (External; app name, support email).
2. Credentials → Create credentials → OAuth client ID → Web application. Authorized
   redirect URI: `<FRONTEND_URL>/oauth/google/callback`, e.g.
   `http://localhost:5173/oauth/google/callback` for development and
   `https://example.com/oauth/google/callback` for the site.
3. Put the client ID and secret into `.env` as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
   and restart. `/bootstrap` then lists `"google"` in `auth_providers`, and the sign-in page
   shows the button.

No Google API has to be enabled: the email comes from the OpenID Connect userinfo
endpoint, and only an email Google has confirmed is accepted. A new Google user gets an
account with a confirmed email; an existing account with the same email is linked. If that
account never confirmed its email (anyone can sign up with someone else's address), it is
taken over: it gets a new random password, so the one typed at sign-up stops working.
Another provider: a client from `httpx_oauth.clients` in `app/modules/auth/oauth.py` and its
keys in `app/config.py`.

### Areas

| Area | Who | Backend | Frontend |
|---|---|---|---|
| Public | everyone | routes without a dependency | pages without a guard |
| User | any signed-in user | `user_router` (`app/user/routes.py`) | `ProtectedRoute` |
| Admin | the `admin.access` permission | `admin_router` (`app/modules/admin/routes.py`) | `/admin` |

Both routers check access for every endpoint added to them. After sign-in staff lands in
the admin and can switch to the user area; everyone else lands on the home page. A new
domain of the project is a package like `app/user/` with its own router.

### Permissions

A permission is a named action. A module declares its own where it uses them and asks for
them with one dependency; `GET /auth/users/me` lists the user's `permissions` for the
frontend.

```python
from app.modules.auth.dependencies import require
from app.modules.auth.permissions import ADMIN_ACCESS, permission

ORDERS_READ = permission("orders.read")
router = APIRouter(dependencies=[Depends(require(ADMIN_ACCESS, ORDERS_READ))])
```

Only declared names exist, so a typo fails at import. A text for a new permission goes to
the `permissions` and `permission_areas` sections of `app/core/locales/*.json` (without it
the name is shown).

A role is a row of the `roles` table with a set of permissions; a user has one role
(`users.role`). A group gives its roles to everyone in it, on top of their own role: what a
user may do is the sum. Three roles come with the template: `root` always has every
permission (also those declared later), `user` has none and is given at sign-up,
`moderator` starts with the ones marked below. Roles and groups are edited in Admin →
Access and given to users in Admin → Users.

Nobody hands out more than they have: a role, a group or a user is changed only by someone
who has every permission involved, also those a role keeps from a module that is switched
off (they work again with the module). The `user` role is given to everyone, so it holds
only permissions declared with `permission("...", everyone=True)`: a person becomes staff
with another role or a group. `root` is not edited and is assigned only with
`manage.py createroot`; the built-in roles are not renamed or deleted.

| Permission | Allows | `moderator` |
|---|---|---|
| `admin.access` | open the admin area | yes |
| `users.read`, `users.export`, `users.block` | the users list, its CSV, block / unblock | yes |
| `users.roles` | give roles and groups; block users who have a role other than `user` or are in a group | |
| `roles.manage` | create and change roles and groups | |
| `leads.read`, `leads.manage`, `leads.export` | leads: see, mark and delete, CSV | yes |
| `entities.manage` | create and change entities (lead channels), send a test message | |
| `settings.<group>` | change one settings group (`site`, `languages`, `mail`, `protection`, `retention`, `files`, `notifications`); see the groups with secrets | |
| `files.manage` | open and delete files of other users | yes |
| `audit.read` | read the audit log | |

### Audit log

Admin actions are recorded with who, when, from which IP and what changed
(`{field: [before, after]}`; secrets only as changed, no data of visitors). A new action:

```python
CANCEL = audit_action("orders.cancel")

async def cancel(..., audit: Audit = Depends()):
    audit(CANCEL, target_id=str(order.id), target=order.number, changes=diff(before, after))
```

before the commit (`app/modules/admin/audit.py`), and its text in the `audit` section of
`app/core/locales/*.json`.

---

## 8. Building blocks

### Forms

A form is described once on the backend and rendered by the frontend:

```python
# app/forms.py
Form(
    name="contact",
    fields=(
        FormField("name", required=True, min_length=2, max_length=100),
        FormField("email", type="email", required=True),
        FormField("message", type="textarea", required=True, min_length=10),
        FormField("consent", type="consent"),
    ),
)
```

From it the server builds the validation model and the description
`GET /forms/<name>` that the frontend renders with the same client rules;
`POST /forms/<name>` validates and delivers. Texts go to the `forms` section of
`app/core/locales/*.json`: `<form>.title`, `<form>.submit`, `<form>.success`,
`<form>.<field>` and, for select options, `<form>.<field>.<option>`.
Field types: `text`, `textarea`, `email`, `tel`, `password`, `number` (a whole number,
limited with `min_value` / `max_value`), `select` and `multiselect` (with `options`),
`checkbox`, `consent`.

Every form gets a honeypot (a hidden `website` field): a bot that fills it gets the usual
answer and its submission is dropped. Submissions are rate-limited per IP and form, and
with a captcha switched on need a token. With the admin they are stored as leads and
delivered to the enabled channels.

### Leads and delivery channels

A submission is stored as a lead (Admin → Leads: search, filters, status, CSV), the admins
who read leads get a notification, and the lead goes to every channel enabled in Admin →
Settings → Channels: email, Telegram, a webhook (signed with `X-Osnova-Signature: sha256=...`
when a secret is set). With background tasks a channel that fails for a transient reason
is retried (1, 2, 4, 8, 16 minutes); one that refused the message is not. Webhooks and
Telegram reach only public addresses and do not follow redirects, so an admin cannot point
a channel at the app's own services; `WEBHOOK_ALLOW_PRIVATE=true` allows a receiver of
your own in the same network. A new kind of channel is an entity type in
`app/modules/leads/channels.py`.

### Email

```python
await send_mail(render_mail("<name>", to, **params))
```

Texts are in the `mail` section of `app/core/locales/*.json` (`<name>.subject`,
`<name>.body`, `<name>.button`), in the recipient's language. Every message has the text
and an HTML version in one layout (`app/core/mail/layout.html`, `button.html`: site name,
heading, a button for a `link` parameter; colours are edited there). Admin → Settings →
Mail picks the delivery: `console` writes the text to the log, `smtp` sends it (standard
library, no extra packages); the test button sends one to yourself.

`send_mail` never delays a response: it sends in a thread, or with background tasks puts
the message on the queue, where the worker retries while the mail server is down.
Failures are logged, not raised.

### Notifications

```python
await notify(session, users, "<kind>", params, link="/admin/leads")
```

(`app/modules/notifications/service.py`) with texts `notifications.<kind>.title` / `.body`
in the locales; they are translated when read, in the recipient's language. The bell is
always on; email is a second channel chosen in Admin → Settings → Notifications. Another
channel (Telegram...) is a function in `app/modules/notifications/channels.py` and becomes
an option there. Example: new leads in `app/modules/leads/service.py`.

### Settings in the admin

A group of settings the owner changes at runtime is a Pydantic model:

```python
# app/settings.py
class SiteSettings(SettingsGroup):
    group = "site"

    name: str = Field(default=config.APP_NAME, min_length=1, max_length=100)
    contact_email: OptionalEmail = ""
```

listed in `GROUPS` (or in a module's `settings.py` with `GROUPS`, shown only with the
module). Read it typed from memory: `settings.get(SiteSettings).contact_email`. The admin
form is generated from the model, so a new field needs no migration and no frontend code;
its labels go to the `settings` section of `app/core/locales/*.json`
(`<group>.<field>.help` for a hint), and the permission `settings.<group>` is declared on
its own. Values from `.env` are the initial ones (`Field(default_factory=lambda:
config.X)`); a saved group wins. `Secret` fields are stored encrypted and sent as
`********`. Every process reloads changed settings after `SETTINGS_REFRESH_SECONDS`; the
worker before a task. Values that need a restart, secrets of the infrastructure and
capability flags stay in `.env`.

### Configurable entities

Lists of similar records the owner edits in the admin (lead channels; later, say, countries
or payment methods) live in one table `(type, name, enabled, params)`. A new kind is a class,
not a table and a migration:

```python
@entity_type
class TelegramChannel(EntityType):
    type = "lead_telegram"
    group = "lead_channels"

    bot_token: Secret
    chat_id: str = Field(min_length=1, max_length=64)

    def send(self, message: LeadMessage) -> None: ...
```

The admin form is generated like a settings group: labels from
`entities.<type>.<field>`, the title from `entities.<type>.title`. Entities that need
relations or heavy queries should become ordinary tables.

### Files

`POST /files` stores a private upload of the signed-in user, within the limits of Admin →
Settings → Files; only its owner and `files.manage` open it. `FILES_STORAGE=local` keeps
them in `FILES_DIR`, `s3` in any S3-compatible bucket (signed requests without a client
library); a download is then a redirect to a short-lived link. Behind nginx a request is
also limited by `client_max_body_size` (frontend `nginx.conf`): keep it in step with
`FILES_MAX_SIZE_MB`.

### Background tasks and schedule

A task is a function with `@celery_app.task` in `app/modules/tasks/tasks.py`, called with
`.delay(...)`. A scheduled one is an entry in `beat_schedule`
(`app/modules/tasks/celery_app.py`) with the task name and a `crontab` (UTC); `beat` runs as
one instance. The worker and beat log like the web process and load the settings changed
in the admin.

### Nightly cleanup

Every night at 03:30 UTC `maintenance.cleanup` removes read notifications, audit records and
(when set) accounts that never confirmed the email and never signed in, after the days of
Admin → Settings → Data retention (90, 365 and off at first; 0 keeps everything). Without
Celery run `python manage.py cleanup` from cron (`make cleanup` in Docker). Another rule:
`cleanup.py` in the module with `async def cleanup(session) -> int`; it is found by itself.

### CSV export

`csv_response("<name>", header, rows)` (`app/core/csv_export.py`) streams a file a
spreadsheet opens: UTF-8 with a BOM, UTC dates, `;` between columns for languages where
Excel expects it, cells that would run as formulas made text. `rows` is an async iterator;
read it with `session.stream_scalars(...)` in a session of its own. Examples:
`export_users` (`app/modules/admin/users.py`), `export_leads` (`app/modules/leads/routes.py`).

### Captcha

Optional, Cloudflare Turnstile. Set the keys in Admin → Settings → Protection and switch it
on (`CAPTCHA_PROVIDER`, `CAPTCHA_SITE_KEY` and `CAPTCHA_SECRET_KEY` in `.env` give the
initial values; test keys are in `.env.example`). `/bootstrap` then has
`captcha: {provider, site_key}`, and `POST /forms/{name}` and `POST /auth/register` need the
widget's token in the `X-Captcha-Token` header (`400 captcha_failed` otherwise). If
Cloudflare cannot be reached, requests are let through with a warning in the log. Protect
another endpoint with `Depends(require_captcha)`; another provider is a function in
`PROVIDERS` (`app/core/captcha.py`).

### Languages

Backend messages, emails and form texts are translated from
`app/core/locales/<code>.json` (sections of flat strings, `str.format` placeholders). The
request language comes from `Accept-Language`; `translate("errors.not_found")` works
anywhere in a request. A new language: `AVAILABLE_LANGUAGES` in `app/core/languages.py`,
translations in `app/core/locales/` and in the frontend, then enable it in `LANGUAGES` or in
Admin → Settings → Languages.

### Logs

`logger.info("...", extra={"order_id": order.id})` adds fields that become keys with
`LOG_FORMAT=json` (`app/core/logging_config.py`). Every line carries the request id, which
the frontend shows with an error and the response has in `X-Request-ID`.

### Error tracking

Set `SENTRY_DSN` (Sentry or a compatible GlitchTip) and install `requirements/sentry.txt`;
in Docker set `EXTRA_REQUIREMENTS=sentry` in `.env` and rebuild. A DSN without the package
stops the app at start with a message. Unhandled errors of the API and Celery tasks and
`ERROR` log lines become events, tagged with the release `osnova-backend@<version>` and
`SENTRY_ENVIRONMENT`. Nothing personal is sent: no request bodies, cookies, auth headers,
user IPs or local variables, and `INFO` lines are not kept as breadcrumbs.
`SENTRY_TRACES_SAMPLE_RATE=0.1` also traces 10% of requests. The frontend has its own DSN
(`FRONTEND_SENTRY_DSN`).

### Stored secrets

`Secret` fields of entities and settings, and OAuth tokens, are stored encrypted (Fernet, a
key derived from `SECRET_KEY`; `app/modules/auth/encryption.py`). APIs send `********`
instead, and a `********` sent back keeps the stored value. To change `SECRET_KEY`: put the
old value into `OLD_SECRET_KEYS`, set the new one, restart, run
`python manage.py rotate-secrets`, then empty `OLD_SECRET_KEYS`. Without the old key the
secrets are lost (logged, read as empty): enter them again in the admin. Sessions and email
links signed with the old key end anyway.

---

## 9. Docker

Both repositories sit side by side (`osnova_backend/`, `osnova_frontend/`); one `.env` in
the backend configures both.

```bash
make up-minimal            # backend + frontend
make up-standard           # + PostgreSQL, Redis, Celery worker and beat
make up-scalable           # standard with 3 backend replicas
make up-standard HTTPS=1   # + Caddy with Let's Encrypt certificates for SITE_URL
make logs                  # follow logs
make down                  # stop (make down-volumes also deletes the data)
```

Only the frontend is published: `http://localhost:8080` (`FRONTEND_PORT`). nginx proxies
`/api`, `/docs`, `/redoc` and `/openapi.json` to the backend, so there is one origin and no
CORS.

- **Backend image:** `python:3.13-slim`, non-root, `uvicorn`, a health check.
  `REQUIREMENTS=base` for minimal, `standard` with the datastores. Port `8000` is exposed
  only inside the compose network, so replicas do not clash. `EXTRA_REQUIREMENTS` adds
  optional requirements files (`sentry`).
- **Datastores and worker:** `postgres`, `redis`, the Celery `worker` and `beat` (the same
  image) are in `docker-compose.datastores.yml` and run only for `standard` / `scalable`.
  Their addresses are set by compose; `localhost` values from `.env` are ignored, and in
  `minimal` `DATABASE_URL` and `REDIS_URL` are forced empty.
- **Migrations:** `make migrate` runs `alembic upgrade head` once in a one-off container;
  with `RUN_MIGRATIONS=true` the backend runs them on every start (never the worker and
  beat); replicas wait for each other on a PostgreSQL lock.
- **Health and readiness:** `GET /api/v1/health` for the backend; `celery inspect ping` for
  the worker; built-in checks for postgres and redis. `GET /api/v1/ready` answers 503 while
  a dependency is down.
- **HTTPS:** `HTTPS=1` adds `docker-compose.https.yml`: Caddy on ports 80 and 443
  (`HTTP_PORT`, `HTTPS_PORT`) gets and renews a Let's Encrypt certificate for the host of
  `SITE_URL`, sends `/api/*` straight to the backend replicas (with the visitor's address
  in `X-Forwarded-For`, so rate limits count per visitor) and the rest to the frontend,
  which is then not published itself (`deploy/Caddyfile`).

---

## 10. Deployment

One Linux server with Docker Compose: the standard profile behind Caddy.

```
visitor ──https──▶ Caddy :443 ──▶ /api/*  backend (one or more replicas)
                    (:80 → https)  ▶ the rest  frontend nginx (site, security headers)
```

### Server and domain

- A Linux server with 2 GB of memory or more (the frontend build needs it), Docker Engine
  and the Compose plugin ([docs.docker.com/engine/install](https://docs.docker.com/engine/install/)),
  `git` and `make`.
- A DNS `A` record (and `AAAA` for IPv6) of your domain pointing to the server. Let's
  Encrypt checks it, so set it before the first start.
- Open ports 22 (SSH), 80 and 443 (TCP, and UDP 443 for HTTP/3), close the rest:

  ```bash
  sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443 && sudo ufw enable
  ```

  Ports published by Docker bypass `ufw`; the stack publishes only 80 and 443.

### Code and settings

```bash
sudo mkdir -p /srv && sudo chown "$USER" /srv && cd /srv
git clone https://github.com/osnova-kit/osnova_backend.git
git clone https://github.com/osnova-kit/osnova_frontend.git
cd osnova_backend
make init
```

Then in `.env`:

| Variable | Value |
|---|---|
| `DEBUG` | `false` (no `/docs` in production) |
| `SITE_URL` | `https://example.com`: Caddy takes the certificate for this host; links in emails, canonical links and the sitemap use it too |
| `SECRET_KEY` | written by `make init`; keep a copy, stored secrets are encrypted with it |
| `POSTGRES_PASSWORD` | written by `make init`; it is applied when the database is created |
| `AUTH_ENABLED`, `ADMIN_ENABLED`, ... | the capabilities you need |
| `COOKIE_SECURE` | `true` |
| `LOG_FORMAT` | `json` if a log collector reads the logs |
| `MAIL_BACKEND`, `SMTP_*` | your SMTP server (later in Admin → Settings → Mail) |
| `SENTRY_DSN`, `EXTRA_REQUIREMENTS=sentry`, `FRONTEND_SENTRY_DSN` | optional [error tracking](#error-tracking) |

`.env` holds secrets: it is written readable by its owner only; never commit it.

### First start

```bash
make up-standard HTTPS=1     # builds the images, starts everything with Caddy
make migrate                 # creates the tables (or RUN_MIGRATIONS=true from make init)
make createroot              # the first root user
```

Open `https://example.com`. The certificate arrives within a minute of the first start;
`docker logs osnova-caddy-1` shows the progress. Every `make` command that starts or stops
containers (`up-*`, `down`) needs `HTTPS=1` too; `export HTTPS=1` in the shell profile of
the deploy user saves typing it. With several replicas use `make up-scalable HTTPS=1` and
files in S3.

### Updates

```bash
make backup
git pull && git -C ../osnova_frontend pull
make up-standard HTTPS=1     # rebuilds the changed images, restarts them
make migrate
```

Read the CHANGELOG of both repositories first: it lists new settings and changes that need
a step from you. A project made from the template takes new releases of Osnova with
`make upgrade` ([Upgrading](#12-upgrading-and-versions)).

### When something is wrong

- **No certificate:** `docker logs osnova-caddy-1`. The DNS record must point to this
  server and ports 80 and 443 must be reachable; Let's Encrypt limits failed attempts, so
  fix the cause before restarting many times.
- **502 from the API:** the backend is not healthy yet or crashed: `make ps HTTPS=1`,
  `docker logs osnova-backend-1` (a missing setting stops it with a message).
- **`/api/v1/ready` answers 503:** the database or Redis is not reachable.
- **Everyone hits the rate limit together:** something in front of Caddy (a load
  balancer, Cloudflare proxy) hides the visitors' addresses. Add its addresses to
  `trusted_proxies` in `deploy/Caddyfile`.
- **A browser blocks something:** the console names the Content Security Policy
  directive; add the host to `CSP_EXTRA_ORIGINS` and rebuild.

Another reverse proxy instead of Caddy (Traefik, nginx with certbot, a cloud load
balancer) works the same way: terminate HTTPS, send `/api/*` to `backend:8000` with
`X-Forwarded-For` set to the visitor's address (not appended to) and
`X-Forwarded-Proto: https`, the rest to `frontend:80`.

---

## 11. Backups

```bash
make backup                                       # into backups/ (git-ignored)
make restore FILE=backups/osnova-2026-11-12_030000.dump
make restore FILE=backups/osnova-2026-11-12_030000-files.tar.gz
```

`make backup` writes the database of the running stack (`pg_dump`, custom format) to
`backups/osnova-<date>.dump`. With local files (`FILES_STORAGE=local`) or submissions on
disk (`FORMS_DELIVERY=file`) it also writes `osnova-<date>-files.tar.gz`; files in S3 are
backed up by the bucket's own means. `KEEP_DAYS=14` deletes backups older than 14 days.

`make restore` asks first (`CONFIRM=yes` skips the question), stops the backend, worker and
beat, replaces the database (it is recreated, so nothing newer stays behind) or the folders
in the archive, and starts them again. Run `make migrate` after restoring a backup older
than the code.

Every night from cron (`crontab -e` of a user in the `docker` group):

```cron
0 3 * * * cd /srv/osnova_backend && make backup KEEP_DAYS=14 >> backups/backup.log 2>&1
```

Keep a copy off the server too (`rsync` or `rclone` of `backups/` to another host or
bucket), and a copy of `.env`: its `SECRET_KEY` decrypts the stored secrets. Certificates
need no backup, Caddy gets new ones.

---

## 12. Upgrading and versions

A project made from Osnova takes a new release of the template with one command; its own
changes stay:

```bash
make upgrade VERSION=v1.1.0          # backend
npm run upgrade -- v1.1.0            # frontend
```

`.osnova-version` holds the release the project is on (keep it from the template). The
command fetches the new release from the template repository (another address:
`UPSTREAM=...`) and merges it into the current branch: what only the project changed and
what only the template changed come together; a line changed on both sides is a conflict
to resolve by hand. The first upgrade of a project made with "Use this template" records
the release it was made from as the common base (a merge that changes no files).

- Modules removed with `make strip` / `npm run strip` stay removed: changes and new files of
  the template in them are dropped.
- `README.md` and `CHANGELOG.md` stay the project's; a version number changed on both sides
  keeps the project's; in the frontend a conflicting `package-lock.json` is written again.
- Only on a clean git working tree. Without conflicts it commits
  `chore: upgrade Osnova to <version>`; with conflicts it lists the files and stops:
  resolve them, `git add`, `git commit`. It prints the commit to go back to.
- Afterwards: the linters and the tests, and the release notes in the template's
  CHANGELOG, mostly the **Breaking** part. Run `make migrate` for new migrations; one that
  touches the tables of a removed module has to be dropped by hand.

### Versions

Osnova follows [Semantic Versioning](https://semver.org/). Its public surface is what a
project builds on: the `.env` settings, `app/core` (what the modules and the project's code
use), the module registry and `app/forms.py`, the `make` and `npm` commands, the API
answered to the frontend, the frontend's `src/components` and `src/config`, and the
database migrations.

- **Patch** (1.0.x): fixes; upgrading needs nothing else.
- **Minor** (1.x.0): new features; the existing settings and code keep working (a new
  setting has a default, a new migration runs on its own).
- **Major** (x.0.0): may need steps by hand: each one is in the **Breaking** part of the
  CHANGELOG with what to do.
