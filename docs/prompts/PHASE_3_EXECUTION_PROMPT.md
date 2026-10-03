# Phase 3 execution prompt: M08 Inspection & Checklist Engine + M07 Technician Workspace

Written by the Team Lead (2026-10-03) for a NEW Claude Code session. The repository is the memory: do not rely on prior conversation. This is a condensed, faithful copy of the Team Lead's prompt plus one override (below).

## Overrides by the Team Lead (win over anything below)
- **Do NOT spend effort on browser acceptance, responsive sweeps or the visible-pane audit in this phase.** All browser/E2E/responsive/Supabase-audit work is done ONCE at the end, after all modules are finished. Phase 3 is verified by backend/API/UI-render tests on local PostgreSQL only. Say so in the report ("Browser: DEFERRED by Team Lead"); do not mark it PASS.
- Work in a fresh git worktree of `main` (Phase 2 is already merged and applied to Supabase: 38 migrations). Merge/apply to Supabase only when the Team Lead asks.
- Do not start Phase 4.

## Token-optimized mode
Implementation quality over narration. Read only what is needed (grep, targeted reads, targeted tests), do not paste files, do not re-read docs, summarize in 3-8 bullets per logical unit, ask only for genuine conflicts / destructive or security-sensitive ambiguity / blocking gaps. Never reduce tests, RBAC, tenant isolation, negative tests, DB verification or docs to save tokens.

## Start
1. Confirm checkout/branch/status. 2. Read in order: `CLAUDE.md`, `docs/PROJECT_SOURCE_OF_TRUTH.md`, `docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md`, `docs/MODULE_STATUS.md`, `docs/DECISIONS.md` (D-034..D-038 are Phase 2), `docs/DOMAIN_MODEL.md`, `docs/TRACEABILITY.md`, `docs/modules/M07*`, `docs/modules/M08*`, `docs/integrations/incidents-workorders.md`. 3. Inspect the M05/M06 code (`src/apps/incidents`, `src/apps/workorders`: `services.py`, `closure_blockers`, selectors, views, tests), RBAC, audit, `files.Attachment`, UI patterns. 4. Baseline: full pytest on local Docker Postgres (`fieldops-test-pg` :55432; 308 passing after Phase 2). 5. Short execution plan, then implement.

## Scope: Phase 3 only
**M08** (owns checklist templates, items, item types, required/optional, inspection execution, responses, findings, evidence requirements, completion state, validation, applicability to work types, the closure-blocking info M06 consumes). **M07** (technician-facing workspace: my work orders, job detail, start/hold/resume/complete, checklist execution UI, notes, evidence, labor/time, material info, status/history; mobile/tablet friendly; Django templates + HTMX, no SPA).
Do NOT start M09-M15. Hooks/interfaces for later modules are fine.

## Boundaries
- M06 stays authoritative for the work-order lifecycle; M08 for checklist/inspection lifecycle; M07 is an orchestration/UI layer that calls M06 services and M08 services. M07 must NOT add a second work-order state machine or duplicate M06 logic.
- Closure integration: wire M08 into the existing `workorders.services.closure_blockers` (and the completion guard). No second closure system, no fake "checklist complete = true": query real persisted inspection state. Required checklist missing/incomplete -> completion/closure blocked (backend, not frontend); complete -> cleared; no required checklist -> existing M06 behaviour.
- Materials: M09 does not exist. Keep the Phase 2 free-text material lines; no stock issue/return/reservation, no fake balances; record the M09 boundary.
- Evidence: reuse `files.Attachment` + `files.access`; labor: reuse M06 `WorkOrderLabor` and its rules (hours 0<h<=24, not future, valid technician/work order).

## M08 design (implement only what HPE / master workflow / decisions / real UI+API needs justify)
Entities (follow repo naming): ChecklistTemplate, ChecklistItem, Inspection, InspectionResponse, Finding. Item types: text, numeric, boolean/pass-fail, selection; required vs optional; ordering; guidance; finding creation where appropriate; evidence requirement where the requirement calls for it. Template management: create, edit draft, activate/deactivate, add/reorder items, configure type/required/validation, view, execute, inspect results, findings. Historical inspections must stay understandable: use versioning/snapshotting (no destructive edits of used templates); if no repo decision exists, choose the least disruptive design and record it in `docs/DECISIONS.md`. Findings retain inspection, item, asset/work-order context, content, severity if required, status if required, created by, timestamp. A technician must not falsely complete a checklist: required items answered, invalid types/values rejected, responses persist, refresh preserves state, completed state is authoritative in the DB, backend validation mandatory.

## M07 design
Views: My Work Orders, Work Order detail, Start/Hold/Resume, Checklist, Notes, Evidence, Labor/Time, Material info, Completion, history/status. Visibility = existing M06 rules (technician sees only own assigned work). Technician gets no planner/supervisor authority; hidden buttons are not security; test direct URL/API access.

## Security and data
Tenant isolation and site scope on every new object (guessed UUIDs/attachments -> 404/403 per existing conventions); proper FKs/indexes; avoid N+1 in the workspace; no DROP/TRUNCATE/mass DELETE; migrations clean; never touch Supabase data destructively.

## Tests (write first / alongside)
M08: template create/permissions, items, required/optional, response persistence, invalid response/numeric, inspection create/complete, incomplete required, findings, evidence, tenant, site, historical data, malicious direct API calls. M07: sees assigned only, not others', start valid WO, invalid state rejected, checklist access, required checklist blocks completion, complete allows it, notes/evidence/labor persist, unauthorized rejected, cross-tenant rejected, refresh preserves state. Adversarial: wrong tenant/org/site, inactive user, unauthorized role, direct POST/PATCH/transition, duplicate execution/submission, stale form, concurrent completion where practical, invalid types, missing evidence, deactivated template, cross-tenant attachment, guessed inspection/work-order URLs. Journey test (API + HTML UI, no DB injection): Organization > Site > Asset > Incident > Work Order > assignment > workspace > start > checklist > required responses > finding > evidence > labor > complete > supervisor review > close. Closure matrix: WO without required checklist; with required checklist but no inspection; incomplete inspection; complete inspection; malicious API completion; UI completion; DB state.

## Gates and docs
Run targeted tests first, then full `pytest`, `ruff check src tests`, `manage.py check`, `makemigrations --check --dry-run`, OpenAPI generation (0 warnings), fresh-DB migration test. Update `docs/MODULE_STATUS.md`, `docs/TRACEABILITY.md`, `docs/DECISIONS.md`, `docs/modules/M07*`, `docs/modules/M08*`, `docs/PROJECT_MAP.md`, `docs/integrations/` (checklist <-> work order contract), write `docs/manual-tests/PHASE_3_MANUAL_TEST.md` and `docs/PHASE_3_ACCEPTANCE_REPORT.md` (feature matrices, API/DB/RBAC/tenant/site verification, M06 integration, closure-blocker verification, test totals, defects, risks; browser/responsive marked DEFERRED). No fake completion: CODE -> TEST -> API -> DB -> UI; anything untested is BLOCKED/DEFERRED, not PASS.

## Git safety
No force push, history rewrite, destructive reset, branch deletion, secrets (`.env*`, passwords, tokens) or large artifacts in commits; meaningful commits; `git diff`/`status` and tests before committing. Python on Windows rewrites LF files as CRLF in text mode: edit with `newline=''` or the Edit tool.

## Final output (concise, then STOP)
`PHASE 3 STATUS: PASS — VERIFIED` or `BLOCKED — DEFECTS REMAIN`; M08 X/Y; M07 X/Y; M06 integration verified/not; Browser: DEFERRED; DB: verified on local PostgreSQL (Supabase apply only on request); tests passed; defects; docs updated; commits; remaining Team Lead decisions. Never claim APPROVED. Do not start Phase 4.
