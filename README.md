# Petru Webapp

Web application for walnut operations: raw-material reception, lot traceability, quality control (QC), and fumigation tracking.

## What This App Covers
- Master data: users, roles, areas, clients, growers, varieties, raw material packaging.
- Raw material flow: reception -> lots -> truck-weight registration -> lot labels PDF.
- QC flow: lot QC and sample QC (HTML report + PDF export).
- Fumigation flow: create -> start -> complete with document attachments.

## Tech Stack
- Python + Flask
- Flask-SQLAlchemy, Flask-Login, Flask-WTF
- WeasyPrint for PDF generation
- SQLite by default (`app/instance/database.db`)

## Quick Start (Windows)
1. Open PowerShell in project root.
2. Run:
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```
Alternative:
```powershell
.\windows_venv\Scripts\python.exe run.py
```
3. Open `http://127.0.0.1:5000`.

## Database Bootstrap
Initialize or refresh local schema/data:
```powershell
.\windows_venv\Scripts\python.exe setup_db.py
```
This ensures base roles (`Admin`, `Contribuidor`, `Lector`), base areas (`Materia Prima`, `Calidad`), and default admin if missing.

Dev default admin:
- Email: `panchato@gmail.com`
- Password: `dx12bb40`

## Environment Configuration
- `DATABASE_URL`: optional DB override (otherwise local SQLite).
- `SECRET_KEY`: required for secure non-local deployments.

## Important Business Rules
- `lot_number` must be unique.
- Net weight:
  - `loaded_truck_weight - empty_truck_weight - (packaging_tare * packagings_quantity)`
- QC validation:
  - units buckets must sum to `100`
  - `shelled_weight = extra_light + light + light_amber + amber`
  - `inshell_weight > 0`
- Fumigation status progression:
  - `1` available -> `2` assigned -> `3` started -> `4` completed

## Repository Layout
- `run.py`: dev entrypoint
- `start.ps1`: Windows launcher
- `setup_db.py`: DB/bootstrap script
- `app/`
  - `config.py`, `models.py`, `forms.py`, `routes.py`
  - `templates/` Jinja views
  - `static/` CSS and uploaded files (`images/`, `pdf/`)

## Contributor Workflow
1. Create/switch to a feature branch.
2. Make focused changes.
3. Run quick validation:
```powershell
python -m py_compile app\__init__.py app\config.py app\forms.py app\models.py app\routes.py run.py setup_db.py
```
4. Update docs when behavior changes (`README.md`, `AGENTS.md`).
5. Commit and open a PR with summary + validation steps.

Do not commit local-only files:
- `app/instance/database.db`
- `.claude/`
- `PROJECT_NOTES.md`
- `app.log`

## Known Issues
- `/generate_qr` references missing endpoint `lot_net_details`.
- Route typo exists at `/list_raw_material_packagins`.
