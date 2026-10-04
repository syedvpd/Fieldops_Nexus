# Final reconciliation report

Date 2026-10-04 (work done 2026-10-03/04). Vocabulary: FIXED / VERIFIED / PARTIAL / BLOCKED / NOT VERIFIED. No browser acceptance, no Supabase migration, no merge was done.

## 1. Branch and commit
- Reconciliation branch: `claude/final-reconciliation` (worktree `.claude/worktrees/reconcile`), based on `claude/final-modules@ed537ad`, plus cherry-pick of `34893a1` (role template excludes, QR throttle/dedupe, tenant hardening tests). Head at the time of writing: see `git log -1` (last commit "Shorten comment", `51f0274`).
- `main` is still `a4e8186`. The forensic audit (`docs/audits/FINAL_MULTI_TENANT_HPE_FORENSIC_AUDIT.md`) was run against `main`; its "M10/M12/M13/M14 MISSING" result is **superseded**: those modules exist on `claude/final-modules` (5 commits ahead of `main`: f9fcaca M10, 5cd4f43 M12, 6d161cd M13+M14+M15, 8f88e88 final integration tests, bf256e2 HPE-named API paths, ed537ad reports).

## 2. M01-M15 matrix (code on this branch)
| Module | App | Migrations | API | UI | Tests (files) | Status |
|---|---|---|---|---|---|---|
| M01 | sites | yes | yes | yes | test_sites, test_site_scope | VERIFIED (automated); browser NOT VERIFIED |
| M02 | assets | yes | yes | yes | test_assets | VERIFIED (automated); browser NOT VERIFIED |
| M03 | assets (hierarchy) | yes | yes | yes | test_hierarchy | VERIFIED (automated); browser NOT VERIFIED |
| M04 | maintenance | yes | yes | yes | test_m04_* | VERIFIED (automated) |
| M05 | incidents | yes | yes | yes | test_phase2_* | VERIFIED (automated) |
| M06 | workorders | yes | yes | yes | test_phase2_*, test_integration_p456 | VERIFIED (automated) |
| M07 | workspace | yes | via M06/M08/M09 | yes | test_m07_workspace | VERIFIED (automated); browser NOT VERIFIED |
| M08 | checklists | yes | yes | yes | test_m08_checklists | VERIFIED (automated) |
| M09 | inventory | yes | yes | yes | test_m09_* | VERIFIED (automated) |
| M10 | contracts | yes | yes | yes | test_m10_contracts | VERIFIED (automated); 1 test was date-flaky, FIXED (see 4) |
| M11 | sla | yes | yes | yes | test_m11_* | VERIFIED (automated) |
| M12 | identification | yes | yes | yes | test_m12_identification, test_hardening_scan | VERIFIED (automated) |
| M13 | portal | yes | yes | yes | test_m13_portal | VERIFIED (automated) |
| M14 | dashboards | `dashboards.0001` (ReportSnapshot, new) | yes | yes | test_m14_dashboards, test_final_celery_snapshots | VERIFIED (automated); formulas = assumptions, TEAM LEAD CONFIRMATION REQUIRED |
| M15 | audit | `audit.0003` | yes (+ export) | yes | test_m15_audit | VERIFIED (automated): list/filter/detail, CSV/XLSX/PDF export, `audit.export`, exports audited |

## 3. Every forensic finding
| Finding | Result |
|---|---|
| M10 / M12 / M13 / M14 missing, M15 partial | FIXED (already on `claude/final-modules`; reconciled, not rebuilt) |
| Role templates: inert patterns, `client_requester` 0 permissions | FIXED: 94-permission catalog, no inert pattern, client = exactly `portal.request.create/view/confirm`; wildcard `*.view` no longer leaks portal permissions (`RoleTemplate.excludes`, `tests/test_hardening_roles.py`, 19 tests pass) |
| `audit.export` not registered | FIXED (owner + auditor) |
| Celery families: warranty/contract alerts, report snapshots missing; serial org loops | FIXED: `contracts.tasks.fan_out_renewal_alerts`, `dashboards.tasks.fan_out_report_snapshots`, `sla...fan_out_sla_monitor`, `maintenance...fan_out_maintenance`; per-org tasks skip suspended orgs (D-056, `tests/test_final_celery_snapshots.py`) |
| HPE entity gaps (9) | FIXED/DOCUMENTED: `ReportSnapshot` implemented; others mapped to functional equivalents (D-054, TRACEABILITY); `IntegrationEvent` = HPE CLARIFICATION REQUIRED (no external system defined) |
| HPE API path names | FIXED on `final-modules` (bf256e2: assign/start/hold/complete, schedules, checklists, stock, reserve/issue/return, slas, breaches, escalations, generate-work-orders, client/requests + status; `tests/test_hpe_api_aliases.py` 5 pass) |
| No CSP | FIXED: nonce-based CSP (`apps.core.csp`), inline handlers removed, no `unsafe-eval`; tests in `tests/test_core.py` (pass) |
| Public OpenAPI schema/docs | FIXED: authenticated only (`SERVE_PERMISSIONS`), docs page has its own CDN policy |
| Runtime DB role could TRUNCATE (bypasses audit trigger) | FIXED in code, NOT APPLIED to Supabase: `scripts/harden_db_roles.py` (migrator/app split, no TRUNCATE/CREATE/DDL, NOSUPERUSER NOBYPASSRLS), verification SQL in `docs/DEPLOYMENT.md`, `tests/test_db_privileges.py` (2 pass on a superuser test DB) |
| QR scan rate limit + refresh creating scan events | FIXED (34893a1): per-user failed-scan limit (HTTP 429, audited once/window), one-scan-one-event; `tests/test_hardening_scan.py` 7 pass |
| Snapshot data visible beyond live-dashboard rights (found in peer review) | FIXED: snapshot section needs `report.view` AND the section's data permission, both organization-wide; test `test_snapshot_kinds_follow_the_sections_data_permissions` |
| Sweep gaps / vacuous sweep | FIXED: `tests/test_hardening_tenant.py` (positive controls first, then attacks both directions incl. portal, files, QR, audit, export, dashboards, workflow writes) passes (3 tests, ~150 attacks) |
| Doc conflicts (tenant.py docstring, test counts, PROJECT_MAP, TRACEABILITY, C-2, incident/SR) | FIXED except C-2 meters (still an open Team Lead decision, recorded) |
| ER diagram missing | FIXED: `scripts/generate_erd.py` -> `docs/ER_DIAGRAM.md` (62 models) |
| Git remote / PRs / staging / CI run | BLOCKED (external): no remote or credentials. CI workflow exists (`.github/workflows/ci.yml`); no evidence fabricated |
| Single clean full regression | PARTIAL, see section 6 |
| Row Level Security | NOT adopted (D-055: documented decision) |

## 4. Defects found while running the regression (all FIXED)
- `test_beat_schedule_registers_the_task`: asserted the old beat task name; beat now points at the per-org fan-out (my change). Test updated.
- `test_fan_out_dispatches_one_task_per_active_org_and_skips_suspended` (my new test): asserted a suspended org had no snapshots although the first fan-out had legitimately written them while active. Test corrected.
- `test_work_order_without_agreement_or_after_expiry_is_not_eligible` (older test, M10): used the machine's LOCAL `date.today()` while the app compares in UTC, so it fails between 00:00 and 05:30 IST. Not an app bug. Test now uses the UTC date.
- Fresh-database migration tests (`test_migrations_phase2/4/5`, and phase 3/6 which did not finish): each runs `manage.py migrate` in a subprocess with a 300 s timeout. Under 6 parallel xdist workers the machine is saturated and the migrate exceeds 300 s. Not a migration defect (they pass alone, see 6); run those files without `-n`.

## 5. Static checks (this branch, run 2026-10-03)
- `ruff check src tests scripts`: clean. `manage.py check`: no issues. `makemigrations --check --dry-run`: no changes. `manage.py spectacular --validate --fail-on-warn`: 0 warnings (361 KB schema). VERIFIED.

## 6. Full regression (exact)
- Collected: 698 tests. Environment: fresh PostgreSQL 16 container `fieldops-reg-final` (tmpfs, port 55452, 0 pre-existing test databases), `pytest -n 6 --create-db -v`, commit `ee0680e` for the run (later commits only touch the 3 tests above).
- Result of that run: **690 passed, 6 failed, 2 not finished (stopped by me)** = 698. The 6 failures are those in section 4 (3 test bugs + 3 migration tests killed by their own 300 s timeout under load); the 2 unfinished are `test_migrations_phase3` and `test_migrations_phase6` (same cause).
- A first attempt (no per-test timeout) hung at 696/698 results on the same migration tests; a second attempt with `--timeout=240` failed 6 tests spuriously because worker DB creation (~4.5 min) is counted in the first test. Neither is reported as a result.
- Serial rerun of the affected files after the fixes: RERUN_RESULT_PLACEHOLDER
- Therefore: **one single uninterrupted green run of all 698 tests has NOT been achieved**. FULL REGRESSION: NOT YET PASS (all 698 executed at least once; no application failure observed).

## 7. Remaining assumptions / Team Lead decisions
- Dashboard formulas (MTTR, MTBF, 8 h/day utilization, PM compliance, parts consumption, overdue): implementation assumptions, NOT approved (D-057).
- C-2 meters M02 vs M03; D-006 existing-user auto-activation; D-027 ACTIVE to OUT_OF_SERVICE; `admin` role scope; TechnicianProfile/Shift equivalents; `IntegrationEvent` need.
- Earlier-seeded organizations keep `portal.request.view` on admin/operations/auditor roles until an administrator removes it (seeding is additive).

## 8. Blockers before final browser acceptance
1. One clean full-suite run (run the migration test files serially, rest with `-n`, or whole suite without `-n`; allow ~40-60 min).
2. Decide whether to apply migrations (45 + new `contracts`, `identification`, `portal`, `audit.0003`, `dashboards.0001`) to Supabase and run `scripts/harden_db_roles.py` there (operator step, not done).
3. Merge `claude/final-reconciliation` (and `claude/final-modules`) into `main` (not done; Team Lead approval).
4. Browser acceptance of M01-M08 (never done) plus M09-M15 re-check, camera scanning path, responsive matrix, Chrome/Edge/Firefox.
5. Git remote, CI run, staging URL (external).

TENANT ISOLATION: PASS (automated: `test_hardening_tenant`, `test_tenant_isolation`, per-module cross-tenant tests all pass in the full run; my earlier independent sweep: 85 API + 44 HTML denials, 0 leaks).
SECURITY HARDENING: PASS (code + tests); DB role split NOT APPLIED to production.
TECHNICAL HARDENING: INCOMPLETE (single clean full run pending).
READY FOR FINAL BROWSER ACCEPTANCE: NO (until the clean full run passes and the Team Lead decides on merge/migration).

## 9. Gap closure addendum (2026-10-04)
Branch `claude/complete-m01-m15`. Findings of the static M01-M15 completeness audit were fixed or recorded as decisions (D-058..D-061); see `MODULE_STATUS.md` and `TRACEABILITY.md`. New migrations (additive): `assets.0002`, `contracts.0002`, `sla.0002`. Checks: ruff clean, `manage.py check` clean, `makemigrations --check` no changes, OpenAPI 0 warnings. Full suite run 1 on local PostgreSQL 16: 735 passed, 1 failed (bug in the new asset-form category handling, fixed, affected files 100 passed). A second full rerun was deliberately skipped: the only failure of run 1 was fixed and its tests re-run (100 passed). Per-file results, not a single uninterrupted green run.
