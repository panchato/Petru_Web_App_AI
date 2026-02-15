# Repository Guidelines

## Project Structure & Module Organization
- `app/` contains the Flask application:
  - `app/__init__.py` app factory and extension setup
  - `app/basemodel.py` base model with common fields
  - `app/models.py` SQLAlchemy models
  - `app/forms.py` WTForms definitions
  - `app/routes.py` routes, permissions, and workflows
  - `app/templates/` Jinja templates
  - `app/static/` CSS and uploaded assets
  - `app/static/css/main.css` shared UI stylesheet (brand, spacing, components)
- Entry points and setup:
  - `run.py` local app runner
  - `setup_db.py` schema/bootstrap helper
  - `start.ps1` Windows startup script
- Local SQLite DB is at `app/instance/database.db` (do not commit local state changes).

## Build, Test, and Development Commands
- Start app (recommended, Windows):
  - `powershell -ExecutionPolicy Bypass -File .\start.ps1`
- Start app (direct):
  - `.\windows_venv\Scripts\python.exe run.py`
- App URL: `http://127.0.0.1:5000`
- Bootstrap/update local DB:
  - `.\windows_venv\Scripts\python.exe setup_db.py`
- Quick syntax validation for changed Python files:
  - `python -m py_compile app\__init__.py app\config.py app\forms.py app\models.py app\routes.py run.py setup_db.py`
- Default admin (dev only): `panchato@gmail.com` / `dx12bb40`
- Session-start git checks:
  - `git fetch --all --prune`
  - `git status --short --branch`
  - `git branch -vv`
  - `gh pr list --state open`

## Coding Style & Naming Conventions
- Python: 4-space indentation, clear function names, minimal side effects in routes.
- Keep business rules in forms/models where possible; keep route handlers readable.
- Templates: use snake_case filenames (e.g., `list_fumigations.html`).
- Routes and helpers should follow existing naming patterns (`create_*`, `list_*`, `edit_*`, `toggle_*`).
- UI copy is in Spanish; keep headings and buttons consistent.
- Prefer shared UI patterns over one-off markup:
  - Page headers: `.page-header` with `.page-actions`
  - Forms grouped in `.form-section`
  - Empty tables use `.empty-state`
  - Statuses use `.status-badge` classes
  - Filters use `.filters` layout

## Architecture & Conventions
- Access control decorators in `app/routes.py`:
  - `@admin_required`, `@area_role_required(area, roles)`, `@dashboard_required` (Admin bypass).
- SQLAlchemy 2.0: use `db.engine.connect()` + `text(...)`, avoid deprecated `db.engine.execute()`.
- Forms with dynamic choices should populate `SelectField` options in `__init__`.
- File uploads: store under `app/static/images/` or `app/static/pdf/` and normalize paths with `.replace('\\', '/')`.
- Upload naming convention: `{uuid}_{timestamp}_{secure_filename}`.
- CSRF: no global `CSRFProtect`; pass `csrf_form` to templates when needed outside forms.
- WeasyPrint on Windows requires GTK/Pango (MSYS2) and `C:\msys64\mingw64\bin` in `PATH`.

## Domain Rules
- Lot net weight formula:
  - `loaded_truck_weight - empty_truck_weight - (packaging_tare * packagings_quantity)`
- `lot_number` and `variety.name` must remain unique.
- QC invariants (lot and sample):
  - `units = lessthan30 + between3032 + between3234 + between3436 + morethan36` and must equal `100`
  - `shelled_weight = extra_light + light + light_amber + amber`
  - `inshell_weight > 0`
  - `yieldpercentage = round((shelled_weight / inshell_weight) * 100, 2)`
- Fumigation state machine (`Lot.fumigation_status`):
  - `1` available -> `2` assigned -> `3` started -> `4` completed
  - Enforce valid transitions in routes.

## Route Map
- Auth: `/login`, `/logout`
- Admin CRUD: `/add_*`, `/list_*`, `/edit_*`, `/toggle_*`, `/assign_*`
- Raw material: `/create_raw_material_reception`, `/create_lot/<id>`, `/list_rmrs`, `/list_lots`, `/register_full_truck_weight/<id>`, `/lots/<id>/labels.pdf`
- QC: `/create_lot_qc`, `/create_sample_qc`, `/list_lot_qc_reports`, `/list_sample_qc_reports`, detail pages + `/pdf`
- Fumigation: `/create_fumigation`, `/list_fumigations`, `/start_fumigation/<id>`, `/complete_fumigation/<id>`

## Testing Guidelines
- No formal automated test suite is currently enforced.
- Before opening a PR:
  - run `py_compile` check above
  - manually smoke-test affected flows (auth, admin, raw material, QC, fumigation)
- Validate QC totals and fumigation state transitions in the UI.
- If adding tests, use `unittest`-compatible naming (`test_*.py`) under a `tests/` folder.

## Change Checklist
- Keep model/form/template/route fields aligned for every behavior change.
- For data model changes, update migration strategy/docs accordingly.
- For upload/PDF changes, verify paths and rendering on Windows.
- Update docs (`README.md`, `AGENTS.md`, and if needed `PROJECT_NOTES.md`) when business rules or flows change.

## Commit & Pull Request Guidelines
- Use short, imperative commit messages (examples in history: `Add ...`, `Split X: ...`).
- Prefer small, focused PRs by concern (backend/workflow, UI, reporting/docs).
- PR description should include:
  - summary of changes
  - validation steps run
  - dependency/merge order when stacked
- For the current split workflow: merge core/backend first, then dependent PRs.
- Exclude local-only artifacts from PRs: `.claude/`, `PROJECT_NOTES.md`, `app/instance/database.db`, `app.log`.

## Security & Configuration Tips
- Set `SECRET_KEY` and `DATABASE_URL` via environment variables for non-local use.
- Do not commit credentials, tokens, or production data.

## Known Issues
- `/generate_qr` references `lot_net_details`, which does not exist.
- Route path typo: `/list_raw_material_packagins` (missing `g`).
