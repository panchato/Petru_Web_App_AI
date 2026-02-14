# Project Notes

## Current System Snapshot
- Framework: Flask monolith (single app package, no blueprints).
- Entrypoints: `run.py` (dev), `start.ps1` (Windows convenience launcher), `setup_db.py` (schema/bootstrap).
- Default DB: SQLite at `app/instance/database.db` unless `DATABASE_URL` is set.
- Primary modules: `app/models.py`, `app/forms.py`, `app/routes.py`.

## Architecture Map
```text
run.py / start.ps1
  -> app/__init__.py (Flask app + extensions)
     -> app/config.py (runtime config)
     -> app/models.py (entities + relations)
     -> app/forms.py (WTForms + dynamic choices)
     -> app/routes.py (auth, ACL, domain workflows)
        -> app/templates/* (Jinja views)
        -> app/static/* (css + user-uploaded images/pdf)
```

## Auth and Authorization
### Authentication
- Flask-Login session auth.
- Login checks:
  - User exists by email.
  - `user.is_active` is true.
  - Bcrypt password hash matches.
- Redirect hardening present in `is_safe_redirect_url()` for `next` parameter.

### Authorization
- `admin_required`: admin-only sections.
- `area_role_required(area, roles)`: non-admins need BOTH area membership and one permitted role.
- Admin bypasses area/role checks.

## Domain Invariants
### Reception and Lot
- A reception can be marked closed (`is_open=False`) after the "last lot" flag in lot creation.
- Closed reception blocks new lot creation.
- `lot_number` must be unique.

### Net Weight
- Net weight is calculated during full-truck weight registration:
  - `net = loaded - empty - (packaging.tare * packagings_quantity)`
- Registration fails if packaging record is missing.

### QC Rules
- Shared by lot QC and sample QC:
  - `units` must equal 100 (sum of size buckets).
  - `shelled_weight = extra_light + light + light_amber + amber`.
  - `inshell_weight` must be greater than 0.
  - `yieldpercentage = round((shelled_weight / inshell_weight) * 100, 2)`.
- Lot QC marks corresponding lot `has_qc=True`.
- Lot QC form only lists lots with `has_qc=False`.

### Fumigation State Machine
`Lot.fumigation_status` lifecycle:
- `1`: available for assignment
- `2`: assigned to a fumigation
- `3`: fumigation started
- `4`: fumigation completed

Transition enforcement:
- Create fumigation accepts only lots in `1`.
- Start fumigation requires all selected lots in `2`.
- Complete fumigation requires all selected lots in `3`.

## File and PDF Handling
- Uploads use `secure_filename` and timestamp/UUID naming.
- Stored paths are relative to `app/static` and normalized to `/`.
- Image uploads: `app/static/images`.
- PDF uploads: `app/static/pdf`.
- WeasyPrint generates:
  - Lot labels PDF.
  - Lot QC report PDF.
  - Sample QC report PDF.

## Developer Operations
### Start app
- `powershell -ExecutionPolicy Bypass -File .\start.ps1`
- or `.\windows_venv\Scripts\python.exe run.py`

### Initialize/refresh DB
- `.\windows_venv\Scripts\python.exe setup_db.py`

### Seeded base data
- Roles: Admin, Contribuidor, Lector.
- Areas: Materia Prima, Calidad.
- Default admin is created if absent (see `setup_db.py`).

## Known Issues / Technical Debt
- Broken/dead QR helper route:
  - `/generate_qr` builds URL for `lot_net_details`, but that endpoint does not exist.
- URL naming inconsistency:
  - Route path is `/list_raw_material_packagins` (typo), while endpoint/function/template naming uses `list_raw_material_packagings`.
- Security posture:
  - Default `SECRET_KEY` is hardcoded fallback.
  - Default admin credentials are stored in repo script.
- Migrations strategy ambiguity:
  - `migrations/` is in `.gitignore`, so migration history may differ per machine.

## Conventions to Preserve
- Keep Spanish-facing UI labels/messages consistent with current templates.
- Keep date form format `%Y-%m-%d` and time `%H:%M` for HTML native controls.
- Preserve path normalization (`replace('\\', '/')`) when saving file paths.
- If changing QC calculations, update both route logic and report templates.

## Recommended Change Checklist
Before merging significant changes:
1. Confirm access decorator coverage for new routes.
2. Confirm model/form/template fields stay aligned.
3. Validate lot/QC/fumigation invariants still hold.
4. Validate upload and PDF paths on Windows runtime.
5. Update `README.md` and this file for any flow or rule changes.
