# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flask web application for walnut raw-material reception, lot management, quality control (QC), and fumigation traceability. Uses SQLAlchemy 2.0, SQLite, Bootstrap 5, jQuery, and WeasyPrint for PDF generation.

## Development Commands

### Start the application
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```
Or directly:
```powershell
.\windows_venv\Scripts\python.exe run.py
```
App runs at `http://127.0.0.1:5000`

### Initialize/refresh database
```powershell
.\windows_venv\Scripts\python.exe setup_db.py
```
This creates tables, ensures base roles (Admin, Contribuidor, Lector) and areas (Materia Prima, Calidad), and creates default admin if missing.

### Default admin credentials (development only)
- Email: `panchato@gmail.com`
- Password: `dx12bb40`

## Architecture

### Application structure
```
run.py                      # Development entrypoint
start.ps1                   # Windows launcher
setup_db.py                 # Database migration/bootstrap
app/
  __init__.py               # Flask app + extensions (db, bcrypt, login_manager, migrate)
  config.py                 # Runtime config (DB URL, upload paths, secret key)
  basemodel.py              # Base model with id, created_at, updated_at
  models.py                 # SQLAlchemy models and relationships
  forms.py                  # WTForms with dynamic choices
  routes.py                 # All HTTP routes, access control, business logic
  templates/                # Jinja2 templates
  static/                   # CSS, uploaded images/, pdf/
  instance/database.db      # SQLite database (gitignored)
```

### Access control pattern
Two decorators in `app/routes.py`:
- `@admin_required`: Admin-only routes
- `@area_role_required(area_name, roles)`: Requires area membership + one of specified roles (Admin bypasses)
- `@dashboard_required`: Admin or Dashboard role

Example:
```python
@area_role_required('Materia Prima', ['Admin', 'Contribuidor'])
def create_lot(reception_id):
    # Only users in Materia Prima area with Admin or Contribuidor role
```

### SQLAlchemy 2.0 patterns
ALWAYS use:
```python
from sqlalchemy import text

with db.engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM lots WHERE id = :id"), {"id": lot_id})
```

NEVER use deprecated `db.engine.execute()`.

### Form pattern with dynamic choices
Forms in `app/forms.py` populate SelectField choices in `__init__`:
```python
def __init__(self, *args, **kwargs):
    super(MyForm, self).__init__(*args, **kwargs)
    self.variety_id.choices = [(v.id, v.name) for v in Variety.query.filter_by(is_active=True).all()]
```

### File upload pattern
Images: `app/static/images/` (config: `UPLOAD_PATH_IMAGE`)
PDFs: `app/static/pdf/` (config: `UPLOAD_PATH_PDF`)

Naming convention: `{uuid}_{timestamp}_{secure_filename}`

**CRITICAL Windows path issue**: Always normalize stored paths:
```python
relative_path = os.path.join('images', filename).replace('\\', '/')
```

When making uploads optional, ensure save/commit/redirect logic is NOT nested inside file-exists check.

## Domain Workflows

### 1. Raw Material Reception → Lot → Weight Registration
- Create reception (multi-select growers/clients)
- Create lots attached to reception
- Optional: mark "last lot" to close reception (`is_open=False`)
- Register full truck weights to calculate net weight
- Generate lot labels PDF with QR code

### 2. Quality Control (QC)
- Create lot QC (linked to specific lot, marks `lot.has_qc=True`)
- Create sample QC (standalone)
- View reports in HTML, export to PDF via WeasyPrint

### 3. Fumigation Workflow
State machine (`Lot.fumigation_status`):
- `'1'`: Available (not fumigated)
- `'2'`: Assigned to fumigation
- `'3'`: Fumigation started
- `'4'`: Fumigation completed

Actions:
- Create fumigation: assigns lots (only accepts lots in status `'1'`)
- Start fumigation: transitions to `'3'` (requires all lots in `'2'`)
- Complete fumigation: transitions to `'4'` (requires all lots in `'3'`)

## Critical Business Rules

### Lot weight calculation
```python
net_weight = loaded_truck_weight - empty_truck_weight - (packaging_tare * packagings_quantity)
```
Registration fails if packaging record is missing.

### QC validation rules (LotQC and SampleQC)
Both share QCMixin fields and must satisfy:
1. `units = lessthan30 + between3032 + between3234 + between3436 + morethan36` must equal `100`
2. `shelled_weight = extra_light + light + light_amber + amber`
3. `inshell_weight > 0`
4. `yieldpercentage = round((shelled_weight / inshell_weight) * 100, 2)`

Forms validate these server-side in route handlers.

### Unique constraints
- `lot_number` must be unique
- `variety.name` must be unique

## Data Model Relationships

### Many-to-many
- `User` ↔ `Role` (via `role_user`)
- `User` ↔ `Area` (via `area_user`)
- `User` ↔ `Client` (via `client_user`)
- `RawMaterialReception` ↔ `Grower` (via `reception_grower`)
- `RawMaterialReception` ↔ `Client` (via `reception_client`)
- `Fumigation` ↔ `Lot` (via `fumigation_lot`)

### One-to-many
- `RawMaterialReception` → `Lot[]`
- `Variety` → `Lot[]`
- `RawMaterialPackaging` → `Lot[]`

### One-to-one
- `Lot` → `FullTruckWeight` (optional)
- `Lot` → `LotQC` (optional)

## Known Issues / Technical Debt

### Dead route reference
`/generate_qr` builds URL for `lot_net_details` endpoint, which does not exist. Calling it will fail.

### URL typo
Route path is `/list_raw_material_packagins` (missing `g`), while function/template use `list_raw_material_packagings`.

### No test suite
Project has no automated tests. Manual testing required.

### Migrations
`migrations/` is gitignored, so migration history is local-only unless policy changes.

## Important Conventions

### UI language
Keep Spanish labels/messages consistent with existing templates.

### Date/time formats
- Date inputs: `%Y-%m-%d` (HTML native)
- Time inputs: `%H:%M` (HTML native)

### Path normalization
Always use `.replace('\\', '/')` when storing file paths (Windows compatibility).

### CSRF handling
App does NOT use global `CSRFProtect`. Pass `FlaskForm()` as `csrf_form` to templates when CSRF token needed outside form contexts.

### Template/form/model alignment
When changing model fields, update ALL of:
- Model field definitions + migrations
- Form validators/defaults
- Route logic
- Template field names
- Documentation (README.md, PROJECT_NOTES.md)

## WeasyPrint PDF Generation

PDFs generated for:
- Lot labels (with QR codes)
- Lot QC reports
- Sample QC reports

**Windows runtime dependency**: WeasyPrint requires GTK/Pango. Install via MSYS2 and add `C:\msys64\mingw64\bin` to PATH.

PDF templates use file URI scheme for local images:
```python
logo_uri = Path(os.path.join(basedir, 'static', 'logo.png')).as_uri()
```

## Route Organization

### Auth
`/login`, `/logout`

### Admin (master data CRUD)
`/add_*`, `/list_*`, `/edit_*`, `/toggle_*`, `/assign_*`

### Raw Material (Materia Prima area)
`/create_raw_material_reception`, `/create_lot/<id>`, `/list_rmrs`, `/list_lots`, `/register_full_truck_weight/<id>`, `/lots/<id>/labels.pdf`

### Quality Control (Calidad area)
`/create_lot_qc`, `/create_sample_qc`, `/list_lot_qc_reports`, `/list_sample_qc_reports`, `/lot_qc/<id>`, `/sample_qc/<id>`, PDF exports

### Fumigation
`/create_fumigation`, `/list_fumigations`, `/start_fumigation/<id>`, `/complete_fumigation/<id>`

## When Making Changes

Before merging significant changes:
1. Confirm access decorator coverage for new routes
2. Validate model/form/template fields stay aligned
3. Test lot/QC/fumigation state transitions
4. Verify file upload paths work on Windows
5. Update README.md and PROJECT_NOTES.md
