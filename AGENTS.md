# Repository Guidelines

## Build, Test, and Development Commands
- Start app (recommended, Windows):
  - `powershell -ExecutionPolicy Bypass -File .\start.ps1`
- Start app (direct):
  - `.\windows_venv\Scripts\python.exe run.py`
- App URL: `http://127.0.0.1:5000`
- Bootstrap/update local DB:
  - `.\windows_venv\Scripts\python.exe setup_db.py`

## Coding Style & Naming Conventions
- Python: 4-space indentation, clear function names, minimal side effects in routes.
- Keep business rules in forms/models where possible; keep route handlers readable.
- Templates: use snake_case filenames (e.g., `list_fumigations.html`).
- Routes and helpers should follow existing naming patterns (`create_*`, `list_*`, `edit_*`, `toggle_*`).
- UI is in Spanish; keep headings and buttons consistent.
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
- QC invariants (lot and sample):
  - `units = lessthan30 + between3032 + between3234 + between3436 + morethan36` and must equal `100`
  - `shelled_weight = extra_light + light + light_amber + amber`
  - `inshell_weight > 0`
  - `yieldpercentage = round((shelled_weight / inshell_weight) * 100, 2)`
- Fumigation state machine (`Lot.fumigation_status`):
  - `1` available -> `2` assigned -> `3` started -> `4` completed
  - Fumigation state machine lives in `app/services/fumigation_service.py`. Use `can_transition(lot, new_state)` for prechecks in routes, and `transition_fumigation_status(lot, new_state)` for the actual transition inside service methods. To add or change valid transitions, update `VALID_TRANSITIONS` only.

## Route Map
- Auth: `/login`, `/logout`
- Admin CRUD: `/add_*`, `/list_*`, `/edit_*`, `/toggle_*`, `/assign_*`
- Raw material: `/create_raw_material_reception`, `/create_lot/<id>`, `/list_rmrs`, `/list_lots`, `/register_full_truck_weight/<id>`, `/lots/<id>/labels.pdf`
- QC: `/create_lot_qc`, `/create_sample_qc`, `/list_lot_qc_reports`, `/list_sample_qc_reports`, detail pages + `/pdf`
- Fumigation: `/create_fumigation`, `/list_fumigations`, `/start_fumigation/<id>`, `/complete_fumigation/<id>`

## Change Checklist
- Keep model/form/template/route fields aligned for every behavior change.
- For data model changes, update migration strategy/docs accordingly.
- For upload/PDF changes, verify paths and rendering on Windows.
- Update docs in `AGENTS.md` when business rules or flows change.

## Commit & Pull Request Guidelines
- Use short, imperative commit messages (examples in history: `Add ...`, `Split X: ...`).
- Prefer small, focused PRs by concern (backend/workflow, UI, reporting/docs).
- PR description should include:
  - summary of changes
  - validation steps run
  - dependency/merge order when stacked

## Branch Strategy (Concrete)
- Do not create new branches. Use only origin master branch.

## Security & Configuration Tips
- Set `SECRET_KEY` and `DATABASE_URL` via environment variables for non-local use.
- For dashboard cache scaling beyond one Gunicorn worker, set `CACHE_TYPE=RedisCache` and `CACHE_REDIS_URL` in environment variables.
- Do not commit credentials, tokens, or production data.

