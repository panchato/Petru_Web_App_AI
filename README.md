# Petru Web App

Intranet web application for raw material reception, lot tracking, QC reporting, and fumigation workflow operations.

Built with Flask + SQLAlchemy, with a service-oriented application layer for business rules, and a UI focused on operational visibility.

## What This App Covers

- User, role, and area administration
- Raw material receptions and lot creation
- Lot and sample QC registration with validation rules
- Fumigation lifecycle management (assign -> start -> complete)
- Operational dashboards (`/` and `/dashboard/tv`)
- PDF generation for labels and reports
- Secure upload handling (private files + server-side validation)

## Layered Architecture

The current codebase follows a practical layered shape:

1. Presentation layer
- `app/blueprints/auth/routes.py`: auth routes
- `app/blueprints/admin/routes.py`: admin CRUD routes
- `app/blueprints/materiaprima/routes.py`: receptions and lots routes
- `app/blueprints/qc/routes.py`: QC routes
- `app/blueprints/fumigation/routes.py`: fumigation routes
- `app/blueprints/dashboard/routes.py`: dashboard and health routes
- `app/templates/`: Jinja templates
- `app/static/`: styles and static assets

2. Application/service layer
- `app/services/lot_service.py`: lot creation and net-weight compute-on-write
- `app/services/fumigation_service.py`: strict fumigation state transitions and state machine (`VALID_TRANSITIONS`)
- `app/services/qc_service.py`: QC validations and QC record creation
- `app/services/pdf_cache_service.py`: disk-backed PDF cache helpers

3. Domain/data layer
- `app/models.py`: SQLAlchemy models and DB constraints
- `migrations/versions/`: Alembic migrations

4. Cross-cutting modules
- `app/permissions.py`: centralized permission checks and decorators
- `app/upload_security.py`: upload allowlists, MIME checks, size limits, optional AV hook
- `app/__init__.py`: app bootstrap, CSRF, request ID, structured logging
- `app/http_helpers.py`: shared HTTP and pagination/upload helpers
- `app/blueprints/dashboard/services.py`: dashboard aggregation logic

## Key Business Rules

- Fumigation state machine is strictly linear:
  - `1` available -> `2` assigned -> `3` started -> `4` completed
- QC validation:
  - size breakdown units must sum to `100`
  - fumigation transitions are defined in `VALID_TRANSITIONS` (`app/services/fumigation_service.py`) and enforced via `can_transition()` and `transition_fumigation_status()`
  - `inshell_weight > 0`
  - yield is computed from business formula
- Lot net weight is compute-on-write from truck weights and packaging tare
- Multi-entity updates (fumigation + lots, QC + lot flags) run transactionally

## Tech Stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Migrate (Alembic)
- Flask-Login / Flask-WTF
- WeasyPrint (PDF rendering)
- SQLite by default (configurable via `DATABASE_URL`)

Dependencies are listed in `requirements.txt`.

## Project Structure

```text
app/
  __init__.py
  config.py
  http_helpers.py
  models.py
  forms.py
  permissions.py
  upload_security.py
  blueprints/
    auth/
      __init__.py
      routes.py
    admin/
      __init__.py
      routes.py
    materiaprima/
      __init__.py
      routes.py
    qc/
      __init__.py
      routes.py
    fumigation/
      __init__.py
      routes.py
    dashboard/
      __init__.py
      routes.py
      services.py
  services/
    fumigation_service.py  # state machine (VALID_TRANSITIONS)
    pdf_cache_service.py
  templates/
  static/
migrations/
tests/
run.py
start.ps1
setup_db.py
run_tests.ps1
```

## Local Setup (Windows)

1. Install dependencies in your environment (or use existing `windows_venv`).
2. Bootstrap database:

```powershell
.\windows_venv\Scripts\python.exe setup_db.py
```

3. Start app:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Or:

```powershell
.\windows_venv\Scripts\python.exe run.py
```

App URL:

```text
http://127.0.0.1:5000
```

## Default Bootstrap User

`setup_db.py` seeds a default admin user.

- Email: `panchato@gmail.com`
- Password: `dx12bb40`

Important: change this immediately in non-local environments.

## Environment Variables

- `SECRET_KEY`: default `very_secret_key`
- `DATABASE_URL`: default local SQLite under app data (`sqlite:///<...>/database.db`)
- `CACHE_TYPE`: default `SimpleCache`
- `CACHE_TIMEOUT_DASHBOARD`: default `60` (seconds)
- `PDF_CACHE_DIR`: default `app/static/pdf_cache/` (resolved to absolute path)

## Database and Migrations

Apply migrations:

```powershell
.\windows_venv\Scripts\python.exe -m flask db upgrade
```

Create/update bootstrap data and indexes:

```powershell
.\windows_venv\Scripts\python.exe setup_db.py
```

## Health Endpoint

Lightweight health check:

```text
GET /healthz
```

Returns JSON with application and database status.

## Testing (Isolated by Design)

All test modules pin a dedicated `DATABASE_URL` before importing `app`.
Use the runner script:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_tests.ps1
```

This script exports test env vars and runs `unittest` in an isolated context.

To run a specific test module:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_tests.ps1 tests.test_fumigation_service -v
```

## Security Notes

- CSRF protection is enabled globally.
- Session cookies are hardened by environment (`HttpOnly`, `Secure`, `SameSite`).
- Upload handling uses:
  - extension and MIME allowlists
  - max file-size controls
  - randomized filenames
  - private file serving through authenticated routes
  - optional antivirus hook (ClamAV command)
- Generated PDFs are cached in `PDF_CACHE_DIR` (default `app/static/pdf_cache/`) and served only through authenticated routes.

## Logging and Observability

- Consistent timestamped logs with level
- Request ID is attached to each request and returned as `X-Request-ID`
- Useful for tracing errors across routes and logs

## Operational Notes

- Main operator dashboard: `index.html` (`/`)
- TV dashboard: `/dashboard/tv`
- Dashboard APIs:
  - `/api/index/summary`
  - `/api/dashboard/summary`

## PDF/Rendering Note

WeasyPrint on Windows may require GTK/Pango runtime (`C:\msys64\mingw64\bin` in `PATH`).

## Repository Conventions

Detailed project conventions and workflow notes are in `AGENTS.md`.
