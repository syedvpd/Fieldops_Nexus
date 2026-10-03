# Phase 3 acceptance report: M08 Inspection & Checklist Engine + M07 Technician Workspace

Merged to `main` as 288de8d (fast-forward) and applied to Supabase on the Team Lead's request (2026-10-03): `checklists.0001`, `workspace.0001`, no drift afterwards, permissions and role templates present for both QA organizations. No QA data was created for M07/M08 yet. This report does not claim Team Lead approval.

## Status
**IMPLEMENTED; automated verification PASS on local PostgreSQL 16; Browser: DEFERRED by the Team Lead; Responsive: DEFERRED; Supabase audit: DEFERRED.** Nothing below is marked PASS on browser evidence.

## Automated results
| Check | Result |
|---|---|
| Full `pytest` (fresh test DB, `--create-db`) | **372 passed** (308 before + 64 new: 45 M08, 18 M07/UI, 1 fresh-DB migration) in 29m42s |
| `ruff check src tests` | clean |
| `manage.py check` | no issues |
| `makemigrations --check --dry-run` | no drift (also on a fresh database in `test_migrations_phase3`) |
| OpenAPI (`spectacular --validate --fail-on-warn`) | 0 warnings, 0 errors |
| Migrations | `checklists.0001`, `workspace.0001` (new apps; no existing migration touched) |

## M08 feature matrix (code -> test -> API -> DB; UI render/POST via Django test client)
| Feature | Code | Test | API | DB | UI | Browser |
|---|---|---|---|---|---|---|
| Template create / edit draft / activate / deactivate | yes | yes | yes | yes | yes | DEFERRED |
| Items: add / edit / remove (draft) / reorder, type + range + option validation | yes | yes | yes | yes | yes | DEFERRED |
| Versioning, frozen active templates, one active per key | yes | yes | yes | yes (partial unique) | yes | DEFERRED |
| Inspection start, answers (4 types), refresh preserves, invalid rejected all-or-nothing | yes | yes | yes | yes | yes | DEFERRED |
| Required answers, exception findings, evidence requirements gate completion | yes | yes | yes | yes | yes | DEFERRED |
| Completed = authoritative / immutable; duplicate completion + execution refused; concurrent completion | yes | yes | yes | yes (unique index, check) | yes | DEFERRED |
| Findings (context, severity, status, resolve) | yes | yes | yes | yes | yes | DEFERRED |
| Evidence (`files.Attachment`, type validation, scoped download) | yes | yes | yes | yes | yes | DEFERRED |
| Standalone asset inspection | yes | yes | yes | yes | no UI entry point (D-041) | n/a |

## M07 feature matrix
| Feature | Code | Test | DB | UI | Browser |
|---|---|---|---|---|---|
| My Jobs (assigned only, filters, no per-row queries) | yes | yes | n/a | yes | DEFERRED |
| Job detail, start / hold / resume / complete via M06 `transition` | yes | yes | yes | yes | DEFERRED |
| Planner / supervisor actions refused in the workspace and at M06 | yes | yes | yes | yes | DEFERRED |
| Checklist execution (HTMX fragment + redirect, plain fallback) | yes | yes | yes | yes | DEFERRED (HTMX only exercised through the HX-Request responses) |
| Notes (append-only), labor (M06 rules), material (free text, no stock), evidence | yes | yes | yes | yes | DEFERRED |
| History / status | yes | yes | yes | yes | DEFERRED |

## M06 integration and closure-blocker verification (verified)
`workorders.services.closure_blockers` and the `complete` guard call `checklists.services.checklist_blockers` (persisted state only). Matrix tested: no required checklist (M06 unchanged, closes); required but not started (blocked); incomplete inspection (blocked); complete inspection (clears, closes); newly required checklist re-blocks; unfinished inspection of a deactivated required template blocks; template type applicability; malicious API completion -> 409 `checklist_incomplete`, status unchanged in DB; UI completion refused with a message; DB state asserted after each step. No second closure system, no second work-order state machine (workspace calls `transition`).

## RBAC / tenant / site-scope / IDOR (verified by tests)
- RBAC: technician cannot browse or manage templates (403); read-only role cannot write (403); supervisor holds `inspection.*` but cannot execute work that is not theirs (assignee / dispatcher rule); only `inspection.review` resolves findings; unmapped actions denied.
- Tenant: Beta cannot read, execute, activate, resolve or download anything of Alpha (404 on API, HTML and file URLs); cross-tenant template / asset / work order in services -> `ValidationFailed`; guessed UUIDs -> 404.
- Site scope: a supervisor scoped to another site gets 404 for the inspection, findings, job and lists.
- Other technician's job / inspection / evidence: 404 (existence not revealed). Unauthenticated -> login redirect; suspended membership refused; CSRF enforced on workspace posts.

## Journey (no DB injection)
`test_full_journey_incident_to_closed_through_api_and_html`: incident -> approve -> work order (API) -> plan / assign / dispatch (API) -> workspace start -> checklist with exceptions -> findings -> finding evidence -> inspection completed -> note, labor, material, evidence -> complete -> supervisor review -> close -> finding resolved; asserts rows and audit actions.

## Defects found and fixed during the phase
1. `FOR UPDATE` on a query joining a nullable FK (`work_order`) failed on PostgreSQL -> `select_for_update(of=("self",))`.
2. Notes endpoint did not require `work_order.record` (read-only role got a redirect instead of 403) -> permission added, test added.
3. OpenAPI warnings (untyped path parameter, method-field types, enum name collisions) -> fixed (0 warnings).
4. Migration choices labels drifted from the model -> unapplied migration regenerated.
No open Critical/High defects known.

## Remaining risks / open points
- **Browser, responsive (1920 / 1366 / 768 / 390), console/network, keyboard use and the HTMX flow in a real browser are NOT verified.** `docs/manual-tests/PHASE_3_MANUAL_TEST.md` is ready.
- Supabase: schema applied, but no persistent QA data exists for M07/M08 and the screens have not been exercised against it.
- Applicability is evaluated live (D-040): activating a new required checklist also blocks open, not-yet-completed work orders. Needs Team Lead confirmation vs. a snapshot-at-start model.
- Materials stay free text (M09 not built); asset status on work start still undecided (D-035).
- Standalone asset inspections have no UI entry point yet (QR / M12 or a later UI task).
- Full regression is slow (about 30 minutes, dominated by fresh-database migration tests).
