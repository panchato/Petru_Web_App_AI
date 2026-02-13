# Petru_Webapp

Flask web application for walnut raw-material reception, lot management, quality control (QC), and fumigation traceability.

## Tech Stack
- Python + Flask
- Flask-SQLAlchemy (ORM)
- Flask-Login (auth/session)
- Flask-WTF (forms + CSRF)
- Flask-Migrate/Alembic (schema migrations)
- WeasyPrint (PDF generation)
- SQLite by default (`app/instance/database.db`)

## Repository Layout
- `run.py`: local development entrypoint.
- `start.ps1`: one-command Windows launcher using `windows_venv`.
- `setup_db.py`: migration/bootstrap script (roles, areas, admin, sample data).
- `app/__init__.py`: creates Flask app and extensions.
- `app/config.py`: runtime/config values.
- `app/models.py`: SQLAlchemy models and relationships.
- `app/forms.py`: WTForms definitions and dynamic choices.
- `app/routes.py`: all HTTP routes, access control, workflows.
- `app/templates/`: Jinja templates.
- `app/static/`: CSS + uploaded images/PDFs.

## How To Run (Windows)
1. Open PowerShell in project root.
2. Start app:
   - `powershell -ExecutionPolicy Bypass -File .\start.ps1`

Alternative:
- `.\windows_venv\Scripts\python.exe run.py`

App URL: `http://127.0.0.1:5000`

Important: if the PowerShell window is closed, the Flask process stops.

## Database + Bootstrap
Run initial setup or refresh local schema/data:
- `.\windows_venv\Scripts\python.exe setup_db.py`

`setup_db.py` does:
- Initialize/generate/upgrade migrations (if local `migrations/` exists/needed).
- Create tables.
- Ensure base roles:
  - `Admin`
  - `Contribuidor`
  - `Lector`
- Ensure base areas:
  - `Materia Prima`
  - `Calidad`
- Create default admin if missing:
  - Email: `panchato@gmail.com`
  - Password: `dx12bb40`

Security note: change credentials and `SECRET_KEY` for production.

## Configuration
From `app/config.py`:
- DB URL: `DATABASE_URL` env var or local SQLite fallback.
- Secret key: `SECRET_KEY` env var or insecure default (`very_secret_key`).
- Upload paths:
  - `app/static/images`
  - `app/static/pdf`
- Allowed upload extensions: `png`, `jpg`, `jpeg`, `pdf`.

## Core Domain Workflows
### 1) Administration
Admin-only CRUD/toggles for:
- Users, roles, areas
- Clients, growers, varieties
- Raw material packaging definitions

### 2) Raw Material (Materia Prima)
- Create raw material reception.
- Create one or more lots attached to reception.
- Optional close of reception when last lot is flagged.
- Register truck weights and auto-calculate lot net weight.
- Generate lot labels PDF with QR payload.

### 3) Quality (Calidad)
- Create lot QC reports (linked to lots).
- Create sample QC reports (standalone sample entries).
- View reports in HTML and export to PDF.

### 4) Fumigation
- Create fumigation work order and assign lots.
- Start fumigation (optional sign image + work-order PDF).
- Complete fumigation (optional certificate PDF).
- Track lot fumigation state transitions.

## Access Control Model
Implemented in `app/routes.py` decorators:
- `@admin_required`: admin-only screens.
- `@area_role_required(area, roles)`: requires area membership + one of listed roles.
- Admin bypasses area/role restrictions.

Menu behavior maps to:
- `Materia Prima` area routes.
- `Calidad` area routes.
- Role tiers: `Admin`, `Contribuidor`, `Lector`.

## Data Model Summary
Main entities:
- Security/master: `User`, `Role`, `Area`, `Client`, `Grower`, `Variety`, `RawMaterialPackaging`
- Operations: `RawMaterialReception`, `Lot`, `FullTruckWeight`
- QC: `LotQC`, `SampleQC`
- Fumigation: `Fumigation`

Important relationships:
- `User` many-to-many with `Role`, `Area`, `Client`.
- `RawMaterialReception` many-to-many with `Grower` and `Client`; one-to-many with `Lot`.
- `Lot` one-to-one with `FullTruckWeight` and `LotQC`; many-to-one to reception/variety/packaging.
- `Fumigation` many-to-many with `Lot`.

## Business Rules (Important)
- Lot number must be unique.
- Lot `net_weight` formula:
  - `loaded_truck_weight - empty_truck_weight - (packaging_tare * packagings_quantity)`
- QC constraints:
  - `units = lessthan30 + between3032 + between3234 + between3436 + morethan36`
  - `units` must equal `100`.
  - `shelled_weight = extra_light + light + light_amber + amber`
  - `yieldpercentage = (shelled_weight / inshell_weight) * 100`
  - `inshell_weight > 0`
- Fumigation lot states (`Lot.fumigation_status`):
  - `'1'`: available (not assigned)
  - `'2'`: assigned to fumigation
  - `'3'`: fumigation started
  - `'4'`: fumigation completed

## File Upload and PDF Notes
- Uploaded names are sanitized with `secure_filename`.
- Stored relative paths are normalized with forward slashes.
- QC and fumigation PDFs are generated with WeasyPrint.
- QC PDF templates resolve local image paths through file URIs.

Windows note for WeasyPrint runtime dependencies:
- Install GTK/Pango via MSYS2 and add `C:\msys64\mingw64\bin` to `PATH`.

## Known Gaps / Cautions
- `/generate_qr` references endpoint `lot_net_details`, which is not defined; calling it will fail unless route is added.
- Raw material packaging list URL is spelled `/list_raw_material_packagins` (missing `g`), while function/template names use `list_raw_material_packagings`.
- The project currently has no automated test suite.
- `migrations/` is ignored in `.gitignore`, so migration history may be local-only unless policy changes.

## Quick Route Groups
- Auth: `/login`, `/logout`
- Admin/master data: `/add_*`, `/list_*`, `/edit_*`, `/toggle_*`, `/assign_*`
- Raw material: `/create_raw_material_reception`, `/create_lot/<id>`, `/list_rmrs`, `/list_lots`, `/register_full_truck_weight/<id>`, `/lots/<id>/labels.pdf`
- QC: `/create_lot_qc`, `/create_sample_qc`, `/list_lot_qc_reports`, `/list_sample_qc_reports`, report detail and `/pdf`
- Fumigation: `/create_fumigation`, `/list_fumigations`, `/start_fumigation/<id>`, `/complete_fumigation/<id>`

## PR Coordination (Current Split)
To collaborate safely on the current feature split:
- PR #2 (`pr1-fumigation-core`) merges first into `master`.
- PR #3 (`pr2-ui-refresh`) and PR #4 (`pr3-reporting-docs`) are stacked on PR #2.
- After PR #2 is merged, rebase PR #3 and PR #4 onto `master` (or retarget base branch to `master`) before final merge.
- Keep local-only files out of PRs (`app/instance/database.db`, `.claude/`, `PROJECT_NOTES.md`).

## For Future Contributors / AI Agents
When changing behavior, update all of:
- Model fields + migration logic
- Form validators/defaults
- Route access decorators
- Template rendering and field names
- Documentation (`README.md` and `PROJECT_NOTES.md`)
