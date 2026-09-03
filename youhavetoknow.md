# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Sentinel** is a Django 5.2 LTS audit-recommendation tracking platform for BICEC (Banque Internationale du Cameroun). It implements RBAC with department-scoped visibility, FSM-based recommendation workflows, soft deletes, and append-only audit logging. All Django code lives under `code/`.

## Common Commands

All commands run from the `code/` directory unless noted otherwise.

```bash
# Start full stack (PostgreSQL + Django + worker + nginx)
docker-compose up --build

# Run Django dev server (requires a local .env based on .env.example)
python manage.py runserver

# Run all tests
python manage.py test --verbosity=2

# Run tests for a single app
python manage.py test apps.users
python manage.py test apps.workflow

# Run a single test
python manage.py test apps.users.tests.test_views.SomeTestClass.test_method

# Lint (CI uses Ruff)
ruff check .
ruff format .

# Apply migrations
python manage.py migrate

# Check for migration issues (run before committing)
python manage.py migrate --check

# Collect static files
python manage.py collectstatic --noinput
```

## Environment Setup

Copy `code/.env.example` to `code/.env`. Required variables:
- `SECRET_KEY` — Django secret key
- `HMAC_SECRET_KEY` — separate key used for seal/HMAC operations (ADR-07, must not rotate with SECRET_KEY)
- `DATABASE_URL` or individual `POSTGRES_*` vars
- `DJANGO_SETTINGS_MODULE` — defaults to `config.settings.dev`

## Architecture

### Django Settings Split

`code/config/settings/` has `base.py`, `dev.py`, `prod.py`. Production adds HSTS, SECURE_PROXY_SSL_HEADER, and strict cookie flags.

### Apps (`code/apps/`)

| App | Responsibility |
|-----|---------------|
| `users` | Custom User model (UUID PK), 6 roles, Department hierarchy, shell-account concept |
| `workflow` | Recommendation lifecycle via FSM (DRAFT → CLOSED_RESOLVED), Deliverable, soft-delete manager |
| `audit` | Append-only AuditLog (12-month retention); generic FK stub — full impl in Epic 5 |
| `notifications` | Stub — reserved for future Epic |
| `dashboards` | Stub — reserved for future Epic 6 |

### URL Layout

```
/          → home (login-gated)
/auth/     → users app (login, logout, shell-pending, lockout, habilitation, IT admin)
/audit/    → workflow app (recommendations CRUD + HTMX partials)
```

### RBAC & User Model

Six roles: `AUDIT`, `DM` (Directeur de Mission), `ETP` (Entité), `DG` (Direction Générale), `EXT` (external auditor), `ADMIN_IT`. A freshly created account has no role ("shell account") until an Audit Admin assigns one — enforced by `RoleRequiredMiddleware`.

Key model flags on `User`: `is_external`, `is_audit_admin`. Department FK provides hierarchical visibility scoping.

### Middleware Order (critical)

`AxesMiddleware` must come after `AuthenticationMiddleware`. `IdleTimeoutMiddleware` (30-min session kill), `RoleRequiredMiddleware` (shell-account gate), and `ExternalIsolationMiddleware` (mission-scoped EXT users) all run after Axes.

### FSM Workflow

`Recommendation` uses `django-fsm-2`. States: `DRAFT → ASSIGNED → IN_PROGRESS → PENDING_DM_REVIEW → PENDING_AUDIT_REVIEW → CLOSED_RESOLVED`. Transitions are guarded by role checks. Always use the service layer (`apps/workflow/services.py`) for mutations — never call FSM transitions directly from views.

### Service / Selector Pattern (HackSoft convention)

- **Selectors** (`selectors.py`) — read-only, RBAC-aware querysets. Use `get_recommendations_for_user(user)` rather than querying the model directly.
- **Services** (`services.py`) — write operations, wrapped in `transaction.atomic()`, emit `AuditLog` entries.
- Views are thin: they call selectors for reads and services for writes.

### Soft Delete

`Recommendation` has `is_deleted` flag. The default manager `ActiveRecommendationManager` filters these out. Use `Recommendation.all_objects.filter(...)` when you need deleted records.

### Frontend

Server-side Django templates with HTMX for dynamic updates (list filtering, inline deletes, form submissions) and Alpine.js for UI state (sidebars, toasts). Tailwind CSS — compiled output is committed at `code/static/output.css`; do not edit it directly.

Templates are organized under `code/templates/`:
- `layouts/` — base shells
- `components/` — reusable snippets (kpi_card, status_badge, alert, form)
- `partials/` — role-specific sidebars, topbar, footer
- Per-app directories (`workflow/`, `habilitation/`, `external/`, `auth/`, `admin_it/`)

HTMX partials live in `<app>/partials/` subdirectories and are rendered via dedicated URL endpoints.

### Async Tasks

`django-q2` with a single worker polling every 10 s. The `worker` Docker service runs it. Configuration lives in `Q_CLUSTER` in `base.py`.

### Security Constraints

- **Brute force**: django-axes, 5 failures → 1-hour lockout. Do not disable in tests without resetting axes state.
- **Session**: 30-min idle timeout, `SESSION_COOKIE_HTTPONLY=True`, `CSRF_COOKIE_HTTPONLY=False` (required for HTMX CSRF header).
- **Audit log**: Every create/update/delete/transition must produce an `AuditLog` entry. The log is append-only — never update or delete `AuditLog` rows.
- **HMAC_SECRET_KEY**: Used for document seal verification. Kept separate from `SECRET_KEY` so Django key rotation doesn't invalidate existing seals.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every PR to `main`/`develop`:
1. Spins up PostgreSQL 16 Alpine service
2. Installs `requirements/dev.txt`
3. Runs `python manage.py migrate --check` then `python manage.py test --verbosity=2`
4. Runs `ruff check .`

A `qodo-review.yml` workflow runs AI code review on PR open/update (requires `QODO_API_KEY` secret in repo settings).

## Git Conventions

Branch naming: `feat/story-<id>-<slug>`, `fix/<slug>`, `chore/<slug>`. Conventional Commits are required: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`. PRs must target `develop`; only `develop` → `main` merges are direct.
