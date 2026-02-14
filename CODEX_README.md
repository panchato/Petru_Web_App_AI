# Codex Session Log

Purpose: keep a persistent, timestamped handoff across sessions for major improvements, startup checks, and pending tasks.

Last updated: 2026-02-14 10:29:44 -03:00

## Next Session Startup Checklist
- [ ] `git fetch --all --prune`
- [ ] `git status --short --branch`
- [ ] `git branch -vv`
- [ ] `gh pr list --state open`
- [ ] Confirm which branch to continue on before editing.

## Major Improvements Log

### 2026-02-14 10:29:44 -03:00
- Split monolithic work into focused PRs:
  - PR #2: Core fumigation workflow/backend (`pr1-fumigation-core`)
  - PR #3: UI refresh/templates (`pr2-ui-refresh`, based on PR #2)
  - PR #4: PDF reporting/docs (`pr3-reporting-docs`, based on PR #2)
- Marked old PR #1 as superseded and closed it in favor of #2/#3/#4.
- Added PR coordination guidance to `README.md` and committed:
  - Commit `9fb25c6` on `pr3-reporting-docs`

## TODO (Timestamped)
- [ ] 2026-02-14 10:29:44 -03:00 - Merge PR #2 first, then rebase/retarget PR #3 and PR #4 to `master`.
- [ ] 2026-02-14 10:29:44 -03:00 - Decide whether `.claude/settings.local.json` should remain local-only or be documented in contributor docs.
- [ ] 2026-02-14 10:29:44 -03:00 - Keep local artifacts out of PRs (`app/instance/database.db`, `.claude/`, `PROJECT_NOTES.md`).

## Session Entry Template
Use this block for future updates:

### YYYY-MM-DD HH:mm:ss ±HH:MM
- Summary of major changes.
- Branches/PRs touched.
- Key commits (short hash + message).

TODO entries format:
- [ ] YYYY-MM-DD HH:mm:ss ±HH:MM - Task description.
