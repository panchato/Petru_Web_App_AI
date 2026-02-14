# Repository Guidelines

## Project Structure & Module Organization
- `app/` contains the Flask application:
  - `app/__init__.py` app factory and extension setup
  - `app/models.py` SQLAlchemy models
  - `app/forms.py` WTForms definitions
  - `app/routes.py` routes, permissions, and workflows
  - `app/templates/` Jinja templates
  - `app/static/` CSS and uploaded assets
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
- Bootstrap/update local DB:
  - `.\windows_venv\Scripts\python.exe setup_db.py`
- Quick syntax validation for changed Python files:
  - `python -m py_compile app\__init__.py app\config.py app\forms.py app\models.py app\routes.py run.py setup_db.py`

## Coding Style & Naming Conventions
- Python: 4-space indentation, clear function names, minimal side effects in routes.
- Keep business rules in forms/models where possible; keep route handlers readable.
- Templates: use snake_case filenames (e.g., `list_fumigations.html`).
- Routes and helpers should follow existing naming patterns (`create_*`, `list_*`, `edit_*`, `toggle_*`).

## Testing Guidelines
- No formal automated test suite is currently enforced.
- Before opening a PR:
  - run `py_compile` check above
  - manually smoke-test affected flows (auth, admin, raw material, QC, fumigation)
- If adding tests, use `unittest`-compatible naming (`test_*.py`) under a `tests/` folder.

## Commit & Pull Request Guidelines
- Use short, imperative commit messages (examples in history: `Add ...`, `Split X: ...`).
- Prefer small, focused PRs by concern (backend/workflow, UI, reporting/docs).
- PR description should include:
  - summary of changes
  - validation steps run
  - dependency/merge order when stacked
- For the current split workflow: merge core/backend first, then dependent PRs.
- Exclude local-only artifacts from PRs: `.claude/`, `PROJECT_NOTES.md`, `app/instance/database.db`.

## Security & Configuration Tips
- Set `SECRET_KEY` and `DATABASE_URL` via environment variables for non-local use.
- Do not commit credentials, tokens, or production data.
