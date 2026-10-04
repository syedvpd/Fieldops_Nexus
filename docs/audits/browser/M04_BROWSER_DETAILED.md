# M04 browser acceptance - detailed (Preventive Maintenance (plans, schedules, generation))

**Batch 1 of the browser acceptance (M01-M04).** Real Chromium (Playwright) against the running application (DEBUG off, CSP on, PostgreSQL `fieldops_browser_qa`, Redis, Celery worker + beat). Every check below was performed in the browser (or by a real in-page request carrying the session cookie and CSRF token) and the database state was read back with SQL; an HTTP 200 alone was never accepted as evidence. No production code was modified.

**Result: M04: 557/562 browser checks PASS** (1 FAIL, 3 PARTIAL, 1 UNVERIFIED; 1 NOT APPLICABLE excluded; 1 superseded harness lines excluded). **Module status: FAIL (High defect).**

Roles driven: owner, admin, ops, supervisor, assets, planner, tech (technician 1), tech2, stores, service, auditor, client (all Alpha) and betaowner (tenant Beta). Viewports: 1920x1080, 1440x900, 1024x768, 390x844.

Matrix columns used by the scripts: FEATURE / PAGE / ROLE / ACTION / EXPECTED / ACTUAL / DATABASE / API-HTMX / AUDIT / STATUS; the full matrix for this module is in `evidence/M04_run_plans.json`, `evidence/M04_run_schedules_generation_reminders_rbac_tenant_responsive.json`, `evidence/M04_run_notification_bell.json`, `evidence/M04_run_anonymous_session.json`.

## 1. Pages tested

Discovered by a crawl of the module (owner): 9 pages; visited in the test runs: 9/9.

| Page / URL (normalised) | Discovered by crawl | Browser visits |
|---|---|---|
| `/app/maintenance/due/` | yes | 29 |
| `/app/maintenance/due/?page` | no (reached by test) | 5 |
| `/app/maintenance/due/?site` | no (reached by test) | 2 |
| `/app/maintenance/due/?state` | no (reached by test) | 4 |
| `/app/maintenance/history/` | yes | 23 |
| `/app/maintenance/history/?page` | no (reached by test) | 1 |
| `/app/maintenance/history/?plan` | no (reached by test) | 4 |
| `/app/maintenance/plans/` | yes | 31 |
| `/app/maintenance/plans/?active` | no (reached by test) | 2 |
| `/app/maintenance/plans/?active&page` | no (reached by test) | 2 |
| `/app/maintenance/plans/?active&q` | no (reached by test) | 2 |
| `/app/maintenance/plans/?active&q&site` | no (reached by test) | 2 |
| `/app/maintenance/plans/?page` | no (reached by test) | 6 |
| `/app/maintenance/plans/?page&site` | no (reached by test) | 1 |
| `/app/maintenance/plans/?q` | no (reached by test) | 9 |
| `/app/maintenance/plans/?site` | no (reached by test) | 4 |
| `/app/maintenance/plans/new/` | yes | 51 |
| `/app/maintenance/plans/new/?asset` | no (reached by test) | 2 |
| `/app/maintenance/plans/{id}/` | yes | 99 |
| `/app/maintenance/plans/{id}/edit/` | yes | 22 |
| `/app/maintenance/plans/{id}/schedules/new/` | yes | 105 |
| `/app/maintenance/schedules/{id}/` | yes | 58 |
| `/app/maintenance/schedules/{id}/edit/` | yes | 27 |

Other URLs the tests visited (negative probes, redirects, API): `/accounts/login/`, `/accounts/login/?next`, `/app/`, `/app/assets/{id}/`, `/app/assets/{id}/?tab`, `/app/notifications/`, `/app/portal/`, `/app/work-orders/{id}/`

## 2. Buttons / links / actions

Discovered controls: 7 buttons (7 clicked/posted), 7 distinct links (7 followed), 7 POST endpoints (7 exercised), 3 GET filter forms (3 used), 0 HTMX endpoints (0 exercised).

State-changing requests issued by the browser (normalised path -> count): `/app/maintenance/plans/{id}/schedules/new/` x103, `/app/maintenance/plans/new/` x44, `/app/maintenance/schedules/{id}/generate/` x33, `/app/maintenance/plans/{id}/active/` x25, `/app/maintenance/schedules/{id}/edit/` x24, `/app/maintenance/plans/{id}/edit/` x19, `/app/maintenance/schedules/{id}/disable/` x16, `/app/maintenance/schedules/{id}/enable/` x6

All discovered controls were exercised.

## 3. Forms

10 distinct forms discovered (owner view); every field of every form was filled, left blank and given invalid/boundary values in section 4.

| Form (action) | Method | Fields (non-hidden) | Exercised |
|---|---|---|---|
| `/app/maintenance/plans/ (self)` | GET | q, site, active | yes |
| `/app/maintenance/plans/new/ (self)` | POST | asset, name, description, priority, estimated_hours, checklist_key | yes |
| `/app/maintenance/plans/{id}/active/` | POST | (button only) | yes |
| `/app/maintenance/schedules/{id}/generate/` | POST | (button only) | yes |
| `/app/maintenance/schedules/{id}/disable/` | POST | (button only) | yes |
| `/app/maintenance/plans/{id}/edit/ (self)` | POST | name, description, priority, estimated_hours, checklist_key | yes |
| `/app/maintenance/plans/{id}/schedules/new/ (self)` | POST | trigger_type, frequency, interval_count, start_date, meter, interval_value, start_value, lead_days, window_start_time, window_hours, remind… | yes |
| `/app/maintenance/schedules/{id}/edit/ (self)` | POST | frequency, interval_count, start_date, meter, interval_value, start_value, lead_days, window_start_time, window_hours, reminder_days | yes |
| `/app/maintenance/due/ (self)` | GET | state, site | yes |
| `/app/maintenance/history/ (self)` | GET | plan | yes |

## 4. Validation (client + server)

84/85 validation, boundary, duplicate, forged-input and XSS checks PASS. Forms are `novalidate`; constraints that the browser would block were removed in the page (or the request forged from the page) so that the SERVER rules were exercised, and the matching client hint (maxlength/required) was asserted separately.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | XSS in search term is escaped | owner | PASS | inert -> ok |
| 2 | Validation: name required | owner | PASS | 400/403/404 + inline error, nothing saved ('required') -> http=400 rows 41->41 This field is required. |
| 3 | Validation: name whitespace only | owner | PASS | 400/403/404 + inline error, nothing saved ('required') -> http=400 rows 41->41 This field is required. |
| 4 | Validation: name 2 chars (min 3) | owner | PASS | 400/403/404 + inline error, nothing saved ('3 characters') -> http=400 rows 41->41 Name must have at least 3 characters. |
| 5 | Validation: name 151 chars (max 150) | owner | PASS | 400/403/404 + inline error, nothing saved ('150') -> http=400 rows 41->41 Ensure this value has at most 150 characters (it has 151). |
| 6 | Validation: duplicate name on the same asset | owner | PASS | 400/403/404 + inline error, nothing saved ('already has a plan') -> http=400 rows 41->41 This asset already has a plan with that name. |
| 7 | Validation: duplicate name, different case | owner | PASS | 400/403/404 + inline error, nothing saved ('already has a plan') -> http=400 rows 41->41 This asset already has a plan with that name. |
| 8 | Validation: duplicate name with padding | owner | PASS | 400/403/404 + inline error, nothing saved ('already has a plan') -> http=400 rows 41->41 This asset already has a plan with that name. |
| 9 | Validation: estimated hours negative | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 41->41 Ensure this value is greater than or equal to 0. |
| 10 | Validation: estimated hours text | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 41->41 Enter a number. |
| 11 | Validation: estimated hours 3 decimals | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 41->41 Ensure that there are no more than 2 decimal places. |
| 12 | Validation: estimated hours 10000 (over 6 digits) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 41->41 Ensure that there are no more than 6 digits in total. |
| 13 | Validation: asset required | owner | PASS | 400/403/404 + inline error, nothing saved ('required') -> http=400 rows 41->41 This field is required. |
| 14 | Boundary: 3-character name accepted | owner | PASS | created -> True |
| 15 | Boundary: 150-character name accepted | owner | PASS | created -> True |
| 16 | Boundary: estimated hours = 0 | owner | PARTIAL | accepted, or refused with a clear message consistent with the form -> http=400; created=False; message='Estimated hours must be a positive number (max 3 decimals).' |
| 17 | Boundary: estimated hours 9999.99 accepted | owner | PASS | created -> True |
| 18 | Stored XSS in plan name is escaped (list + detail) | owner | PASS | inert -> ok |
| 19 | Validation: asset of another tenant (forged) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 45->45 |
| 20 | Validation: non-existent asset id (forged) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 45->45 |
| 21 | Validation: malformed asset id (forged) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 45->45 |
| 22 | Validation: retired asset (forged) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 45->45 |
| 23 | Validation: invalid priority (forged) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 45->45 |
| 24 | Validation: unknown checklist key (forged) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 45->45 |
| 25 | Validation: checklist key of another tenant (forged) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 45->45 |
| 26 | Edit: duplicate name on the same asset refused | owner | PASS | refused -> This asset already has a plan with that name. |
| 27 | Edit: 2-character name refused | owner | PASS | refused -> Name must have at least 3 characters. |
| 28 | Forged 'asset' on edit is ignored (asset cannot be changed) | owner | PASS | asset unchanged -> True |
| 29 | Validation: frequency missing | owner | PASS | 400 + message, nothing saved ('frequency') -> http=400 rows 0->0 Choose a frequency. |
| 30 | Validation: start date missing | owner | PASS | 400 + message, nothing saved ('start date') -> http=400 rows 0->0 A start date is required. |
| 31 | Validation: start date not a date | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Enter a valid date. |
| 32 | Validation: start date impossible 2026-02-30 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Enter a valid date. |
| 33 | Validation: interval missing | owner | PASS | 400 + message, nothing saved ('interval') -> http=400 rows 0->0 The interval must be a whole number. |
| 34 | Validation: interval 0 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is greater than or equal to 1. |
| 35 | Validation: interval -1 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is greater than or equal to 1. |
| 36 | Validation: interval 1001 (max 1000) | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is less than or equal to 1000. |
| 37 | Validation: interval 1.5 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Enter a whole number. |
| 38 | Validation: interval abc | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Enter a whole number. |
| 39 | Validation: interval 99999999999 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is less than or equal to 1000. |
| 40 | Validation: lead days 61 (max 60) | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is less than or equal to 60. |
| 41 | Validation: lead days -1 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is greater than or equal to 0. |
| 42 | Validation: window hours 0 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is greater than or equal to 1. |
| 43 | Validation: window hours 73 (max 72) | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is less than or equal to 72. |
| 44 | Validation: reminder days 61 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is less than or equal to 60. |
| 45 | Validation: reminder days -1 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is greater than or equal to 0. |
| 46 | Validation: window start time invalid | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Enter a valid time. |
| 47 | Validation: window start time missing | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 This field is required. |
| 48 | Validation: lead days abc | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Enter a whole number. |
| 49 | Validation: window hours 99999999999 | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Ensure this value is less than or equal to 72. |
| 50 | Validation: meter-based without a meter | owner | PASS | 400 + message, nothing saved -> http=400 rows 0->0 Meter not found in this organization. |
| 51 | Boundary accepted: interval 1000 + lead 60 + window 72h + reminder 60 | owner | PASS | created -> rows 0->1 |
| 52 | Boundary accepted: interval 1 + lead 0 + window 1h | owner | PASS | created -> rows 1->2 |
| 53 | Boundary accepted: window start 00:00 | owner | PASS | created -> rows 2->3 |
| 54 | Boundary accepted: window start 23:59 | owner | PASS | created -> rows 3->4 |
| 55 | Duplicate schedule (same frequency + interval on the plan) refused | owner | PASS | refused 'identical schedule' -> The plan already has an identical schedule. |
| 56 | Crafted POST: meter of another asset (forged) rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 57 | Crafted POST: meter of another tenant (forged) rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 58 | Crafted POST: unknown trigger type (forged) rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 59 | Crafted POST: unknown frequency (forged) rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 60 | Validation: identical meter schedule (same meter + interval) | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 The plan already has an identical schedule. |
| 61 | Validation: interval 0 | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 Interval must be a positive number (max 3 decimals). |
| 62 | Validation: interval negative | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 Ensure this value is greater than or equal to 0. |
| 63 | Validation: interval missing | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 Interval is required. |
| 64 | Validation: interval text | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 Enter a number. |
| 65 | Validation: interval 4 decimals | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 Ensure that there are no more than 3 decimal places. |
| 66 | Validation: interval 1e12 | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 Interval must be a positive number (max 3 decimals). |
| 67 | Validation: start value negative | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 Ensure this value is greater than or equal to 0. |
| 68 | Validation: start value text | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 Enter a number. |
| 69 | Validation: meter not chosen | owner | PASS | 400 + message, nothing saved -> http=400 rows 1->1 Meter not found in this organization. |
| 70 | Boundary: interval 0.001 accepted | owner | PASS | created -> 2 |
| 71 | Boundary: interval 999999999999.999 accepted | owner | PASS | created -> 3 |
| 72 | Edit validation: interval 0 refused, schedule unchanged | owner | PASS | refused -> Ensure this value is greater than or equal to 1. |
| 73 | Edit validation: interval 1001 refused, schedule unchanged | owner | PASS | refused -> Ensure this value is less than or equal to 1000. |
| 74 | Edit validation: lead days 61 refused, schedule unchanged | owner | PASS | refused -> Ensure this value is less than or equal to 60. |
| 75 | Edit validation: window hours 0 refused, schedule unchanged | owner | PASS | refused -> Ensure this value is greater than or equal to 1. |
| 76 | Edit validation: start date missing refused, schedule unchanged | owner | PASS | refused -> A start date is required. |
| 77 | Edit validation: frequency missing refused, schedule unchanged | owner | PASS | refused -> Choose a frequency. |
| 78 | Edit into an identical sibling schedule refused | owner | PASS | refused -> The plan already has an identical schedule. |
| 79 | Generate on a disabled schedule (forged POST) creates nothing | owner | PASS | no WO -> http=200 |
| 80 | WO description names the plan/recurrence and the required checklist (M08 contract) | owner | PASS | plan + checklist -> Preventive maintenance generated from plan 'Gen plan 20307' (every 1 month). Due date: 202 |
| 81 | Generate now again while the previous WO is open: refused ('previous cycle's work order is still open'), no d… | owner | PASS | refused -> The previous cycle's work order is still open: finish it before generating the next occurr |
| 82 | Beta schedule with an Alpha meter id is rejected | betaowner | PASS | rejected -> http=400 |
| 83 | Anonymous POST /app/maintenance/plans/new/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> /login/?next=/app/maintenance/plans/new/ |
| 84 | Anonymous POST /app/maintenance/schedules/{id}/generate/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 50-dc70-48eb-8004-10c7c208b939/generate/ |
| 85 | Anonymous POST /app/maintenance/plans/{id}/active/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 1e71-e597-489d-8181-98b9ec51f4aa/active/ |

## 5. RBAC

240/240 RBAC checks PASS across 23 distinct checks x up to 12 roles. For every role the expected outcome is derived from the role's real permission set in the database (membership -> role -> permission); the browser then proves (a) the control is shown iff permitted, (b) the direct URL answers 200 iff permitted else 403/404, (c) a real forged POST is refused with the database unchanged when denied and succeeds with the expected state change when allowed.

| Check (expected outcome derived from the role's DB permission set) | owner | admin | ops | supervisor | assets | planner | tech | tech2 | stores | service | auditor | client |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RBAC plans list access follows maintenance.view | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC due list access follows maintenance.view | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC history access follows maintenance.view | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC plan detail access follows maintenance.view | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC schedule detail access follows maintenance.view | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC nav 'Maintenance plans' iff maintenance.view | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC 'New plan' button iff maintenance.create | ok | ok | ok | ok | - | ok | - | - | - | - | ok | - |
| RBAC plan Edit / Disable iff maintenance.update | ok | ok | ok | ok | - | ok | - | - | - | - | ok | - |
| RBAC 'Add schedule' iff maintenance.create | ok | ok | ok | ok | - | ok | - | - | - | - | ok | - |
| RBAC 'Generate now' iff maintenance.generate | ok | ok | ok | ok | - | ok | - | - | - | - | ok | - |
| RBAC schedule Disable/Enable iff maintenance.update | ok | ok | ok | ok | - | ok | - | - | - | - | ok | - |
| RBAC due-list 'Generate now' iff maintenance.generate | ok | ok | ok | ok | - | ok | - | - | - | - | ok | - |
| RBAC direct URL: new plan form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: edit plan form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: new schedule form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: edit schedule form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC create plan | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC edit plan | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC disable plan | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC create schedule | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC edit schedule | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC disable schedule | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC generate now | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |

## 6. Tenant isolation (Alpha <-> Beta, both directions)

48/48 tenant checks PASS. Beta fixtures were created through the Beta UI; Alpha fixtures through the Alpha UI. Probes cover list, search, filters, detail, edit forms, edit POSTs, status/state actions, documents/meters/relations/schedules, HTMX partials, file download, API and forged foreign ids.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Validation: asset of another tenant (forged) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 45->45 |
| 2 | Validation: checklist key of another tenant (forged) | owner | PASS | 400/403/404 + inline error, nothing saved -> http=400 rows 45->45 |
| 3 | Crafted POST: meter of another tenant (forged) rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 4 | Setup: Beta asset, plan and schedule exist (created through the Beta UI) | betaowner | PASS | rows -> ok |
| 5 | Tenant: Beta cannot open the other tenant's plan | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 6 | Tenant: Beta cannot open its plan edit form | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 7 | Tenant: Beta cannot edit it (POST) | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 8 | Tenant: Beta cannot disable it | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 9 | Tenant: Beta cannot add a schedule to it | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 10 | Tenant: Beta cannot open its schedule | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 11 | Tenant: Beta cannot open its schedule edit form | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 12 | Tenant: Beta cannot edit its schedule | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 13 | Tenant: Beta cannot disable its schedule | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 14 | Tenant: Beta cannot GENERATE work for its schedule | betaowner | PASS | 400/403/404, DB unchanged -> http=404 |
| 15 | Tenant: Beta cannot create a plan on the other tenant's asset | betaowner | PASS | 400/403/404, DB unchanged -> http=400 |
| 16 | Tenant: Alpha cannot open the other tenant's plan | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 17 | Tenant: Alpha cannot open its plan edit form | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 18 | Tenant: Alpha cannot edit it (POST) | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 19 | Tenant: Alpha cannot disable it | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 20 | Tenant: Alpha cannot add a schedule to it | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 21 | Tenant: Alpha cannot open its schedule | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 22 | Tenant: Alpha cannot open its schedule edit form | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 23 | Tenant: Alpha cannot edit its schedule | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 24 | Tenant: Alpha cannot disable its schedule | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 25 | Tenant: Alpha cannot GENERATE work for its schedule | owner | PASS | 400/403/404, DB unchanged -> http=404 |
| 26 | Tenant: Alpha cannot create a plan on the other tenant's asset | owner | PASS | 400/403/404, DB unchanged -> http=400 |
| 27 | Beta plans page shows no Alpha plans/schedules/cycles | betaowner | PASS | none -> ok |
| 28 | Beta due page shows no Alpha plans/schedules/cycles | betaowner | PASS | none -> ok |
| 29 | Beta history page shows no Alpha plans/schedules/cycles | betaowner | PASS | none -> ok |
| 30 | Beta plan search for an Alpha asset tag returns nothing | betaowner | PASS | none -> ok |
| 31 | Beta site filter with an Alpha site id returns nothing | betaowner | PASS | empty -> ok |
| 32 | Beta 'New plan' asset dropdown contains no Alpha assets | betaowner | PASS | none -> ok |
| 33 | Beta schedule form offers no Alpha meters | betaowner | PASS | none -> ['---------'] |
| 34 | API: Beta GET Alpha plan -> 404 | betaowner | PASS | 404 -> 404 |
| 35 | API: Beta maintenance-plans list has no Alpha records | betaowner | PASS | none -> 200 |
| 36 | API: Beta maintenance-schedules list has no Alpha records | betaowner | PASS | none -> 200 |
| 37 | API: Beta maintenance-cycles list has no Alpha records | betaowner | PASS | none -> 200 |
| 38 | Beta schedule with an Alpha meter id is rejected | betaowner | PASS | rejected -> http=400 |
| 39 | Anonymous GET /app/maintenance/plans/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> /127.0.0.1:8098/accounts/login/?next=/app/maintenance/plans/ |
| 40 | Anonymous GET /app/maintenance/plans/new/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> .0.0.1:8098/accounts/login/?next=/app/maintenance/plans/new/ |
| 41 | Anonymous GET /app/maintenance/plans/{id}/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> /app/maintenance/plans/ed661e71/ |
| 42 | Anonymous GET /app/maintenance/plans/{id}/edit/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> maintenance/plans/ed661e71/edit/ |
| 43 | Anonymous GET /app/maintenance/schedules/{id}/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> /maintenance/schedules/9dbb6650/ |
| 44 | Anonymous GET /app/maintenance/due/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> ://127.0.0.1:8098/accounts/login/?next=/app/maintenance/due/ |
| 45 | Anonymous GET /app/maintenance/history/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> 27.0.0.1:8098/accounts/login/?next=/app/maintenance/history/ |
| 46 | Anonymous POST /app/maintenance/plans/new/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> /login/?next=/app/maintenance/plans/new/ |
| 47 | Anonymous POST /app/maintenance/schedules/{id}/generate/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 50-dc70-48eb-8004-10c7c208b939/generate/ |
| 48 | Anonymous POST /app/maintenance/plans/{id}/active/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 1e71-e597-489d-8181-98b9ec51f4aa/active/ |

## 7. Database persistence (browser action -> SQL read-back, refresh persistence, audit)

226/228 checks that carry a database/audit read-back PASS.

| # | Feature | Db | Audit | Status |
|---|---|---|---|---|
| 1 | Page 1 shows 20 rows; data spans several pages | 38 |  | PASS |
| 2 | Search by plan name | 24 |  | PASS |
| 3 | Search by asset tag | 0 |  | PASS |
| 4 | Site filter HYD-1: exactly its plans (38) | 38 |  | PASS |
| 5 | Site filter BLR-1: exactly its plans (0) | 0 |  | PASS |
| 6 | 'Enabled' filter matches the database (36) | 36 |  | PASS |
| 7 | All pages together list every plan once | 38 |  | PASS |
| 8 | Create plan with all fields: persisted exactly, redirect to detail + success message | 8473552d\|358049f8\|Full plan 19718\|Line1 Line2 <b>x</b>\|HIGH\|4.50\|dc6f5448… | maintenance.plan_created | PASS |
| 9 | Minimal create (asset + name): defaults MEDIUM, no hours/checklist |  | maintenance.plan_created | PASS |
| 10 | Validation: name required | 41->41 |  | PASS |
| 11 | Validation: name whitespace only | 41->41 |  | PASS |
| 12 | Validation: name 2 chars (min 3) | 41->41 |  | PASS |
| 13 | Validation: name 151 chars (max 150) | 41->41 |  | PASS |
| 14 | Validation: duplicate name on the same asset | 41->41 |  | PASS |
| 15 | Validation: duplicate name, different case | 41->41 |  | PASS |
| 16 | Validation: duplicate name with padding | 41->41 |  | PASS |
| 17 | Validation: estimated hours negative | 41->41 |  | PASS |
| 18 | Validation: estimated hours text | 41->41 |  | PASS |
| 19 | Validation: estimated hours 3 decimals | 41->41 |  | PASS |
| 20 | Validation: estimated hours 10000 (over 6 digits) | 41->41 |  | PASS |
| 21 | Validation: asset required | 41->41 |  | PASS |
| 22 | Boundary: 3-character name accepted |  | maintenance.plan_created | PASS |
| 23 | Boundary: estimated hours = 0 | False |  | PARTIAL |
| 24 | Validation: asset of another tenant (forged) | 45->45 |  | PASS |
| 25 | Validation: non-existent asset id (forged) | 45->45 |  | PASS |
| 26 | Validation: malformed asset id (forged) | 45->45 |  | PASS |
| 27 | Validation: retired asset (forged) | 45->45 |  | PASS |
| 28 | Validation: invalid priority (forged) | 45->45 |  | PASS |
| 29 | Validation: unknown checklist key (forged) | 45->45 |  | PASS |
| 30 | Validation: checklist key of another tenant (forged) | 45->45 |  | PASS |
| 31 | Edit all fields persisted (name, description, priority, hours, checklist cleared) + message | Edited plan 19718\|edited\|URGENT\|9.00\| | maintenance.plan_updated | PASS |
| 32 | Audit stores before/after |  | {"name": "Full plan 19718", "priority": "HIGH", "is_ac… | PASS |
| 33 | Disable plan: persisted, banner shown |  | maintenance.plan_disabled | PASS |
| 34 | Enable plan: persisted (no confirmation needed) |  | maintenance.plan_enabled | PASS |
| 35 | A plan on a retired asset cannot be re-enabled | false |  | PASS |
| 36 | Create time-based schedule: all fields persisted, first occurrence = start date, success messa… | TIME\|MONTHLY\|1\|2026-10-14\|2\|09:30:00\|6\|3\|0\|2026-10-14\|true | maintenance.schedule_created | PASS |
| 37 | Create Day(s) schedule (every 3): stored with first due = start date | DAILY\|3\|2026-10-24 | maintenance.schedule_created | PASS |
| 38 | Create Week(s) schedule (every 2): stored with first due = start date | WEEKLY\|2\|2026-10-24 | maintenance.schedule_created | PASS |
| 39 | Create Quarter(s) schedule (every 1): stored with first due = start date | QUARTERLY\|1\|2026-10-24 | maintenance.schedule_created | PASS |
| 40 | Create Year(s) schedule (every 1): stored with first due = start date | YEARLY\|1\|2026-10-24 | maintenance.schedule_created | PASS |
| 41 | Start date in the past: schedule points to the next future occurrence (2026-10-20); no backlog… | 2\|2026-10-20 |  | PASS |
| 42 | Start date 9999-12-31 (year-overflow boundary) | 62->63 |  | PASS |
| 43 | Start date 0001-01-01 boundary | 2 |  | PASS |
| 44 | Validation: frequency missing | 0->0 |  | PASS |
| 45 | Validation: start date missing | 0->0 |  | PASS |
| 46 | Validation: start date not a date | 0->0 |  | PASS |
| 47 | Validation: start date impossible 2026-02-30 | 0->0 |  | PASS |
| 48 | Validation: interval missing | 0->0 |  | PASS |
| 49 | Validation: interval 0 | 0->0 |  | PASS |
| 50 | Validation: interval -1 | 0->0 |  | PASS |
| 51 | Validation: interval 1001 (max 1000) | 0->0 |  | PASS |
| 52 | Validation: interval 1.5 | 0->0 |  | PASS |
| 53 | Validation: interval abc | 0->0 |  | PASS |
| 54 | Validation: interval 99999999999 | 0->0 |  | PASS |
| 55 | Validation: lead days 61 (max 60) | 0->0 |  | PASS |
| 56 | Validation: lead days -1 | 0->0 |  | PASS |
| 57 | Validation: window hours 0 | 0->0 |  | PASS |
| 58 | Validation: window hours 73 (max 72) | 0->0 |  | PASS |
| 59 | Validation: reminder days 61 | 0->0 |  | PASS |
| 60 | Validation: reminder days -1 | 0->0 |  | PASS |
| 61 | Validation: window start time invalid | 0->0 |  | PASS |
| 62 | Validation: window start time missing | 0->0 |  | PASS |
| 63 | Validation: lead days abc | 0->0 |  | PASS |
| 64 | Validation: window hours 99999999999 | 0->0 |  | PASS |
| 65 | Validation: meter-based without a meter | 0->0 |  | PASS |
| 66 | Boundary accepted: interval 1000 + lead 60 + window 72h + reminder 60 | 0->1 | maintenance.schedule_created | PASS |
| 67 | Boundary accepted: interval 1 + lead 0 + window 1h | 1->2 | maintenance.schedule_created | PASS |
| 68 | Boundary accepted: window start 00:00 | 2->3 | maintenance.schedule_created | PASS |
| 69 | Boundary accepted: window start 23:59 | 3->4 | maintenance.schedule_created | PASS |
| 70 | Duplicate schedule (same frequency + interval on the plan) refused | 5->5 |  | PASS |
| 71 | Crafted POST: meter of another asset (forged) rejected | 6->6 |  | PASS |
| 72 | Crafted POST: meter of another tenant (forged) rejected | 6->6 |  | PASS |
| 73 | Crafted POST: unknown trigger type (forged) rejected | 6->6 |  | PASS |
| 74 | Crafted POST: unknown frequency (forged) rejected | 6->6 |  | PASS |
| 75 | Create meter-based schedule (every 500 h): threshold 500, no due date | METER\|b956479f\|500.000\|0.000\|1\|500.000\|- | maintenance.schedule_created | PASS |
| 76 | Validation: identical meter schedule (same meter + interval) | 1->1 |  | PASS |
| 77 | Validation: interval 0 | 1->1 |  | PASS |
| 78 | Validation: interval negative | 1->1 |  | PASS |
| 79 | Validation: interval missing | 1->1 |  | PASS |
| 80 | Validation: interval text | 1->1 |  | PASS |
| 81 | Validation: interval 4 decimals | 1->1 |  | PASS |
| 82 | Validation: interval 1e12 | 1->1 |  | PASS |
| 83 | Validation: start value negative | 1->1 |  | PASS |
| 84 | Validation: start value text | 1->1 |  | PASS |
| 85 | Validation: meter not chosen | 1->1 |  | PASS |
| 86 | Start value 100 + interval 250 -> first threshold 350 |  | maintenance.schedule_created | PASS |
| 87 | Edit window/lead/reminder only: saved and the due date is unchanged | 5\|10:15:00\|4\|2\|0\|2026-11-03 | maintenance.schedule_updated | PASS |
| 88 | Audit has before/after |  | {"meter": null, "frequency": "MONTHLY", "is_active": t… | PASS |
| 89 | Edit recurrence (every 2 weeks from +12d): next occurrence restarts at the new start date | WEEKLY\|2\|2026-10-16\|0\|2026-10-16 | maintenance.schedule_updated,maintenance.schedule_upda… | PASS |
| 90 | Edit validation: interval 0 refused, schedule unchanged | unchanged |  | PASS |
| 91 | Edit validation: interval 1001 refused, schedule unchanged | unchanged |  | PASS |
| 92 | Edit validation: lead days 61 refused, schedule unchanged | unchanged |  | PASS |
| 93 | Edit validation: window hours 0 refused, schedule unchanged | unchanged |  | PASS |
| 94 | Edit validation: start date missing refused, schedule unchanged | unchanged |  | PASS |
| 95 | Edit validation: frequency missing refused, schedule unchanged | unchanged |  | PASS |
| 96 | Disable schedule: persisted, state DISABLED, reason shown |  | maintenance.schedule_disabled | PASS |
| 97 | Generate on a disabled schedule (forged POST) creates nothing | WOs 16->16 |  | PASS |
| 98 | Enable schedule: persisted, state back to SCHEDULED |  | maintenance.schedule_enabled | PASS |
| 99 | Generate now: one cycle + one REAL work order created, success message names the WO | 5c3057f0\|0\|2026-10-04\|0\|manual\|80f02dfd | maintenance.cycle_generated | PASS |
| 100 | Work order row: PREVENTIVE / plan priority / PLANNED / source = this cycle / asset / hours / t… | WO-000017\|PREVENTIVE\|URGENT\|PLANNED\|PREVENTIVE_MAINTENANCE\|true\|7375b880\… |  | PASS |
| 101 | Planned window = schedule window (09:30 + 6 h, site time) | 2026-10-05 09:30:00 -> 2026-10-05 15:30:00 |  | PASS |
| 102 | Schedule advances to cycle 1, next due one month later | 1\|2026-11-04 |  | PASS |
| 103 | Generate now again while the previous WO is open: refused ('previous cycle's work order is sti… | WOs 17->17, cycles=1 |  | PASS |
| 104 | 5 simultaneous 'Generate now' requests: still exactly 1 cycle / no extra WO | WOs 17->17, cycles=1 |  | PASS |
| 105 | 5 simultaneous 'Generate now' requests on a fresh DUE schedule: exactly ONE work order is crea… | WOs 17->18, cycles=1 |  | PASS |
| 106 | Celery scheduler: the due schedule is generated by the worker (trigger=scheduler), exactly onc… | cycles=1 | maintenance.cycle_generated | PASS |
| 107 | Re-running the scheduler again creates no further work orders (idempotent) | 35->35 |  | PASS |
| 108 | Manual generate on a SCHEDULED schedule creates the next occurrence early | 35->36 | maintenance.schedule_created | PASS |
| 109 | SIMULATED scheduler downtime (QA DB counters rewound 7 days): schedule is DUE/overdue | QA-database counters edited to simulate missed runs (clock cannot be advanced) |  | PASS |
| 110 | Overdue catch-up: ONE work order covers the 7 missed occurrences (collapsed, '+7 missed' shown) | 10\|7 |  | PASS |
| 111 | F-H01 recheck: edit the recurrence (every 1 -> every 2 months) after cycle 0 exists, then cont… | 0\|2026-10-04 |  | FAIL |
| 112 | Generate on a schedule of a retired asset creates nothing | 38->38 |  | PASS |
| 113 | Reminder: the planner gets exactly ONE notification for the occurrence due in 3 days (reminder… | planner notifications 0->1 | maintenance.reminder_sent | PASS |
| 114 | Reminder bookkeeping: last_reminded_sequence = 0 | 0 |  | PASS |
| 115 | Due list shows every enabled schedule of enabled plans (88) across 4 page(s) | 88 |  | PASS |
| 116 | Site filter on the due list matches the database | 0 |  | PASS |
| 117 | History lists every generated cycle (39) | 39 |  | PASS |
| 118 | RBAC create plan | 0 -> 1 |  | PASS |
| 119 | RBAC edit plan |  -> owner |  | PASS |
| 120 | RBAC disable plan | t -> f |  | PASS |
| 121 | RBAC create schedule | 1 -> 2 |  | PASS |
| 122 | RBAC edit schedule | 0 -> 1 |  | PASS |
| 123 | RBAC disable schedule | t -> f |  | PASS |
| 124 | RBAC create plan | 0 -> 0 |  | PASS |
| 125 | RBAC edit plan | owner -> owner |  | PASS |
| 126 | RBAC disable plan | t -> t |  | PASS |
| 127 | RBAC create schedule | 2 -> 2 |  | PASS |
| 128 | RBAC edit schedule | 1 -> 1 |  | PASS |
| 129 | RBAC disable schedule | t -> t |  | PASS |
| 130 | RBAC create plan | 0 -> 1 |  | PASS |
| 131 | RBAC edit plan | owner -> ops |  | PASS |
| 132 | RBAC disable plan | t -> f |  | PASS |
| 133 | RBAC create schedule | 2 -> 3 |  | PASS |
| 134 | RBAC edit schedule | 1 -> 3 |  | PASS |
| 135 | RBAC disable schedule | t -> f |  | PASS |
| 136 | RBAC create plan | 0 -> 0 |  | PASS |
| 137 | RBAC edit plan | ops -> ops |  | PASS |
| 138 | RBAC disable plan | t -> t |  | PASS |
| 139 | RBAC create schedule | 3 -> 3 |  | PASS |
| 140 | RBAC edit schedule | 3 -> 3 |  | PASS |
| 141 | RBAC disable schedule | t -> t |  | PASS |
| 142 | RBAC create plan | 0 -> 0 |  | PASS |
| 143 | RBAC edit plan | ops -> ops |  | PASS |
| 144 | RBAC disable plan | t -> t |  | PASS |
| 145 | RBAC create schedule | 3 -> 3 |  | PASS |
| 146 | RBAC edit schedule | 3 -> 3 |  | PASS |
| 147 | RBAC disable schedule | t -> t |  | PASS |
| 148 | RBAC create plan | 0 -> 1 |  | PASS |
| 149 | RBAC edit plan | ops -> planner |  | PASS |
| 150 | RBAC disable plan | t -> f |  | PASS |
| 151 | RBAC create schedule | 3 -> 4 |  | PASS |
| 152 | RBAC edit schedule | 3 -> 6 |  | PASS |
| 153 | RBAC disable schedule | t -> f |  | PASS |
| 154 | RBAC create plan | 0 -> 0 |  | PASS |
| 155 | RBAC edit plan | planner -> planner |  | PASS |
| 156 | RBAC disable plan | t -> t |  | PASS |
| 157 | RBAC create schedule | 4 -> 4 |  | PASS |
| 158 | RBAC edit schedule | 6 -> 6 |  | PASS |
| 159 | RBAC disable schedule | t -> t |  | PASS |
| 160 | RBAC create plan | 0 -> 0 |  | PASS |
| 161 | RBAC edit plan | planner -> planner |  | PASS |
| 162 | RBAC disable plan | t -> t |  | PASS |
| 163 | RBAC create schedule | 4 -> 4 |  | PASS |
| 164 | RBAC edit schedule | 6 -> 6 |  | PASS |
| 165 | RBAC disable schedule | t -> t |  | PASS |
| 166 | RBAC create plan | 0 -> 0 |  | PASS |
| 167 | RBAC edit plan | planner -> planner |  | PASS |
| 168 | RBAC disable plan | t -> t |  | PASS |
| 169 | RBAC create schedule | 4 -> 4 |  | PASS |
| 170 | RBAC edit schedule | 6 -> 6 |  | PASS |
| 171 | RBAC disable schedule | t -> t |  | PASS |
| 172 | RBAC create plan | 0 -> 0 |  | PASS |
| 173 | RBAC edit plan | planner -> planner |  | PASS |
| 174 | RBAC disable plan | t -> t |  | PASS |
| 175 | RBAC create schedule | 4 -> 4 |  | PASS |
| 176 | RBAC edit schedule | 6 -> 6 |  | PASS |
| 177 | RBAC disable schedule | t -> t |  | PASS |
| 178 | RBAC create plan | 0 -> 0 |  | PASS |
| 179 | RBAC edit plan | planner -> planner |  | PASS |
| 180 | RBAC disable plan | t -> t |  | PASS |
| 181 | RBAC create schedule | 4 -> 4 |  | PASS |
| 182 | RBAC edit schedule | 6 -> 6 |  | PASS |
| 183 | RBAC disable schedule | t -> t |  | PASS |
| 184 | RBAC create plan | 0 -> 0 |  | PASS |
| 185 | RBAC edit plan | planner -> planner |  | PASS |
| 186 | RBAC disable plan | t -> t |  | PASS |
| 187 | RBAC create schedule | 4 -> 4 |  | PASS |
| 188 | RBAC edit schedule | 6 -> 6 |  | PASS |
| 189 | RBAC disable schedule | t -> t |  | PASS |
| 190 | RBAC generate now | 0 -> 1 |  | PASS |
| 191 | RBAC generate now | 0 -> 0 |  | PASS |
| 192 | RBAC generate now | 0 -> 1 |  | PASS |
| 193 | RBAC generate now | 0 -> 0 |  | PASS |
| 194 | RBAC generate now | 0 -> 0 |  | PASS |
| 195 | RBAC generate now | 0 -> 1 |  | PASS |
| 196 | RBAC generate now | 0 -> 0 |  | PASS |
| 197 | RBAC generate now | 0 -> 0 |  | PASS |
| 198 | RBAC generate now | 0 -> 0 |  | PASS |
| 199 | RBAC generate now | 0 -> 0 |  | PASS |
| 200 | RBAC generate now | 0 -> 0 |  | PASS |
| 201 | RBAC generate now | 0 -> 0 |  | PASS |
| 202 | Tenant: Beta cannot open the other tenant's plan | 1 -> 1 |  | PASS |
| 203 | Tenant: Beta cannot open its plan edit form | 1 -> 1 |  | PASS |
| 204 | Tenant: Beta cannot edit it (POST) | Tenant plan 20307MEDIUM -> Tenant plan 20307MEDIUM |  | PASS |
| 205 | Tenant: Beta cannot disable it | t -> t |  | PASS |
| 206 | Tenant: Beta cannot add a schedule to it | 1 -> 1 |  | PASS |
| 207 | Tenant: Beta cannot open its schedule | 1 -> 1 |  | PASS |
| 208 | Tenant: Beta cannot open its schedule edit form | 1 -> 1 |  | PASS |
| 209 | Tenant: Beta cannot edit its schedule | 0MONTHLY -> 0MONTHLY |  | PASS |
| 210 | Tenant: Beta cannot disable its schedule | t -> t |  | PASS |
| 211 | Tenant: Beta cannot GENERATE work for its schedule | 44/44 -> 44/44 |  | PASS |
| 212 | Tenant: Beta cannot create a plan on the other tenant's asset | 0 -> 0 |  | PASS |
| 213 | Tenant: Alpha cannot open the other tenant's plan | 1 -> 1 |  | PASS |
| 214 | Tenant: Alpha cannot open its plan edit form | 1 -> 1 |  | PASS |
| 215 | Tenant: Alpha cannot edit it (POST) | Beta plan 20307MEDIUM -> Beta plan 20307MEDIUM |  | PASS |
| 216 | Tenant: Alpha cannot disable it | t -> t |  | PASS |
| 217 | Tenant: Alpha cannot add a schedule to it | 1 -> 1 |  | PASS |
| 218 | Tenant: Alpha cannot open its schedule | 1 -> 1 |  | PASS |
| 219 | Tenant: Alpha cannot open its schedule edit form | 1 -> 1 |  | PASS |
| 220 | Tenant: Alpha cannot edit its schedule | 0MONTHLY -> 0MONTHLY |  | PASS |
| 221 | Tenant: Alpha cannot disable its schedule | t -> t |  | PASS |
| 222 | Tenant: Alpha cannot GENERATE work for its schedule | 44/44 -> 44/44 |  | PASS |
| 223 | Tenant: Alpha cannot create a plan on the other tenant's asset | 0 -> 0 |  | PASS |
| 224 | Bell unread count equals the database | 47 |  | PASS |
| 225 | Clicking a notification marks it read | 47 |  | PASS |
| 226 | Anonymous POST /app/maintenance/plans/new/ is refused (login redirect / 403) and changes nothi… | 0 -> 0 |  | PASS |
| 227 | Anonymous POST /app/maintenance/schedules/{id}/generate/ is refused (login redirect / 403) and… | 44 -> 44 |  | PASS |
| 228 | Anonymous POST /app/maintenance/plans/{id}/active/ is refused (login redirect / 403) and chang… | t -> t |  | PASS |

## 8. HTMX

HTMX requests observed: `GET /app/notifications/bell/` x532, `GET /app/contracts/work-orders/{id}/panel/` x2. Failures observed: 0 (all injected on purpose: `-`). 3/3 HTMX-related checks PASS.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Notification bell present for the planner | planner | SUPERSEDED | bell -> ok |
| 2 | Notification bell (HTMX-loaded) is present for the planner | planner | PASS | bell rendered -> Notifications (47 unread) |
| 3 | Bell unread count equals the database | planner | PASS | 47 unread -> Notifications (47 unread) |
| 4 | Bell dropdown lists the M04 notifications (reminder / generated work order) | planner | PASS | M04 items -> Notifications Mark all read WO-000043 generated: RBGEN planner 20307 1 minute ago WO-000042 generate |

## 9. Error handling

Deliberately provoked errors (forged ids, unauthorised roles, invalid input, foreign tenants) were answered with 400/403/404/405/409-style refusals and a visible message, never a stack trace; the one exception is listed in section 13. Provoked responses are counted separately from unexplained errors:

| Provoked response | Count |
|---|---|
| 400 POST /app/maintenance/plans/{id}/schedules/new/ body=tri | 39 |
| 400 POST /app/maintenance/plans/new/ body=asset={id}&name=V+ | 10 |
| 403 GET /app/maintenance/plans/new/ | 9 |
| 403 GET /app/maintenance/plans/{id}/edit/ | 9 |
| 403 GET /app/maintenance/plans/{id}/schedules/new/ | 9 |
| 403 GET /app/maintenance/schedules/{id}/edit/ | 9 |
| 403 POST /app/maintenance/plans/new/ body=asset={id}&name=RB | 9 |
| 403 POST /app/maintenance/plans/{id}/edit/ body=name=RBAC+pl | 9 |
| 403 POST /app/maintenance/plans/{id}/active/ body=active=0 | 9 |
| 403 POST /app/maintenance/plans/{id}/schedules/new/ body=tri | 9 |
| 403 POST /app/maintenance/schedules/{id}/edit/ body=frequenc | 9 |
| 403 POST /app/maintenance/schedules/{id}/disable/ body= | 9 |
| 403 POST /app/maintenance/schedules/{id}/generate/ body= | 9 |
| 400 POST /app/maintenance/schedules/{id}/edit/ body=frequenc | 7 |

45/45 error/negative-path checks PASS.

## 10. Responsive / keyboard / modal behaviour

39/39 responsive and usability checks PASS. Method: for each page and viewport the page's `scrollWidth` is compared with the window width, elements wider than the window and clipped buttons/inputs are listed (tables inside `.table-responsive` may scroll internally).

| Page | 1920x1080 | 1440x900 | 1024x768 | 390x844 |
|---|---|---|---|---|
| Plan list | PASS | PASS | PASS | PASS |
| New plan | PASS | PASS | PASS | PASS |
| Plan detail | PASS | PASS | PASS | PASS |
| Edit plan | PASS | PASS | PASS | PASS |
| New schedule | PASS | PASS | PASS | PASS |
| Schedule detail | PASS | PASS | PASS | PASS |
| Edit schedule | PASS | PASS | PASS | PASS |
| Due list | PASS | PASS | PASS | PASS |
| PM history | PASS | PASS | PASS | PASS |

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Mobile: validation error visible on the schedule form | owner | PASS | visible -> True |
| 2 | Mobile: the 'Disable plan' confirmation dialog fits the viewport | owner | PASS | within viewport -> {'x': 15.59375, 'y': 335.4375, 'width': 358.796875, 'height': 173.125} |
| 3 | Keyboard: Tab order follows the schedule form fields | owner | PASS | logical -> ['frequency', 'interval_count', 'start_date', 'meter'] |

## 11. Console / network result

Console errors, page errors, failed requests and 4xx/5xx recorded outside the harness' 'provoked error' window: 2, of which **0 unexplained** and 2 are 400/404 answers to the scripted negative probes (forged id, foreign tenant, invalid input) whose console line was emitted after the suppression window closed. JavaScript page errors: 0.

Unexplained:

| Kind | Message | Count |
|---|---|---|
| - | none | 0 |

Explained (deliberate negative probes):

| Kind | Message | Count |
|---|---|---|
| http | 404 GET /api/v1/maintenance-plans/{id}/ | 1 |
| console | Failed to load resource: the server responded with a status of 404 (Not Found) | 1 |

Provoked (expected) problems recorded inside the suppression window: 446; aborted requests of the polling notification bell during navigation (benign, not errors): 19; failed static assets: 0.

Notes: `GET /favicon.ico 404` (if listed) is reported as BX-ALL-02 (cosmetic).

## 12. Integration result

- Site -> Zone -> Asset -> PM plan -> schedule -> generated Work Order: verified end to end in the browser and database (WO-numbered row, PREVENTIVE, plan priority, PLANNED, source = cycle id, asset, estimated hours, planned window = schedule window moved to the site's working day, description with plan/recurrence/required checklist).
- Duplicate prevention: second 'Generate now' refused while the previous WO is open; 5 simultaneous POSTs -> exactly one cycle/WO; Celery fan_out run 3x + 2x -> exactly one scheduler cycle, later runs idempotent (PASS).
- Meter-based: a reading recorded in M02 (520 h) turns the 500 h schedule DUE (PASS). Reminders: planner receives exactly one notification, visible in the notifications page and the bell (PASS).
- Overdue/missed catch-up was exercised by rewinding the QA database counters (clock cannot be advanced): ONE work order covered 7 missed occurrences ('+7 missed'). This is a labelled simulation, not a time-travel test.
- PM state after the work order moves on (assigned/completed/verified) is M06 -> UNVERIFIED in this batch.

## 13. Findings

Counts for this module: Critical 0, High 1, Medium 0, Low 3, Cosmetic 1, Unverified 1.

| ID | Severity | Title | Status |
|---|---|---|---|
| BX-M04-01 | HIGH | Editing a schedule's recurrence re-points it at an already-generated occurrence; the next due occurrence is silently lost (F-H01, reproduce… | OPEN (same defect as F-H01 in FINDINGS_… |
| BX-ALL-01 | LOW | Keyboard / mobile navigation accessibility: no 'skip to content' link; off-canvas sidebar links stay focusable while hidden; Esc does not c… | OPEN |
| BX-M04-02 | LOW | 'Estimated hours = 0' is accepted by the form (min=0) but refused by the server ('must be a positive number') | OPEN |
| BX-M04-03 | LOW | DUE state does not distinguish 'due today' from 'overdue by N days' | OPEN |
| BX-ALL-02 | COSMETIC | Every fresh browser session logs 'GET /favicon.ico -> 404' in the console (no favicon served) | OPEN |

### BX-M04-01 - HIGH - Editing a schedule's recurrence re-points it at an already-generated occurrence; the next due occurrence is silently lost (F-H01, reproduced in the browser)

- **Module:** M04
- **Page / URL:** /app/maintenance/schedules/{id}/edit/ -> /app/maintenance/schedules/{id}/
- **Role:** owner (Org Owner)
- **Action:** Generate cycle 0 (monthly, start today) -> Edit: interval 1 -> 2 -> Save -> open schedule -> Generate now
- **Expected:** After the edit the schedule continues at the next valid occurrence (sequence 1, date in 2 months) and keeps generating work orders (D-043 / HPE PM requirement).
- **Actual:** Saved schedule shows next occurrence no. 0, next due = today, state DUE although cycle 0 already has its work order; 'Generate now' answers 'Nothing was generated (that occurrence already has its work order)'. The unique (schedule, sequence) collision is swallowed: work orders 12 -> 12; database after the click: next_sequence=1, next due moved to 2026-12-04 (the occurrence due today was skipped), last_error empty, audit rows for the schedule only 'schedule_created' and 'schedule_updated' (nothing records the skip).
- **API / HTMX / network:** POST /app/maintenance/schedules/{id}/edit/ 302; POST .../generate/ 302 (flash 'Nothing was generated')
- **Console:** none (the failure is silent)
- **Screenshot:** evidence/shots/M04_generated_wo.png (cycle 0) - failure is textual, see run row 'F-H01 recheck'
- **Source location:** src/apps/maintenance/services.py: update_schedule:299, _resync:210, generate_cycle IntegrityError branch:460
- **Status:** OPEN (same defect as F-H01 in FINDINGS_REGISTER.md; browser-confirmed)
- **Run evidence:** [FAIL] F-H01 recheck: edit the recurrence (every 1 -> every 2 months) after cycle 0 ex… -> after edit: next=0\|2026-10-04, state shown 'Every 2 months Due'; Generate now result: 'Nothing was generated (that occurrence already has …

### BX-ALL-01 - LOW - Keyboard / mobile navigation accessibility: no 'skip to content' link; off-canvas sidebar links stay focusable while hidden; Esc does not close the open mobile menu

- **Module:** M01-M04
- **Page / URL:** every /app/ page (src/templates/shell.html)
- **Role:** owner
- **Action:** Tab from the top of any page; open the mobile menu at 390 px and press Escape
- **Expected:** Skip link; hidden navigation not focusable; Esc closes the menu.
- **Actual:** ~35 sidebar tab stops precede page content; the hidden (translated off-screen) nav links remain in the tab order; the menu stays open after Esc.
- **API / HTMX / network:** -
- **Console:** none
- **Screenshot:** evidence/shots/M01_mobile_menu_open.png
- **Source location:** src/templates/shell.html, src/static/js/app.js:41
- **Status:** OPEN

### BX-M04-02 - LOW - 'Estimated hours = 0' is accepted by the form (min=0) but refused by the server ('must be a positive number')

- **Module:** M04
- **Page / URL:** /app/maintenance/plans/new/
- **Role:** owner
- **Action:** Create a plan with estimated hours 0
- **Expected:** Form and server agree.
- **Actual:** 400 with a clear message; nothing saved (safe, inconsistent).
- **API / HTMX / network:** POST /app/maintenance/plans/new/ -> 400
- **Console:** 400 (provoked)
- **Screenshot:** -
- **Source location:** src/apps/maintenance/forms.py:25 vs services.py:90 (_decimal positive=True)
- **Status:** OPEN
- **Run evidence:** [PARTIAL] Boundary: estimated hours = 0 -> http=400; created=False; message='Estimated hours must be a positive number (max 3 decimals).'

### BX-M04-03 - LOW - DUE state does not distinguish 'due today' from 'overdue by N days'

- **Module:** M04
- **Page / URL:** /app/maintenance/due/, schedule and history pages
- **Role:** owner
- **Action:** Rewind a schedule 7 days (QA database) and read the state
- **Expected:** An overdue indicator.
- **Actual:** State DUE; the backlog is shown only as '+7 missed' on the generated cycle.
- **API / HTMX / network:** -
- **Console:** none
- **Screenshot:** -
- **Source location:** src/apps/maintenance/selectors.py:87 (schedule_state)
- **Status:** OPEN
- **Run evidence:** [PARTIAL] Cycle table 'Overdue' presentation -> M04 shows DUE (including overdue: the badge does not distinguish 'due today' from 'overdue by N days'); overdue backlog is expressed as '+N…

### BX-ALL-02 - COSMETIC - Every fresh browser session logs 'GET /favicon.ico -> 404' in the console (no favicon served)

- **Module:** M01-M04
- **Page / URL:** any page
- **Role:** any
- **Action:** Open any page in a new browser context
- **Expected:** No console error.
- **Actual:** Console error 'Failed to load resource: 404 /favicon.ico' (once per fresh context).
- **API / HTMX / network:** GET /favicon.ico -> 404
- **Console:** Failed to load resource: the server responded with a status of 404 (Not Found) /favicon.ico
- **Screenshot:** -
- **Source location:** src/templates/shell.html / static files (no <link rel=icon>)
- **Status:** OPEN

**Unverified items (not claimed as PASS):**

- PM state follows the work order lifecycle (assigned / completed / verified): Advancing a work order is M06 (later batch). Only GENERATED state and the cycle -> work-order contract were verified (WO row, source link, planned window, priority, hours, checklist text, link from the cycle table to the WO page).

## 14. Evidence

- Raw per-run result files (every row, console/network capture, click and request coverage): `evidence/M04_run_plans.json`, `evidence/M04_run_schedules_generation_reminders_rbac_tenant_responsive.json`, `evidence/M04_run_notification_bell.json`, `evidence/M04_run_anonymous_session.json`
- Discovery inventory (all pages/links/buttons/forms/tables/HTMX of M01-M04): `evidence/inventory_owner.json`; coverage computation: `evidence/coverage.json`
- Screenshots: `evidence/shots/M04_bell.png`, `evidence/shots/M04_generated_wo.png`, `evidence/shots/M04_meter_due.png`, `evidence/shots/M04_mobile_due.png`, `evidence/shots/M04_mobile_modal.png`, `evidence/shots/M04_mobile_validation.png`, `evidence/shots/M04_reminder.png`
- Scripts (Playwright, Python): `tools/playwright/` (m04a.py, m04b.py, m04c.py)
- Provoked-error and benign-abort logs are stored in the run files under `expected` and `benign`.

## 15. Final module status

**M04: FAIL (High defect).** 557/562 checks PASS; 1 FAIL; 3 PARTIAL; 1 UNVERIFIED; 1 not applicable.
Open findings: BX-M04-01 (HIGH), BX-ALL-01 (LOW), BX-M04-02 (LOW), BX-M04-03 (LOW), BX-ALL-02 (COSMETIC).
Plans, schedules, generation (UI, Celery, concurrency), duplicate prevention, reminders, lead days, catch-up and cross-module blocking work. The High defect BX-M04-01 (F-H01: recurrence edit re-points the schedule at an already generated occurrence) is reproduced in the browser and BLOCKS acceptance of M04 until fixed.
