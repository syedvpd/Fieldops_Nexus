# Findings register: FieldOps Nexus M01-M15 audit (2026-10-04)

Audit of branch `ccr-a9c54b8b-icbtpz` (HEAD `95dfc50`). Phase 1 was **read-only**: no source, migration, configuration or test file was changed. All runtime work used an isolated local audit database (`fieldops_browser_qa`) and a local Redis on :6390; nothing touched Supabase/production.

**Evidence tags used below**
- **RUNTIME** = reproduced by me against the running application (browser, HTTP, DB, Celery). Scripts are in `docs/audits/final/tools/`, raw results in `docs/audits/final/evidence/`.
- **STATIC** = established by reading code/schema only (four read-only static auditors plus my own reading); not reproduced at runtime.
- **UNVERIFIED** = cannot be established from this environment.

**Severity rules applied** (as specified): CRITICAL production/security/data-integrity blocker; HIGH major HPE workflow broken or serious authorization/business-rule defect; MEDIUM important functional deficiency or integration gap; LOW minor; COSMETIC visual only; UNVERIFIED; INTENTIONAL (deliberate, documented decision).

**Totals:** CRITICAL 0 · HIGH 2 · MEDIUM 20 · LOW 57 · COSMETIC 4 · INTENTIONAL 11 · UNVERIFIED 10. HIGH and MEDIUM findings use the full 17-field format (section A, B). LOW / COSMETIC / INTENTIONAL / UNVERIFIED are in compact tables (sections C-F) carrying ID, module, severity, location, behaviour, fix and the regression test needed.

No CRITICAL finding was established. Cross-tenant isolation was attacked in both directions (UI, REST, files, QR, dashboards, audit, exports, workflow actions) and **no leak was found**.

---

## A. HIGH

### F-H01: Editing a PM schedule's recurrence silently stops work-order generation
- **ID:** F-H01 (source M04-01) **Module:** M04 (touches M06, M14) **Severity:** HIGH **Evidence:** RUNTIME (reproduced)
- **Requirement:** HPE "PM scheduler generates future WOs without duplicates and handles missed/overdue cycles"; D-043 "editing the recurrence restarts at the next occurrence that is not in the past".
- **Expected behavior:** after changing interval/frequency/start date (or meter interval), the next due occurrence still generates a work order.
- **Actual behavior:** `update_schedule` -> `_resync` resets `next_sequence` to the first not-yet-past occurrence **under the new recurrence**, but previously generated `MaintenanceCycle` rows keep their old sequence numbers. `UNIQUE(schedule, sequence)` then collides; `generate_cycle` catches the `IntegrityError`, silently advances `next_sequence`, creates nothing, returns `None`. No `last_error`, no audit row, nothing in the UI. This repeats for every occurrence until the new sequence exceeds the old maximum, i.e. roughly as long as the schedule has already existed.
- **Evidence:** `docs/audits/final/tools/m04_edit_bug.py` (real service layer, controlled clock): weekly schedule, 8 weekly cycles generated (sequences 1-8); edited to every 2 weeks; over the next 10 weeks the scheduler generated **1** work order (expected about 5); `last_error` empty; cycles afterwards 1-9. Existing test `tests/test_m04_maintenance.py:321` has one cycle and only asserts `next_due_date`.
- **File:** `src/apps/maintenance/services.py` **Line/function:** `update_schedule` (299), `_resync` (210), `generate_cycle` IntegrityError branch (460).
- **API/URL:** `PATCH /api/v1/maintenance-schedules/{id}/`, UI `/app/maintenance/schedules/{id}/edit/`.
- **Database impact:** no work orders are created for due occurrences; consumed sequence numbers are never reused; PM compliance KPI shows nothing "missed" because no cycle exists.
- **Browser evidence:** edit form reachable (`m04.py`); the loss itself is a scheduler effect (Celery/service path), reproduced through the real service layer, not a click.
- **Security impact:** none.
- **Business impact:** silent loss of preventive maintenance after a routine schedule edit: a safety/compliance risk and a direct hit on HPE's headline PM requirement.
- **Recommended fix:** on a recurrence change set `next_sequence = max(resync_result, max(existing cycle.sequence) + 1)` and recompute the due date for that sequence (or add a recurrence "epoch" to the unique key). In the `IntegrityError` branch set `last_error`, write an audit entry and surface it on the schedule page; never skip silently.
- **Regression test required:** generate N cycles with a frozen clock, edit the interval, advance the clock, assert the next due occurrence creates a WO and that any skip is visible; same for a meter interval increase.
- **HPE acceptance impact:** Day-90 journey 2 (PM -> scheduler -> WO) passes only on the unedited path; **must be fixed before acceptance**.

### F-H02: Audit-trail and stock-ledger immutability is not enforced against the database owner role; production hardening is not applied
- **ID:** F-H02 (sources SEC-005, DB-3, DEP-002, M09-001) **Module:** M15 / M09 / deployment **Severity:** HIGH (code defect confirmed; production exposure UNVERIFIED) **Evidence:** STATIC + RUNTIME on local DB (`has_table_privilege(..., 'TRUNCATE')` = true for the app role; `pg_trigger` shows one row-level trigger only)
- **Requirement:** CLAUDE.md "NEVER ... TRUNCATE app tables" and HPE "auditable, append-only audit"; the repo claims immutability at three layers.
- **Expected:** neither the application role nor SQL injected through it can rewrite or erase `audit_auditlog` (or the stock ledger).
- **Actual:** `audit.0002` installs a row-level `BEFORE UPDATE OR DELETE` trigger only. `TRUNCATE`, `ALTER TABLE ... DISABLE TRIGGER` and `DROP TRIGGER` are not blocked for the table owner. `scripts/harden_db_roles.py` (role split, no TRUNCATE/DDL) is operator-run and `docs/DEPLOYMENT.md` states it is **not applied to Supabase**; the same document describes the admin password as weak and the database as internet-reachable. `StockMovement` and the history tables (`AssetStatusHistory`, `AssetLocationHistory`, `WorkOrderEvent`) are append-only only through ORM overrides (no trigger). Reversing `audit.0002` silently drops immutability.
- **Evidence:** `src/apps/audit/migrations/0002_audit_immutable_trigger.py:3-12`; psql `\d audit_auditlog` (single trigger `audit_auditlog_immutable`); `scripts/harden_db_roles.py` header; `docs/DEPLOYMENT.md:35,45`; API `PATCH/DELETE /api/v1/audit-logs/{id}/` return 403 for every role including Owner (RUNTIME, `rbac_matrix.py`), so the ORM/API layers hold; the DB layer is the gap.
- **File:line:** `src/apps/audit/migrations/0002_audit_immutable_trigger.py:3-12`; `src/apps/inventory/models.py:241-247`; `src/apps/assets/models.py:80-92`.
- **API/URL:** none (database layer).
- **Database impact:** audit and ledger history can be wiped or rewritten by the owner role or a compromised credential/SQL-injection path.
- **Browser evidence:** n/a.
- **Security impact:** tamper-evidence of the audit trail is the core compliance promise (M15). In production the live state is UNVERIFIED (no Supabase access); if the runtime still uses the owner role the promise is false.
- **Business impact:** audit/evidence packages are not defensible to an auditor until the role split is applied and TRUNCATE is trapped.
- **Recommended fix:** add `BEFORE TRUNCATE ... FOR EACH STATEMENT` triggers (audit + ledger + histories); apply `harden_db_roles.py` in production and rotate the admin password; add the same row triggers to `inventory_stockmovement` and the history tables; fix F-M18 first so the app role can stay non-owner.
- **Regression test required:** `tests/test_db_privileges.py` already exists; add (1) TRUNCATE on `audit_auditlog` fails under the runtime role and via the trigger, (2) raw UPDATE/DELETE on ledger/history tables raise, (3) readiness check that fails if the runtime role owns audit tables.
- **HPE acceptance impact:** M15 evidence integrity and security hardening gate; **must be resolved (and verified on the production database) before Day-90 acceptance**.

---

## B. MEDIUM

### F-M01: Reopening a resolved request while its work order is still COMPLETED produces HTTP 500 and a dead end
- **ID:** F-M01 (M05-01) **Module:** M05 / M06 / M13 **Severity:** MEDIUM **Evidence:** RUNTIME
- **Requirement:** HPE request chain RESOLVED -> CONFIRMED/rework (D-035); client reopen via portal.
- **Expected:** a reopened request can get a replacement work order, or the user receives a clear 409 explaining what must happen first.
- **Actual:** request becomes RESOLVED when the WO is COMPLETED; the WO stays "live" until CLOSED/CANCELLED. Client `POST /api/v1/portal/requests/{id}/reopen/` -> request APPROVED. Planner `POST /service-requests/{id}/create-work-order/` hits `uniq_live_work_order_per_request` and raises an unhandled `IntegrityError` -> **HTTP 500**. The old WO cannot be cancelled (`cancel` is not allowed from COMPLETED, 409).
- **Evidence:** run with INC-000008 / WO-000018 (flow in `tools/flow.py`): reopen 200 (request APPROVED, WO COMPLETED), create-work-order **500**, cancel old WO 409. Server log shows `Internal Server Error`.
- **File:line:** `src/apps/incidents/services.py` `create_work_order_for_request` (199), `_apply` reopen (147); `src/apps/workorders/models.py:66-68` (constraint); `src/apps/portal/services.py` `reopen`.
- **API/URL:** `POST /api/v1/service-requests/{id}/create-work-order/`, `POST /app/incidents/{id}/create-work-order/`, `POST /api/v1/portal/requests/{id}/reopen/`.
- **Database impact:** transaction rolled back; request left APPROVED with a live WO.
- **Browser evidence:** UI path identical (service layer); 500 page shown.
- **Security impact:** none (information-free 500).
- **Business impact:** client-initiated rework stalls until a supervisor closes the old WO; a 500 in a core HPE flow.
- **Recommended fix:** on reopen require/force the live WO to CLOSED/CANCELLED, or catch the conflict and return a 409 with guidance; allow cancelling a COMPLETED WO that is being superseded.
- **Regression test required:** request RESOLVED while WO COMPLETED -> reopen -> create WO: expect clean 409 or a supported path.
- **HPE acceptance impact:** Day-90 journey 7 happy path passes; the rework branch is broken.

### F-M02: Request can be confirmed/closed while its work order is still under supervisor review or back in rework
- **ID:** F-M02 (M05-03) **Module:** M05 / M06 / M13 **Severity:** MEDIUM **Evidence:** RUNTIME
- **Requirement:** HPE "client request closed only after technician completion + confirmation" and a consistent request/WO lifecycle.
- **Expected:** `confirm`/`close` require every linked WO to be CLOSED; a supervisor `reject_review` after confirmation re-opens the request.
- **Actual:** request goes RESOLVED at WO COMPLETED (before supervisor review). The client can confirm immediately (observed: request CONFIRMED while WO SUPERVISOR_REVIEW). If the supervisor then runs `reject_review` the WO returns to IN_PROGRESS but `on_work_order_reworked` only acts on RESOLVED, so the request stays CONFIRMED; a Service Manager can then close the request while the WO is IN_PROGRESS.
- **Evidence:** INC-000009 / WO-000020: reject_review -> WO IN_PROGRESS, request CONFIRMED; `close` -> 200, request CLOSED, WO still IN_PROGRESS. Browser: client confirmed from the portal while the WO was in SUPERVISOR_REVIEW (INC-000002).
- **File:line:** `src/apps/incidents/workflow.py` (no guards); `src/apps/incidents/services.py:174,232-235`; `src/apps/workorders/services.py:341`.
- **API/URL:** `POST /api/v1/service-requests/{id}/transition/`, `POST /api/v1/portal/requests/{id}/confirm/`.
- **Database impact:** request and WO statuses diverge; SLA closure and downtime already ended.
- **Browser evidence:** `docs/audits/final/evidence/m13_resolved_mobile.png` (client sees "Resolved: please confirm" while review is pending).
- **Security impact:** none.
- **Business impact:** closed incident with active rework; SLA/closure evidence misleading.
- **Recommended fix:** guard `confirm`/`close` on all linked WOs CLOSED; make `reject_review` reopen a CONFIRMED request (or block it).
- **Regression test required:** confirm before supervisor close; reject_review after confirm; close with WO IN_PROGRESS.
- **HPE acceptance impact:** closure integrity for journey 7 and the M15 closure-approval story.

### F-M03: A rejected request leaves its downtime record open
- **ID:** F-M03 (M05-02) **Module:** M05 / M14 **Severity:** MEDIUM **Evidence:** RUNTIME
- **Requirement:** HPE M05 "downtime start/end"; M14 downtime/MTTR/MTBF.
- **Expected:** downtime ends (or is voided) when the request is rejected/cancelled; reopen reopens it.
- **Actual:** downtime is closed only in `on_work_order_completed`. Reject, cancelled WO and close-without-completion never end it; `set_downtime` refuses REJECTED/CLOSED requests so it cannot be corrected; `dashboards/metrics.py` counts open downtime up to "now" with no request-status filter.
- **Evidence:** INC-000010 created with `downtime_started_at`, triaged, rejected: `incidents_downtime.ended_at` stays NULL; correction attempt rejected.
- **File:line:** `src/apps/incidents/services.py:147-170,225-229,275-283`; `src/apps/dashboards/metrics.py:37,185-192`.
- **API/URL:** `PUT /api/v1/service-requests/{id}/downtime/`.
- **Database impact:** `incidents_downtime.ended_at` NULL indefinitely.
- **Browser evidence:** n/a (API-reproduced).
- **Security impact:** none.
- **Business impact:** inflated downtime, wrong MTTR/MTBF; asset appears down forever.
- **Recommended fix:** void/end downtime on reject/cancel; allow privileged audited correction on locked requests; reopen downtime on `reopen`/`resume_service`.
- **Regression test required:** reject with open downtime; KPI excludes it.
- **HPE acceptance impact:** M14 KPI trustworthiness.

### F-M04: Required checklists apply by work type only, so unrelated checklists block unrelated assets
- **ID:** F-M04 (new) **Module:** M08 / M06 **Severity:** MEDIUM **Evidence:** RUNTIME
- **Requirement:** HPE "WO closure requires checklist ... according to work type"; M08 template-based checklists.
- **Expected:** required checklists apply to the assets/categories/sites they were designed for.
- **Actual:** `required_templates` filters by org + work type + ACTIVE only. A corrective WO on an HVAC unit is forced to complete the "Generator corrective inspection" (output voltage 380-440 V, fuel condition). The technician must enter meaningless data to complete the job. A newly activated required template also applies retroactively to in-flight WOs (M08-02).
- **Evidence:** WO-000011 (HVAC-001 corrective, client request): workspace shows "Required checklist 'Generator corrective inspection' has not been started" and a voltage question (`m08_mobile_insp.png`).
- **File:line:** `src/apps/checklists/services.py:321-330` (`required_templates`); templates have no asset/category/site applicability.
- **API/URL:** `/app/workspace/{wo}/`, `/api/v1/inspections/`.
- **Database impact:** fabricated checklist answers stored as inspection evidence.
- **Browser evidence:** `evidence/m08_mobile_insp.png`, `evidence/m08_mobile_insp_done.png`.
- **Security impact:** none (data-integrity of evidence).
- **Business impact:** in a multi-asset organisation every corrective job either needs a bogus checklist or the checklist is deactivated (which then bypasses it for everyone; see F-M05).
- **Recommended fix:** add applicability (asset category / asset / site) and an effective-from date to templates; resolve required templates by applicability.
- **Regression test required:** required checklist for category A is not demanded on a category-B WO.
- **HPE acceptance impact:** the checklist-gated closure rule is satisfied literally but produces unusable data.

### F-M05: A PM plan whose checklist is DRAFT/INACTIVE generates work orders with no checklist gate
- **ID:** F-M05 (M04-02) **Module:** M04 / M08 **Severity:** MEDIUM **Evidence:** STATIC
- **Requirement:** HPE M04 "checklists", closure requires checklist.
- **Expected:** a plan naming a checklist always enforces it.
- **Actual:** `_check_checklist` only checks the key exists in any status; `required_templates` filters ACTIVE. If the checklist is DRAFT or deactivated the generated WO has no blocker (description still says "Required checklist: ...").
- **File:line:** `src/apps/maintenance/services.py:104-119`; `src/apps/checklists/services.py:321-330`.
- **API/URL:** `POST/PATCH /api/v1/maintenance-plans/`; WO complete/close.
- **Database impact:** none.
- **Browser evidence:** n/a.
- **Security impact:** none. **Business impact:** mandatory PM inspection can be bypassed by deactivating its checklist.
- **Recommended fix:** reject/warn on plan create when the key has no ACTIVE version; block or flag cycle generation when none exists.
- **Regression test required:** yes.
- **HPE acceptance impact:** PM + checklist integration.

### F-M06: Retiring/disposing an asset with hierarchy links leaves an undetachable tree
- **ID:** F-M06 (M03-1) **Module:** M02 / M03 **Severity:** MEDIUM **Evidence:** RUNTIME
- **Requirement:** HPE asset state machine ACTIVE -> ... -> RETIRED/DISPOSED with hierarchy integrity.
- **Expected:** retire/dispose is refused (or links detached) while live children/parents exist; open WOs/PM plans are considered.
- **Actual:** `change_status` has no hierarchy guard. After retire, `remove_component/update_component/move_component` refuse (`asset_terminal`), so live children of a retired parent can never be detached and a retired child stays linked to a live parent.
- **Evidence:** `m03.py`: parent P with child links driven to RETIRED (links remaining = 1-2); detach of the child afterwards rejected (`PROBE` records FAIL).
- **File:line:** `src/apps/assets/services.py:207-220`; `src/apps/assets/hierarchy.py:70,135,159`.
- **API/URL:** `POST /api/v1/assets/{id}/transition/`, `POST /app/assets/{id}/transition/retire/`.
- **Database impact:** orphaned assembly links on terminal assets.
- **Browser evidence:** `m03.py` output (PROBE lines in `evidence/browser_results.jsonl`).
- **Security impact:** none. **Business impact:** permanently stuck component tree, misleading BOM/tree views.
- **Recommended fix:** refuse retire/dispose with non-terminal links (409) or auto-detach with audit; check open WOs/plans.
- **Regression test required:** retire parent with children; retire child.
- **HPE acceptance impact:** M03 integrity.

### F-M07: REST API does not enforce site scope for asset documents and meter readings
- **ID:** F-M07 (M02-1) **Module:** M02 **Severity:** MEDIUM (arguably HIGH under the "site scope on every action" rule) **Evidence:** STATIC + RUNTIME (reproduced for meter readings)
- **Requirement:** CLAUDE.md "Authorization = identity + membership + permission + tenant object + site scope".
- **Expected:** API checks `asset.document.manage` / `asset.meter.record` for the asset's own site, like the HTML views.
- **Actual:** `documents` POST/remove and `readings` POST call `_asset(request, pk)` / `_meter(request, pk)` without a permission code, so only the class-level "anywhere" gate applies. A user holding the permission only at site A can write to site-B assets they can view.
- **Runtime proof:** an Auditor (org-wide read) was additionally given a role holding `asset.meter.record` scoped to site BLR-1 only; `POST /api/v1/meters/{id}/readings/` on the HYD-1 asset GEN-001 returned **201 and stored the reading**, while the HTML endpoint `POST /app/meters/{id}/reading/` returned **403**. (Roles restored afterwards.)
- **File:line:** `src/apps/assets/api_views.py:404-425,582-592` (contrast `meter.create` and `views.py:290-360`).
- **API/URL:** `POST /api/v1/assets/{id}/documents/`, `.../documents/{doc}/remove/`, `POST /api/v1/meters/{id}/readings/`.
- **Database impact:** documents/readings written for a site the actor cannot write to (audited with the real actor).
- **Browser evidence:** UI path is correct; API gap only.
- **Security impact:** intra-tenant site-scope bypass; falsified meter readings drive meter-based PM.
- **Business impact:** site-scoped technician/clerk can alter another site's documents/readings.
- **Recommended fix:** pass the permission code (`_asset(request, pk, "asset.document.manage")`, `_meter(request, pk, "asset.meter.record")`).
- **Regression test required:** API test mirroring `tests/test_site_scope.py` with org-wide `asset.view` + site-scoped write permission.
- **HPE acceptance impact:** RBAC/site-scope gate.

### F-M08: Moving an asset to another site does not propagate to open work or plans
- **ID:** F-M08 (M02-2) **Module:** M02 / M04-M06 / M11 **Severity:** MEDIUM **Evidence:** STATIC
- **Actual:** `_move` blocks only hierarchy-linked assets. `site` is denormalised into WorkOrder, ServiceRequest, MaintenancePlan, Inspection, Finding and SLA/contract rows and never updated; no open-work check.
- **Impact:** wrong dispatch scope, wrong SLA/calendar/timezone for PM windows, audit `site_id` mismatch.
- **File:line:** `src/apps/assets/services.py:193-203`; `src/apps/workorders/services.py:112`; `src/apps/maintenance/services.py:142`.
- **Database impact:** `workorders_workorder.site_id` can diverge from `assets_asset.site_id`; no constraint.
- **Browser evidence:** n/a. **Security impact:** site-scoped users see the wrong jobs. **Business impact:** misdirected maintenance.
- **Recommended fix:** refuse the site change while non-terminal work exists, or propagate inside the transaction and re-point/disable plans.
- **Regression test required:** move an asset with an open WO and a PM plan.
- **HPE acceptance impact:** M02/M05/M06 consistency.

### F-M09: A disabled client portal account keeps read access to its request history
- **ID:** F-M09 (M13-001) **Module:** M13 **Severity:** MEDIUM **Evidence:** RUNTIME
- **Requirement:** `portal.manage` can disable a client; a disabled client must lose access.
- **Actual:** after `POST /api/v1/portal-accounts/{id}/disable/`, the client could still `GET /api/v1/portal/requests/`, `/portal/assets/` (200) and open `/app/portal/requests/` and each request page in the browser; only creating a request and the "new request" form are blocked.
- **File:line:** `src/apps/portal/api_views.py:87-107`; `src/apps/portal/views.py:23-26`; `src/apps/portal/apps.py` (file checker also ignores account state).
- **Browser evidence:** probe output in `evidence/browser_results.jsonl` (M13-001 line).
- **Security impact:** revocation incomplete (reads of own history, visit windows, technician names). **Business impact:** staff cannot cut off a client.
- **Recommended fix:** apply the enabled-account check in the viewset `initial()`, the HTML mixin and the file checker.
- **Regression test required:** disabled client gets 403 on every GET.
- **HPE acceptance impact:** M13 access control.

### F-M10: Dashboard "Low-stock balances" KPI disagrees with the stock screen it drills into
- **ID:** F-M10 (M14-001) **Module:** M14 / M09 **Severity:** MEDIUM **Evidence:** RUNTIME
- **Actual:** KPI counts `min_level IS NOT NULL AND on_hand <= min_level` (balance override only); the stock list `low=1` and `StockBalance.is_low` use effective minimum (balance override else `Part.min_stock`) against **available** (on-hand minus reserved). Observed: part UIP-12877 on hand 2, part minimum 5 -> stock list shows 1 low balance, dashboard shows 0.
- **File:line:** `src/apps/dashboards/metrics.py:304-305` vs `src/apps/inventory/selectors.py:106-110`, `models.py:104-107`.
- **Business impact:** shortages under-reported (most parts use the part-level minimum). **Recommended fix:** reuse the selector predicate. **Regression test required:** part-level minimum and reserved stock.
- **Browser evidence:** `evidence/browser_results.jsonl` (M14-001 line). **Security impact:** none. **Database impact:** none. **API/URL:** `GET /api/v1/dashboards/inventory/`. **HPE acceptance impact:** M14 "no wrong KPIs".

### F-M11: Redis outage takes down the whole REST API and QR scanning; invitations are saved but the request fails and the email is lost
- **ID:** F-M11 (CEL-001, M12-001) **Module:** Celery/Redis, M12 **Severity:** MEDIUM **Evidence:** RUNTIME
- **Actual (Redis stopped):** `/health/ready/` 503 (correct); HTML pages still work (sessions in DB); **every `/api/v1/*` request returns 500** (DRF throttle uses the cache); **QR scan returns 500** (failed-scan counter in cache); HTML invite: user row committed, response error, email never queued (`.delay()` raises after commit). Recovery after Redis restart is automatic (API 200, worker/beat reconnected).
- **File:line:** `src/config/settings/base.py:175-181,232-238,276-281`; `src/apps/identification/services.py:47-60,126-136`; `src/apps/notifications/services.py:28`; `src/apps/accounts/services.py:32`.
- **Evidence:** `docs/audits/final/evidence/browser_results.jsonl` (REDIS lines); server log `Internal Server Error: /api/v1/members/`, `/app/s/<token>/`.
- **Business impact:** one cache blip = total REST outage + lost invitations; field scanning stops.
- **Recommended fix:** fail-open throttle/scan limiter (catch cache errors), wrap `.delay()` in on_commit with try/except + outbox/log, set broker/cache socket timeouts.
- **Regression test required:** patch cache/`delay` to raise; endpoints degrade, not 500. **Browser evidence:** n/a. **Security impact:** availability only. **Database impact:** committed user row without email. **HPE acceptance impact:** "Celery/Redis" and robustness.

### F-M12: Daily/6-hourly beat jobs are interval-based and restart from zero on every deploy/restart
- **ID:** F-M12 (CEL-002) **Module:** Celery **Severity:** MEDIUM **Evidence:** STATIC
- **Actual:** `report-snapshots` (24 h), `contract-renewal-alerts` (6 h), `clear-expired-sessions` (24 h) use numeric intervals; the beat schedule file is `/tmp/celerybeat-schedule` (ephemeral). On Render (frequent restarts, free-tier sleep) these can starve.
- **File:line:** `src/config/settings/base.py:144-168`; `scripts/render_start.py:31`.
- **Recommended fix:** `crontab(hour=..., minute=...)` (jobs are idempotent). **Regression test required:** assert schedule types. **Business impact:** missed renewal alerts / report snapshots. **Browser evidence:** n/a (the 60 s SLA and 15 min PM beats were observed running). **Security impact:** none. **Database impact:** missing `ReportSnapshot` days. **API/URL:** n/a. **HPE acceptance impact:** "Celery handles ... expiry alerts and report snapshots".

### F-M13: A warranty/contract renewal alert is marked "sent" even when nobody was notified
- **ID:** F-M13 (M10-001) **Module:** M10 **Severity:** MEDIUM **Evidence:** STATIC (positive path RUNTIME: alert delivered to 3 users)
- **Actual:** `run_alerts` stamps `renewal_alerted_at` and writes audit even when no active member holds `contract.update` for the site; the alert is never retried.
- **File:line:** `src/apps/contracts/services.py:505-533`. **Fix:** don't stamp when `users` is empty; fall back to org owners. **Test:** agreement with no eligible recipient. **Business impact:** an expiring contract can lapse unnoticed. **Browser evidence:** n/a. **Security impact:** none. **Database impact:** `renewal_alerted_at` set with zero notifications. **API/URL:** Celery `fan_out_renewal_alerts`. **HPE acceptance impact:** M10 renewal alerts.

### F-M14: API (JWT) sign-ins and single failed logins are not audited
- **ID:** F-M14 (M15-001) **Module:** M15 / accounts **Severity:** MEDIUM **Evidence:** STATIC
- **Actual:** `auth.login` is recorded from Django's `user_logged_in` signal (session logins). `POST /api/v1/auth/token/` and `/refresh/` never fire it; individual failed logins are not audited (only lockout). Local audit DB had no `auth.*` rows for QA users created through the ORM; browser logins in this audit do produce `auth.login` rows.
- **File:line:** `src/apps/accounts/signals.py:14-32`; `src/apps/accounts/api.py:16-23`.
- **Fix:** override `TokenObtain.post` to `audit.record("auth.login"/"auth.login_failed")`. **Test:** token obtain audited. **Security impact:** API account takeover untraceable. **Browser evidence:** n/a. **Business impact:** weak security audit. **Database impact:** missing rows. **API/URL:** `/api/v1/auth/token/`. **HPE acceptance impact:** M15 security events.

### F-M15: Platform audit page shows every organization's operational audit rows
- **ID:** F-M15 (M15-002) **Module:** M15 / platform admin **Severity:** MEDIUM (policy decision) **Evidence:** STATIC + RUNTIME (the platform organization page's "Recent activity" showed `qr.generated` for a tenant)
- **Actual:** `PlatformAuditView` lists all orgs' rows (including `target_repr` such as asset names, WO numbers) with only action/q filters; page subtitle and docstring say "platform and security events"; viewing is not itself audited.
- **File:line:** `src/apps/platform_admin/views.py:127-137`. **Fix:** restrict to `organization.*`, `auth.*`, `user.*`, `platform.*`, hide operational `target_repr`, audit the access. **Test:** platform audit excludes operational rows. **Security impact:** tenant confidentiality vs the Super Admin; needs a Team Lead decision. **Business impact:** customer trust. **Browser evidence:** n/a. **Database impact:** none. **API/URL:** `/platform/audit/`. **HPE acceptance impact:** tenancy story.

### F-M16: The shell's organization-switch dropdown does nothing (blocked by the CSP)
- **ID:** F-M16 (SEC-001) **Module:** UI / CSP **Severity:** MEDIUM (functional) **Evidence:** RUNTIME
- **Actual:** `templates/shell.html:48` uses `onchange="this.form.submit()"`. The CSP is `script-src 'self' 'nonce-...'` (no `unsafe-inline`), so the browser refuses the handler. A multi-org user (I invited an Alpha technician into Beta to test) selecting the other org in the topbar sees no change; console: "Refused to execute inline event handler because it violates the following Content Security Policy directive". Users can still switch via `/app/choose-organization/`.
- **File:line:** `src/templates/shell.html:48`; `src/apps/core/csp.py:190`; no handler in `src/static/js/app.js`.
- **Fix:** `data-autosubmit` + delegated handler (or a submit button). **Test:** template lint failing on `on[a-z]+=`, plus a browser test. **Security impact:** none. **Business impact:** multi-org users (consultants) stuck. **Browser evidence:** `UI` line in `evidence/browser_results.jsonl`. **Database impact:** none. **API/URL:** `POST /app/switch-organization/`. **HPE acceptance impact:** low.

### F-M17: Org Admin can grant itself every permission and can modify an Owner
- **ID:** F-M17 (SEC-002) **Module:** RBAC / tenancy **Severity:** MEDIUM **Evidence:** RUNTIME
- **Actual:** an Organization Admin (holds `role.*`, `user.*`) created a role with all 94 permissions via `POST /api/v1/roles/` (201), assigned it to itself via `PATCH /api/v1/members/{id}/` (200) and `GET /api/v1/audit-logs/export/` then returned 200 (Admin template has no `audit.export`). The Admin also edited the Owner's membership record (200). Owner role grant/revoke is correctly Owner-only; last-owner guard holds. (State restored after the test.)
- **File:line:** `src/apps/rbac/services.py:279-326`; `src/apps/tenancy/services.py:196-259`.
- **Fix:** record "Admin is trusted" as a decision, or enforce "grant only what you hold" and "only an Owner may modify/deactivate an Owner". **Test:** admin cannot grant what it lacks / cannot touch an Owner. **Security impact:** horizontal-to-vertical escalation inside one tenant; no cross-tenant effect. **Business impact:** weakens separation of duties. **Browser evidence:** `RBAC` lines in `evidence/browser_results.jsonl`. **Database impact:** role rows. **API/URL:** `/api/v1/roles/`, `/api/v1/members/{id}/`. **HPE acceptance impact:** RBAC gate (document or fix).

### F-M18: Migrate-on-start conflicts with the least-privilege DB role design
- **ID:** F-M18 (DEP-001) **Module:** Deployment **Severity:** MEDIUM **Evidence:** STATIC
- **Actual:** `scripts/render_start.py:21-22` runs `manage.py migrate` at every boot with the same `DATABASE_URL` as web/worker (`RUN_MIGRATIONS_ON_START=true` in `render.yaml`). Once `harden_db_roles.py` is applied (app role without DDL) the service crash-loops on any new migration; to keep booting the app role must remain owner (un-hardened). Direct dependency of F-H02.
- **Fix:** run migrations as a pre-deploy step with a migrator URL; keep the runtime on the app role. **Test:** deployment script test. **Security impact:** see F-H02. **Business impact:** deploys fail or hardening never lands. **Browser evidence:** n/a. **Database impact:** n/a. **API/URL:** n/a. **HPE acceptance impact:** deployment/security hardening.

### F-M19: Concurrent zone re-parenting can create a cycle
- **ID:** F-M19 (M01-1) **Module:** M01 **Severity:** MEDIUM **Evidence:** STATIC (race not reproduced; single-request cycle prevention verified in the browser)
- **Actual:** `validate_zone_parent`/`update_zone` take no lock (M03 uses advisory + row locks). Two opposite moves can both pass the ancestor walk and commit a cycle; no DB CHECK. No M01 concurrency test exists.
- **File:line:** `src/apps/sites/services.py:166-250`. **Fix:** per-site advisory lock; add `parent <> id` CHECK. **Test:** real-thread opposing-move test like `tests/test_m09_concurrency.py`. **Business impact:** unreachable locations. **Security impact:** none. **Browser evidence:** single-user cycle attempts rejected (UI list excludes descendants, crafted POST rejected). **Database impact:** `sites_zone.parent_id` cycle. **API/URL:** `PATCH /api/v1/zones/{id}/`. **HPE acceptance impact:** low.

### F-M20: Tenant isolation has no database-level backstop
- **ID:** F-M20 (DB-1) **Module:** database **Severity:** MEDIUM (defence in depth) **Evidence:** STATIC (probe query found 0 cross-tenant rows)
- **Actual:** all 211 FKs are single-column; no composite `(id, organization_id)` FK or trigger; `rbac_membershiprole` and `rbac_rolepermission` carry no `organization_id`. Isolation relies on the fail-closed `TenantManager` and service checks (which attack tests show hold).
- **Fix:** composite FKs on the highest-risk edges or a scheduled cross-tenant verifier; CI check running the probe SQL. **Test:** CI probe. **Security impact:** a future service bug or script could create cross-tenant rows silently. **Business impact:** low today. **Browser evidence:** n/a. **Database impact:** see above. **API/URL:** n/a. **HPE acceptance impact:** none (defence in depth).

---

## C. LOW (compact)

| ID | Module | Evid. | Location | Behaviour | Fix / regression test |
|---|---|---|---|---|---|
| L01 | M01 | STATIC | `sites/services.py:103-119,253-273` | Deactivate site vs concurrent asset create unlocked (M01-2) | `select_for_update` on site; concurrent test |
| L02 | M01 | STATIC | `sites/models.py:64` | No self-parent CHECK on `sites_zone` (M01-3) | CHECK `parent<>id`; IntegrityError test |
| L03 | M01 | STATIC | `sites/services.py:306-313` | Calendar rejects end<=start so overnight shifts cannot be modelled (M01-4) | allow overnight window; 22:00-06:00 test |
| L04 | M02 | STATIC | `core/uploads.py:20-21` | `.docx/.xlsx` accept any zip; `add_document` allowed on terminal assets, `remove_document` not (M02-3) | inspect OOXML entries; terminal check |
| L05 | M02 | STATIC | `assets/models.py:187-190` | Meter monotonicity only in service (DB only `>=0`) (M02-4) | optional constraint trigger; concurrent readings test |
| L06 | M03 | STATIC | `assets/hierarchy.py:93-164` | No atomic `replace_component`; replacement history only in audit; `part_number` free text (M03-2) | add replace op; test |
| L07 | M03 | STATIC | `assets/hierarchy.py:132-164` | update/remove component read unlocked state (M03-3) | lock; M03 concurrency test (none exists) |
| L08 | DB | STATIC | `assets/models.py:80-92`, `inventory/models.py:241` | History/ledger tables append-only via ORM only (DB-2); see F-H02 | triggers; raw UPDATE test |
| L09 | DB | STATIC | models | No CHECK on status columns; two redundant PositiveInteger checks (DB-5) | optional CHECKs |
| L10 | M04 | STATIC | `maintenance/services.py:422` | Cancelled PM WO not regenerated; automated generation does not wait for the previous cycle (M04-03) | surface cancelled/overdue cycle |
| L11 | M04 | STATIC | `maintenance/services.py:529`, `config/api_aliases.py:72` | Scheduler failures only `last_error`; alias `POST /generate-work-orders/` runs unattributed (M04-04) | notify planners; audit alias |
| L12 | M04 | STATIC | `maintenance/selectors.py:94` etc. | N+1 in due list/API filter/`_planners` (M04-05) | annotate/batch |
| L13 | M04 | STATIC | `assets/services.py:385` | Monotonic meter readings: a mistyped high reading cannot be corrected; no rollover (M04-06) | supervised correction action |
| L14 | M06 | STATIC+RUNTIME | `workorders/services.py:401-418` | Labor: no per-day cap/overlap/duplicate guard (observed two identical 1.5 h rows after repeated submit), accepts tomorrow, no void (M06-01) | daily cap, dup detection, void |
| L15 | M06 | STATIC | `workorders/services.py:167-182` | Technician overlap check is read-then-write (no lock) (M06-02). Overlap detection itself works (RUNTIME: 409 `technician_conflict`) | lock membership row |
| L16 | M06 | STATIC | `workorders/services.py:209-223` | Closure "evidence" = any attachment; open findings do not block closure (D-061); none for PREVENTIVE/INSPECTION (M06-03) | decide policy |
| L17 | M06 | STATIC | `workorders/api_views.py:45` | N+1 `total_hours` per row (M06-04) | annotate Sum |
| L18 | M08 | STATIC | `checklists/services.py:482-520,599` | Answer audit records counts not before/after; a finding with `item=None` does not satisfy an exception (M08-01) | audit values |
| L19 | M08 | STATIC | `checklists/services.py:321` | Newly activated required template applies retroactively to in-flight WOs (M08-02; see F-M04) | effective-from |
| L20 | M08 | STATIC | `checklists/services.py:270` | `activate_template` sets old version INACTIVE directly (bypasses `apply`); no reactivation path (M08-03) | add transition |
| L21 | M08 | STATIC | `checklists/api_views.py:157,162` | Finding description/notes unbounded in API (M08-04) | max_length |
| L22 | M08 | STATIC | checklists | Standalone inspection not assignment-scoped (M08-05) | scope |
| L23 | M09 | STATIC | `inventory/services.py:709-725,549-557` | Possible deadlock in `_wind_down` lock order (M09-002) | pre-lock balances |
| L24 | M09 | STATIC | `inventory/services.py:717-725` | Cancel audit says `part_line.reconciled` though status not RECONCILED (M09-003) | derive action from final status |
| L25 | M09 | STATIC | `inventory/services.py:317-403` | receive/adjust/transfer have no idempotency key (double post) (M09-004) | optional token |
| L26 | M10 | STATIC | `contracts/models.py:78`, `services.py:203,511` | Expiry state/alerts use server-local `date.today()` not site timezone (M10-002) | site date |
| L27 | M10 | STATIC | `contracts/services.py:129-147` | Overlap rule only in service (no exclusion constraint) (M10-003) | btree_gist EXCLUDE |
| L28 | M11 | STATIC | `sla/services.py:624-691` | Acknowledged breach still escalates (M11-002) | decide policy |
| L29 | M11 | STATIC | `sla/services.py:361-414` | `_meet` uses stale due while PAUSED -> spurious MET_LATE (M11-003) | extend due by pause |
| L30 | M11 | STATIC | `sla/services.py:361-485` | pause/resume/reopen/cancel/retarget write only `SLAEvent`, no `audit.record` (M11-004) | audit them |
| L31 | M12 | STATIC | `identification/views.py:154-170` | `GET /app/s/<token>/` writes active-org to session and a ScanEvent (state-changing GET) (M12-002/SEC-010) | POST to switch |
| L32 | M12 | RUNTIME | `static/js/qr_scan.js` | Synthetic-camera decode of a small on-screen QR (360 px) did not trigger in 16 s while a 420 px QR resolved immediately; decoder is size-sensitive | test with real phone camera; larger frame guidance |
| L33 | M13 | STATIC | `portal/services.py:194-205` | Staff roles added later to a portal member are not re-checked (M13-002) | recheck |
| L34 | M14 | STATIC | `dashboards/metrics.py:65-67,191,206-208` | MTBF window counts full 24 h of the last day and pre-existence time (M14-002) | clip to now |
| L35 | M14 | STATIC | `dashboards/metrics.py:92-95,233-237` | UTC day windows vs site-local PM due date (M14-003) | site tz |
| L36 | M15 | STATIC | `files/views.py:16-37` | Attachment downloads not audited (M15-003) | `attachment.downloaded` |
| L37 | M15 | STATIC | `audit/evidence.py:334-373` | Evidence ZIP built fully in memory (~300 MB peak for 100 MB of files) (M15-004) | stream/spool |
| L38 | M15 | STATIC | `audit/exports.py:31-33` | XLSX export raises on control chars; negative numbers prefixed with `'` (M15-005) | strip control chars |
| L39 | Celery | STATIC | `notifications/tasks.py:11-25` | Retry re-sends to all recipients; no delivery flag (CEL-003) | task per notification |
| L40 | Celery | STATIC | `scripts/render_start.py` | `--pool=solo` does not enforce time limits; beat tasks have no `expires` (CEL-004) | threads pool / expires |
| L41 | Config | STATIC | `config/settings/prod.py` | No guard for console email backend or localhost `SITE_BASE_URL` in prod (CEL-005) | fail fast |
| L42 | Deploy | RUNTIME | `Dockerfile:21-22`, `prod.py` | Plain-HTTP `/health/live/` answers 301 under prod settings (observed under gunicorn): the image HEALTHCHECK follows to https and fails (DEP-003) | `SECURE_REDIRECT_EXEMPT=[r"^health/"]` |
| L43 | Deploy | STATIC | `Dockerfile:25`, `render_start.py:35`, `deploy/nginx/default.conf:25-26` | gunicorn `--forwarded-allow-ips "*"`; nginx forwards client `X-Forwarded-Proto`; `TRUSTED_PROXY_COUNT=1` on Render unverified (DEP-004) | restrict to proxy |
| L44 | Deploy | STATIC | `.github/workflows/ci.yml` | CI uses locmem/eager Celery so Redis/Celery behaviour is untested; actions not SHA-pinned; no `permissions:` block; no docker run/scan (DEP-005) | Redis smoke job |
| L45 | Deploy | STATIC | `.github/workflows/keepalive.yml` | Render Free sleeps; beat/worker stop; keepalive cron best-effort (DEP-006) | always-on instance |
| L46 | Security | STATIC | `tenancy/services.py:196-204,127-133` | `update_member` renames the global User row; existing accounts auto-activated into an inviting org (D-006) (SEC-003; RUNTIME: Beta owner added an Alpha user to Beta with status ACTIVE, no consent) | consent / scope |
| L47 | Security | STATIC | `config/settings/base.py:276-281` | DRF throttle ident uses client `X-Forwarded-For` (no `NUM_PROXIES`); per-IP only (SEC-004) | `NUM_PROXIES`; per-username throttle |
| L48 | Security | STATIC | `config/settings/base.py:282-288` | JWT refresh tokens not blacklistable (SEC-006) | add blacklist app + logout |
| L49 | Security | STATIC | `accounts/services.py:169-183` | Activation link activates all of a user's INVITED memberships (SEC-007) | scope to inviting org |
| L50 | Security | STATIC | `core/uploads.py:287-323`, `deploy/nginx/default.conf:14` | Size checked after the body is received; the 12 MB cap exists only in nginx (not on Render) (SEC-008) | request-size cap in app |
| L51 | Security | STATIC | `files/access.py:9-11`, `incidents/apps.py:16`, `portal/apps.py:23` | Two checkers registered for `incidents.servicerequest`; correctness depends on app order (SEC-009) | `register` raises on duplicate |
| L52 | Security | STATIC | `core/csp.py:190-217` | `style-src 'unsafe-inline'`; Swagger docs `unsafe-inline` + CDN without SRI (authenticated only) (SEC-011) | self-host Swagger |
| L53 | API | RUNTIME | `api_sweep.json` | `findings/`, `inspections/`, `work-order-parts/` list endpoints return 200 with an empty list for principals that lack permission (others return 403); GET on POST-only action routes returns 403 not 405 | consistent gating |
| L54 | API | RUNTIME | `/api/v1/assets/?status=BOGUS` | Unknown filter values/orderings are silently ignored (200, 0 rows / default order) | validate filter values |
| L55 | API | RUNTIME | `config/api_aliases.py` | 72 HPE-named alias routes (`/stock/`, `/slas/`, `/breaches/`, `/client/requests/`, `/issue/` ...) are intentionally absent from OpenAPI; canonical routes documented (see INTENTIONAL I06) | document aliases as deprecated pointers |
| L56 | UX | RUNTIME | UI | Times render in UTC (e.g. PM window 08:00 IST shows "02:30"); Service Manager can approve a request but lacks `work_order.create`, the detail page says "An approved request can create one" with no hint who can (observation) | show site-local time; hand-off hint |
| L57 | Process | STATIC | `tests/` | No automated browser (Playwright) tests in the suite or CI; no concurrency tests for M01-M03; HPE browser acceptance rests on manual runs | add Playwright smoke + concurrency tests |

## D. COSMETIC

| ID | Location | Behaviour |
|---|---|---|
| C01 | `platform_admin/api_views.py:36-39` | Bare `except Exception` converted to NotFound hides real DB errors (SEC-012) |
| C02 | `identification/views.py:119-126` | Label `Content-Disposition` interpolates `asset_tag` without quoting helper (SEC-013) |
| C03 | `Dockerfile`, `requirements.lock`, `celery.py:4` | No `.dockerignore`, no hash pinning, `celery.py` defaults to dev settings (DEP-007) |
| C04 | asset form | Help text "coverage tracking arrives with the warranty module" is stale (M10 exists) |

## E. INTENTIONAL (confirmed deliberate, documented)

| ID | Item | Source |
|---|---|---|
| I01 | SLA timers use 24/7 wall-clock minutes; M01 calendars not consulted | D-044/D-047 |
| I02 | PM lifecycle is derived from the WO state (not a `StateMachine` object); VERIFIED = WO CLOSED; missed cycles collapse into one catch-up WO | D-043/D-045 |
| I03 | No segregation-of-duties between triage/approve/confirm/close; Operations Manager holds plan..close on the same WO | M05-04, M06-05 |
| I04 | Technician workspace has no offline/PWA (HPE lists none) | M07-01 |
| I05 | `ClosureApproval`, `TechnicianProfile`, `Shift`, `WorkOrderAssignment`, `Incident`, `Warranty`, `ServiceContract` entities implemented as functional equivalents; `IntegrationEvent` deliberately not built (HPE defines no consumer) | D-054/D-061 |
| I06 | HPE-named alias API routes hidden from OpenAPI | `config/api_aliases.py` docstring |
| I07 | Revoked/replaced QR shows the asset with a "do not rely" warning to authorised users; API answers 410 `REVOKED`; foreign/unknown stay 404 | M12 design |
| I08 | Super Admin is redirected to `/platform/` from every `/app/` URL and gets 403 on tenant APIs | tenancy design |
| I09 | Stock `adjust` requires no second approval and no costing | D-046 |
| I10 | Existing users are auto-activated when invited by another org | D-006 (see L46) |
| I11 | Direct ACTIVE -> OUT_OF_SERVICE not allowed (needs UNDER_MAINTENANCE first) | D-027 |

## F. UNVERIFIED (cannot be established here)

| ID | Item | Why |
|---|---|---|
| U01 | Live Supabase role/privilege state, admin password rotation, `harden_db_roles.py` applied? | no production access (see F-H02) |
| U02 | Docker image build and `docker compose` stack | no Docker daemon in the audit sandbox; Dockerfile/compose/nginx reviewed statically |
| U03 | Python 3.12 (Dockerfile base) | audit ran on Python 3.11.15; suite is green there |
| U04 | Chrome/Edge/Firefox/Safari matrix | only Chromium 1194 available |
| U05 | Physical phone camera scan | only a synthetic capture device was available |
| U06 | SMTP delivery through Brevo; Render health-check handling of 301 | no external network/credentials |
| U07 | Load/performance/p95 | out of scope for the sandbox |
| U08 | Race conditions F-M19, L01, L07, L15, L23 | statically identified, not reproduced |
| U09 | htmx history cache storing tenant pages in localStorage after logout on shared devices (SEC-015) | not exercised in a browser |
| U10 | Whether HPE expects asset financial fields (purchase cost/vendor/currency): none exist (M02-5); digest lists none | requirement silent |

---

## G. Corrections to earlier repository claims (documentation vs reality)

- `docs/FINAL_RECONCILIATION_REPORT.md` section 6 says "one single uninterrupted green run ... NOT achieved". **This audit achieved it:** 746 passed, 0 failed, 356 s, fresh test DB, PostgreSQL 16 (and again with coverage: 746 passed, 93 % line coverage).
- `docs/MODULE_STATUS.md` still lists M01-M08 browser acceptance as outstanding; this audit performed it (see `M01_M15_BROWSER_ACCEPTANCE.md`).
- D-050 says QR rate limiting is "NOT implemented"; it is implemented and verified (HTTP 429 after 15 failed scans per 10 min, and a throttled user is also refused valid tokens).
- `docs/FINAL_BROWSER_ACCEPTANCE_REPORT.md` stated the camera path NOT VERIFIED; a synthetic-device run passed here (L32 caveat).
