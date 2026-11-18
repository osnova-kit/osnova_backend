# Contributing

Thanks for helping with Osnova! The project has two repositories:
[osnova_backend](https://github.com/osnova-kit/osnova_backend) (this one) and
[osnova_frontend](https://github.com/osnova-kit/osnova_frontend). How the template is built:
[DOCUMENTATION.md](DOCUMENTATION.md); ideas and bugs go to the issues.

## Setup

```bash
make install          # venv + requirements/dev.txt
cp .env.example .env
make dev              # API on http://localhost:8000, docs at /docs
make dev-all          # API + frontend dev server (../osnova_frontend), Ctrl+C stops both
```

Full stack in Docker (both repositories side by side): `make up-minimal` or `make up-standard`.

## Workflow

1. Create a branch from `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
2. Use [Conventional Commits](https://www.conventionalcommits.org/):
   `feat: add language list to bootstrap`, `fix(files): reject unknown names`.
3. Before pushing: `make lint` and `make test` (`make format` fixes the style; after API
   changes `make openapi` writes `openapi.json`, the tests check it). `make help` lists every
   command.
4. Open a pull request using the template. CI must be green.
5. Note user-visible changes in [CHANGELOG.md](CHANGELOG.md) under *Unreleased*.

## Architecture rules

- **Module = folder.** An optional capability lives in `app/modules/<name>/` and exposes
  `register(app)`. It is registered in `app/core/modules.py` and imported only when enabled.
- The core (`app/core`) never imports a module. A module may import only the modules it
  lists in `requires`.
- A module's dependencies go to `requirements/<name>.txt` and are included in `standard.txt`.
- Dependencies are pinned. Dependabot (`.github/dependabot.yml`) proposes the minor and patch
  updates once a month, one PR per kind (Python packages, Compose images, GitHub Actions);
  major versions, a new Python release, SQLAlchemy 2.1 (fastapi-users does not support it yet)
  and minor releases of ruff are updated by hand.
- Each new setting gets a default in `app/config.py` and an entry in `.env.example`.
- Database schema changes go through Alembic migrations only:
  `alembic revision --autogenerate -m "<message>"`, then review the file
  ([`migrations/README.md`](migrations/README.md)).

## Code style

ruff, line length 100. Names carry the meaning; a docstring only on a class or function whose
name does not tell enough, a comment only for unusual behaviour.

## Tests

`pytest` runs with all modules enabled on an in-memory SQLite database. `tests/test_modules.py` checks in a separate process
that the minimal profile imports none of the optional packages — keep it passing.

## CI

CI (GitHub Actions) runs ruff and the tests (with a real Redis), checks that the
migrations match the models on PostgreSQL, starts the app with base requirements only,
builds the Docker image with base and with standard requirements, and strips a copy for
each flag. It also starts the whole scalable stack with both repositories (3 backend
replicas, files in an S3 bucket from SeaweedFS, `.github/ci/`) and runs
`scripts/check_stack.py` through the frontend: the sign-in works on every replica, a sent
form is stored as a lead and found in the admin, a file uploaded through one replica is
served by the others from the bucket, the sign-in rate limit is shared, and every replica
got requests. The script needs only the standard library, so it checks a deployed stack
too (`python3 scripts/check_stack.py --help`).
