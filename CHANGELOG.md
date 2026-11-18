# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-11-18

The first public release.

### Added
- Three profiles on one codebase: `minimal`, `standard` and `scalable`.
- Modules switched on by flags, and `make strip` to remove the unused ones.
- Accounts: sign-up with email confirmation, password reset, Google, sessions in a JWT cookie
  or Redis, a profile API.
- Admin API: users, named permissions, roles and groups, an audit log, leads with CSV export,
  delivery channels and typed settings with encrypted secrets.
- Forms described once on the backend, stored as leads and sent to email, Telegram or a webhook.
- Files on disk or in S3, notifications, background tasks with Celery, translated emails.
- Docker Compose, HTTPS with Caddy, JSON logs, readiness checks, backups, optional Sentry and
  rate limits shared by replicas.
- `make upgrade` to take new releases of the template.

[Unreleased]: https://github.com/osnova-kit/osnova_backend/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/osnova-kit/osnova_backend/releases/tag/v1.0.0
