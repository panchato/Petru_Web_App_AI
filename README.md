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
- `app/routes.py`: HTTP routes, request/response, flashes, redirects
- `app/templates/`: Jinja templates
- `app/static/`: styles and static assets

2. Application/service layer
- `app/services/lot_service.py`: lot creation and net-weight compute-on-write
- `app/services/fumigation_service.py`: strict fumigation state transitions
- `app/services/qc_service.py`: QC validations and QC record creation

3. Domain/data layer
- `app/models.py`: SQLAlchemy models and DB constraints
- `migrations/versions/`: Alembic migrations

4. Cross-cutting modules
- `app/permissions.py`: centralized permission checks and decorators
- `app/upload_security.py`: upload allowlists, MIME checks, size limits, optional AV hook
- `app/__init__.py`: app bootstrap, CSRF, request ID, structured logging

## Key Business Rules

- Fumigation state machine is strictly linear:
  - `1` available -> `2` assigned -> `3` started -> `4` completed
- QC validation:
  - size breakdown units must sum to `100`
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
  models.py
  routes.py
  forms.py
  permissions.py
  upload_security.py
  services/
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
