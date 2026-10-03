# Handoff: Phase 4 committed, Phase 5 built (uncommitted), Phase 6 in progress

Worktree `claude/admiring-dhawan-507e3a`. Phase 4 (M09) is committed as `b77fef9` and fully verified (439 tests, browser, DB; report `docs/PHASE_4_ACCEPTANCE_REPORT.md`).

## Phase 5 (M04) - code, tests and docs written, NOT committed
- App `maintenance` (+ `workorders.0003` source_type/source_id, M08 hook in `checklists/services.py` + `selectors.py`), D-043, docs (module, integration, manual test, TRACEABILITY, DOMAIN_MODEL, MODULE_STATUS, PROJECT_MAP) done.
- Tests: `tests/test_m04_*.py`, `test_migrations_phase5.py`, one backfill test in `test_phase2_rules.py`. Full run before the Phase 6 edits: 513 passed, 7 failed. The 7 failures were NOT real: 6 migration tests failed because `apps.sla` was added to INSTALLED_APPS mid-run without a migration; 1 was `test_unscoped_is_only_used_in_trusted_modules` (fixed: `maintenance/tasks.py generate_schedule` no longer uses `.unscoped()`; signature is now `(organization_id, schedule_id)`).
- Browser verified (QA DB `fieldops_qa` in the `fieldops-test-pg` container): plan -> meter schedule (1200 h, every 500 -> 1500) -> scheduler -> WO source shown -> duplicate guard -> 4 viewport sizes. DB checked (no duplicates/orphans).
- STILL TO DO for Phase 5: run the full suite once more; write `docs/PHASE_5_ACCEPTANCE_REPORT.md` (numbers + the evidence above); commit.

## Phase 6 (M11) - partially written
Done: `apps/sla/` models, services (profiles, targets, rules, tracking, pause, monitor, breaches), selectors, API (`api_views.py`), permissions, navigation, tasks; hooks in `incidents/services.py` and `workorders/services.py`; settings (INSTALLED_APPS, beat), `config/urls.py` routes, role template `sla.acknowledge` for operations manager.
Missing: `apps/sla/migrations/0001_initial.py` (run `makemigrations sla`; Docker/Postgres must be up), real `apps/sla/urls.py` + `views.py` + `forms.py` + templates (`src/templates/sla/`: trackings, tracking detail, breaches, profiles list/detail/new with targets+rules forms, "Run check now" button; SLA panels on request and work-order detail), tests (controllable clock T0..T4 via `tests/pm_support.freeze`, pause/resume, duplicate processing, Celery retry, RBAC/tenant/IDOR, API metrics), D-044 in DECISIONS.md, module/integration docs, acceptance report, manual test, migration test, browser verification, then `docs/PHASE_4_5_6_INTEGRATION_REPORT.md` and the final report.
Design decisions to record as D-044 (OUR IMPLEMENTATION DECISIONS): timers start at persisted `created_at`; response = first transition out of NEW (request) / first assignment (work order without request); resolution = RESOLVED/COMPLETED; pause only for states listed in `SLAProfile.pause_states` (tokens like `WORK_ORDER:ON_HOLD`), unconfigured = keeps running; wall-clock minutes (business hours NOT implemented, HPE silent); breach unique per (tracking, target), events unique by dedupe key; rules fire once each, max 6 per profile; no rule = no notification.

## Environment notes
Docker Desktop must be running (container `fieldops-test-pg` on :55432; password via `docker inspect`, never printed). Helper scripts live in the session scratchpad (not in the repo). Use `--create-db` for the first pytest run after new migrations.
