# M01 browser acceptance - detailed (Sites, Locations, Calendars & Contacts)

**Batch 1 of the browser acceptance (M01-M04).** Real Chromium (Playwright) against the running application (DEBUG off, CSP on, PostgreSQL `fieldops_browser_qa`, Redis, Celery worker + beat). Every check below was performed in the browser (or by a real in-page request carrying the session cookie and CSRF token) and the database state was read back with SQL; an HTTP 200 alone was never accepted as evidence. No production code was modified.

**Result: M01: 731/738 browser checks PASS** (1 FAIL, 6 PARTIAL, 0 UNVERIFIED; 3 NOT APPLICABLE excluded; 0 superseded harness lines excluded). **Module status: PARTIAL (defect reproduced).**

Roles driven: owner, admin, ops, supervisor, assets, planner, tech (technician 1), tech2, stores, service, auditor, client (all Alpha) and betaowner (tenant Beta). Viewports: 1920x1080, 1440x900, 1024x768, 390x844.

Matrix columns used by the scripts: FEATURE / PAGE / ROLE / ACTION / EXPECTED / ACTUAL / DATABASE / API-HTMX / AUDIT / STATUS; the full matrix for this module is in `evidence/M01_run_sites.json`, `evidence/M01_run_zones_calendars_contacts.json`, `evidence/M01_run_rbac_tenant_audit_links_responsive.json`, `evidence/M01_run_mobile_menu.json`, `evidence/M01_run_sorting.json`, `evidence/M01_run_anonymous_session.json`.

## 1. Pages tested

Discovered by a crawl of the module (owner): 11 pages; visited in the test runs: 11/11.

| Page / URL (normalised) | Discovered by crawl | Browser visits |
|---|---|---|
| `/app/` | no (reached by test) | 33 |
| `/app/audit/` | no (reached by test) | 1 |
| `/app/audit/?q` | no (reached by test) | 2 |
| `/app/calendars/{id}/edit/` | yes | 20 |
| `/app/contacts/{id}/edit/` | yes | 20 |
| `/app/locations/{id}/edit/` | yes | 31 |
| `/app/portal/` | no (reached by test) | 2 |
| `/app/sites/` | yes | 32 |
| `/app/sites/?ordering` | no (reached by test) | 1 |
| `/app/sites/?page` | no (reached by test) | 9 |
| `/app/sites/?page&q` | no (reached by test) | 2 |
| `/app/sites/?q` | no (reached by test) | 15 |
| `/app/sites/?q&status` | no (reached by test) | 2 |
| `/app/sites/?status` | no (reached by test) | 5 |
| `/app/sites/new/` | yes | 43 |
| `/app/sites/not-a-uuid/` | no (reached by test) | 1 |
| `/app/sites/{id}/` | yes | 42 |
| `/app/sites/{id}/?tab` | yes | 128 |
| `/app/sites/{id}/calendars/new/` | yes | 28 |
| `/app/sites/{id}/contacts/new/` | yes | 29 |
| `/app/sites/{id}/edit/` | yes | 28 |
| `/app/sites/{id}/locations/new/` | yes | 48 |

Other URLs the tests visited (negative probes, redirects, API): `/app/assets/new/`, `/app/assets/new/?site`, `/app/assets/{id}/`, `/app/sites/{id}/locations/new/?parent`

## 2. Buttons / links / actions

Discovered controls: 12 buttons (12 clicked/posted), 18 distinct links (13 followed), 12 POST endpoints (12 exercised), 1 GET filter forms (1 used), 2 HTMX endpoints (2 exercised).

State-changing requests issued by the browser (normalised path -> count): `/app/sites/{id}/locations/new/` x45, `/app/sites/{id}/calendars/new/` x37, `/app/sites/new/` x35, `/app/sites/{id}/contacts/new/` x28, `/app/locations/{id}/edit/` x25, `/app/sites/{id}/edit/` x23, `/app/sites/{id}/` x22, `/app/locations/{id}/status/` x22, `/accounts/login/` x21, `/app/calendars/{id}/holidays/` x20, `/app/calendars/{id}/delete/` x17, `/app/contacts/{id}/edit/` x17, `/app/calendars/{id}/edit/` x16, `/api/v1/sites/` x3, `/api/v1/assets/` x2, `/app/sites/{id}/locations/new/?parent` x1

**Controls discovered but NOT exercised (with reason):**

- `/app/contracts/agreements/new/?assets` - warranty / contract coverage belongs to M10 (later batch); the asset 'Coverage' panel loaded without error
- `/app/contracts/agreements/{id}/` - warranty / contract coverage belongs to M10 (later batch); the asset 'Coverage' panel loaded without error
- `/app/identification/assets/{id}/label/` - QR / barcode / scan feature belongs to M07 (later batch); the asset 'Labels' panel itself loaded without error
- `/app/identification/scan/` - QR / barcode / scan feature belongs to M07 (later batch); the asset 'Labels' panel itself loaded without error
- `/app/incidents/new/?asset` - link into M05 (later batch); the target href carries ?asset=<id> and was verified, the incident page was not opened

## 3. Forms

14 distinct forms discovered (owner view); every field of every form was filled, left blank and given invalid/boundary values in section 4.

| Form (action) | Method | Fields (non-hidden) | Exercised |
|---|---|---|---|
| `/app/sites/ (self)` | GET | q, status | yes |
| `/app/sites/new/ (self)` | POST | code, name, description, address, city, state_region, postal_code, country, timezone, contact_name, contact_email, contact_phone | yes |
| `/app/sites/{id}/ (self)` | POST | action, reason | yes |
| `/app/locations/{id}/status/` | POST | action, reason | yes |
| `/app/calendars/{id}/delete/` | POST | (button only) | yes |
| `/app/calendars/{id}/holidays/` | POST | action | yes |
| `/app/contacts/{id}/edit/` | POST | action | yes |
| `/app/sites/{id}/edit/ (self)` | POST | code, name, description, address, city, state_region, postal_code, country, timezone, contact_name, contact_email, contact_phone | yes |
| `/app/sites/{id}/locations/new/ (self)` | POST | name, zone_type, code, parent, description | yes |
| `/app/sites/{id}/calendars/new/ (self)` | POST | name, is_24x7, working_days, working_days, working_days, working_days, working_days, working_days, working_days, start_time, end_time, is_d… | yes |
| `/app/sites/{id}/contacts/new/ (self)` | POST | name, role_title, phone, email, escalation_order, notes | yes |
| `/app/locations/{id}/edit/ (self)` | POST | name, zone_type, code, parent, description | yes |
| `/app/calendars/{id}/edit/ (self)` | POST | name, is_24x7, working_days, working_days, working_days, working_days, working_days, working_days, working_days, start_time, end_time, is_d… | yes |
| `/app/contacts/{id}/edit/ (self)` | POST | name, role_title, phone, email, escalation_order, notes | yes |

## 4. Validation (client + server)

57/58 validation, boundary, duplicate, forged-input and XSS checks PASS. Forms are `novalidate`; constraints that the browser would block were removed in the page (or the request forged from the page) so that the SERVER rules were exercised, and the matching client hint (maxlength/required) was asserted separately.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Search term is escaped (XSS) | owner | PASS | inert -> no script executed |
| 2 | Pagination: no duplicate or missing rows across all pages | owner | PASS | 85 unique -> 85/85 |
| 3 | Create site: only required fields | owner | PASS | created ACTIVE with blanks -> ACTIVE\|UTC |
| 4 | Site validation: duplicate code (exact) | owner | PASS | rejected with already exists; no row -> rows=1 msg=A site with this code already exists. |
| 5 | Site validation: duplicate code (lower-case) | owner | PASS | rejected with already exists; no row -> rows=1 msg=A site with this code already exists. |
| 6 | Site validation: duplicate code with padding | owner | PASS | rejected; no row -> rows=1 msg=A site with this code already exists. |
| 7 | Boundary: 1-character code/name accepted | owner | PASS | created -> Site E created. |
| 8 | Boundary: code at max length (30) accepted | owner | PASS | created -> Site 14910ZZZZZZZZZZZZZZZZZZZZZZZZZ created. |
| 9 | Stored XSS in site name is escaped on detail | owner | PASS | inert -> escaped |
| 10 | Stored XSS escaped in list | owner | PASS | inert -> ok |
| 11 | Empty submit: field-level 'required' errors under code and name | owner | PASS | error beneath each missing field -> novalidate=True posted=1 fields_with_error=['code', 'name'] |
| 12 | Validation messages are visible | owner | PASS | visible -> True |
| 13 | Edit: duplicate code rejected | owner | PASS | rejected -> A site with this code already exists. |
| 14 | Deactivate with reason '' refused server-side | owner | PASS | ACTIVE -> 200 |
| 15 | Deactivate with reason '   ' refused server-side | owner | PASS | ACTIVE -> 200 |
| 16 | Seventh level rejected (limit 6) | owner | PASS | refused with message -> Location hierarchy is limited to 6 levels. |
| 17 | Zone validation: duplicate name under the same parent (exact) | owner | PASS | rejected (already exists) -> count=1 A location with this name already exists here. |
| 18 | Zone validation: duplicate name, different case | owner | PASS | rejected (already exists) -> count=1 A location with this name already exists here. |
| 19 | Zone validation: duplicate root name | owner | PASS | rejected (already exists) -> count=1 A location with this name already exists here. |
| 20 | Zone validation: duplicate code in site (exact) | owner | PASS | rejected (code already exists) -> count=0 A location with this code already exists in the site. |
| 21 | Zone validation: duplicate code in site (case-insensitive) | owner | PASS | rejected (code already exists) -> count=0 A location with this code already exists in the site. |
| 22 | Stored XSS in zone name/description is escaped | owner | PASS | inert -> escaped |
| 23 | Crafted POST: parent from another site rejected | owner | PASS | no zone created -> http=400 |
| 24 | Crafted POST: parent from another tenant rejected | owner | PASS | no zone created -> http=400 |
| 25 | Crafted POST: non-existent parent rejected | owner | PASS | no zone created -> http=400 |
| 26 | Crafted POST: malformed parent id rejected | owner | PASS | no zone created -> http=400 |
| 27 | Move that would exceed depth 6 refused | owner | PASS | refused -> Location hierarchy is limited to 6 levels. |
| 28 | Changing type to Building while nested refused | owner | PASS | refused -> A building must be a top-level location of the site. |
| 29 | Cycle prevention (crafted POST): self as parent | owner | PASS | rejected, parent unchanged -> http=400 |
| 30 | Cycle prevention (crafted POST): descendant as parent | owner | PASS | rejected, parent unchanged -> http=400 |
| 31 | Cycle prevention (crafted POST): block (root) under its descendant | owner | PASS | rejected, parent unchanged -> http=400 |
| 32 | Edit: duplicate name among siblings handled | owner | PASS | rejected (unique among siblings) -> A location with this name already exists here. |
| 33 | Edit: duplicate code in site rejected | owner | PASS | rejected -> A location with this code already exists in the site. |
| 34 | Deactivate without reason refused (server) | owner | PASS | ACTIVE -> 200 |
| 35 | Child under an inactive parent refused | owner | PASS | refused -> 400 |
| 36 | Overnight window (end<start) rejected | owner | PASS | refused 'End time must be after start' -> End time must be after start time. |
| 37 | Equal start/end rejected | owner | PASS | refused -> End time must be after start time. |
| 38 | No working day selected rejected | owner | PASS | refused -> Select at least one working day. |
| 39 | Missing hours rejected (non-24x7) | owner | PASS | refused -> Start and end time are required unless the site works 24x7. |
| 40 | Calendar name required | owner | PASS | refused -> This field is required. |
| 41 | Duplicate calendar name rejected | owner | PASS | refused -> A calendar with this name already exists for the site. |
| 42 | Deleting the default calendar (others exist) refused | owner | PASS | refused -> Make another calendar the default before deleting this one. |
| 43 | Second holiday on the same date rejected | owner | PASS | refused -> This calendar already has a holiday on that date. |
| 44 | Invalid holiday date refused (server) | owner | PASS | refused -> 200 |
| 45 | Holiday without name refused (server) | owner | PASS | refused -> 200 |
| 46 | Duplicate escalation order rejected | owner | PASS | refused -> Escalation level 5 is already used at this site. |
| 47 | Contact name required | owner | PASS | refused -> This field is required. |
| 48 | Invalid contact email rejected | owner | PASS | refused -> Enter a valid email address. |
| 49 | Escalation order zero (0) rejected cleanly (no server error) | owner | PASS | 400 re-render with a field error, nothing saved -> http=400; Ensure this value is greater than or equal to 1. |
| 50 | Escalation order negative (-3) rejected cleanly (no server error) | owner | PASS | 400 re-render with a field error, nothing saved -> http=400; Ensure this value is greater than or equal to 1. |
| 51 | Escalation order decimal (1.5) rejected cleanly (no server error) | owner | PASS | 400 re-render with a field error, nothing saved -> http=400; Enter a whole number. |
| 52 | Escalation order huge (99999999999) rejected cleanly (no server error) | owner | FAIL | 400 re-render with a field error, nothing saved -> http=500; Server Error page |
| 53 | Stored XSS in contact name escaped | owner | PASS | inert -> ok |
| 54 | Edit to an order already used is rejected | owner | PASS | refused -> Escalation level 2 is already used at this site. |
| 55 | Anonymous POST /app/sites/new/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 098/accounts/login/?next=/app/sites/new/ |
| 56 | Anonymous POST /app/sites/{id}/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> es/358049f8/ |
| 57 | Anonymous POST /app/locations/{id}/status/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 05cf-74e4-4e5b-ad2d-938dda9c75cd/status/ |
| 58 | Anonymous POST /app/calendars/{id}/delete/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> fe66-d1db-4827-a89a-6a527116f956/delete/ |

## 5. RBAC

386/386 RBAC checks PASS across 34 distinct checks x up to 12 roles. For every role the expected outcome is derived from the role's real permission set in the database (membership -> role -> permission); the browser then proves (a) the control is shown iff permitted, (b) the direct URL answers 200 iff permitted else 403/404, (c) a real forged POST is refused with the database unchanged when denied and succeeds with the expected state change when allowed.

| Check (expected outcome derived from the role's DB permission set) | owner | admin | ops | supervisor | assets | planner | tech | tech2 | stores | service | auditor | client |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RBAC nav 'Sites & Locations' shown iff site.view | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC site list access | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC 'New site' button iff site.create | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC site detail opens | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC site 'Edit' iff site.update | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC site 'Deactivate' iff site.deactivate | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC 'Add location' iff zone.create | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC zone 'Edit' iff zone.update | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC zone 'Deactivate' iff zone.deactivate | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC 'Add calendar' iff calendar.create | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC calendar 'Edit' iff calendar.update | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC calendar 'Delete' iff calendar.delete | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC contact add/edit iff site.contact.manage | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC direct URL: site create form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: site edit form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: zone create form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: zone edit form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: calendar create form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: calendar edit form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: contact create form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: contact edit form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC create site | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC edit site | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC deactivate site | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC create zone | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC edit zone | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC deactivate zone | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC create calendar | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC edit calendar | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC add holiday | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC delete calendar | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC add contact | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC edit contact | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC created sites all belong to the actor's tenant | - | - | - | - | - | - | - | - | - | - | - | - |

## 6. Tenant isolation (Alpha <-> Beta, both directions)

46/46 tenant checks PASS. Beta fixtures were created through the Beta UI; Alpha fixtures through the Alpha UI. Probes cover list, search, filters, detail, edit forms, edit POSTs, status/state actions, documents/meters/relations/schedules, HTMX partials, file download, API and forged foreign ids.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Crafted POST: parent from another tenant rejected | owner | PASS | no zone created -> http=400 |
| 2 | Setup: Beta site/zone/calendar/contact exist | betaowner | PASS | rows exist -> ['a54ca2be', '476857f8', 'f1d1482b', 'c56882d2'] |
| 3 | Tenant: Beta cannot open Alpha site detail | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 4 | Tenant: Beta cannot open Alpha site edit form | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 5 | Tenant: Beta cannot edit Alpha site (POST) | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 6 | Tenant: Beta cannot deactivate Alpha site | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 7 | Tenant: Beta cannot create a zone in an Alpha site | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 8 | Tenant: Beta cannot edit an Alpha zone | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 9 | Tenant: Beta cannot open an Alpha zone edit form | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 10 | Tenant: Beta cannot deactivate an Alpha zone | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 11 | Tenant: Beta cannot create an Alpha calendar | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 12 | Tenant: Beta cannot edit an Alpha calendar | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 13 | Tenant: Beta cannot delete an Alpha calendar | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 14 | Tenant: Beta cannot add an Alpha holiday | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 15 | Tenant: Beta cannot add an Alpha contact | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 16 | Tenant: Beta cannot edit an Alpha contact | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 17 | Tenant: Alpha cannot open Beta site detail | owner | PASS | 403/404, DB unchanged -> http=404 |
| 18 | Tenant: Alpha cannot edit Beta site (POST) | owner | PASS | 403/404, DB unchanged -> http=404 |
| 19 | Tenant: Alpha cannot deactivate Beta site | owner | PASS | 403/404, DB unchanged -> http=404 |
| 20 | Tenant: Alpha cannot create a zone in a Beta site | owner | PASS | 403/404, DB unchanged -> http=404 |
| 21 | Tenant: Alpha cannot edit a Beta zone | owner | PASS | 403/404, DB unchanged -> http=404 |
| 22 | Tenant: Alpha cannot open a Beta zone edit form | owner | PASS | 403/404, DB unchanged -> http=404 |
| 23 | Tenant: Alpha cannot deactivate a Beta zone | owner | PASS | 403/404, DB unchanged -> http=404 |
| 24 | Tenant: Alpha cannot edit a Beta calendar | owner | PASS | 403/404, DB unchanged -> http=404 |
| 25 | Tenant: Alpha cannot delete a Beta calendar | owner | PASS | 403/404, DB unchanged -> http=404 |
| 26 | Tenant: Alpha cannot add a Beta holiday | owner | PASS | 403/404, DB unchanged -> http=404 |
| 27 | Tenant: Alpha cannot edit a Beta contact | owner | PASS | 403/404, DB unchanged -> http=404 |
| 28 | Tenant: Alpha cannot add a Beta contact | owner | PASS | 403/404, DB unchanged -> http=404 |
| 29 | Alpha site list/search never shows Beta sites | owner | PASS | no result -> not listed |
| 30 | Alpha list has no Beta sites | owner | PASS | not listed -> ok |
| 31 | Beta site list/search never shows Alpha sites | betaowner | PASS | no result -> ok |
| 32 | Beta asset form offers no Alpha sites/zones | betaowner | PASS | none -> ['(none)', 'PUN-1 · Beta zone 15610', 'PUN-1 · Beta zone 15865', 'PUN-1 · Block 1', '---------', 'PUN-1 · Pune Plant'] |
| 33 | API: Beta GET Alpha site -> 404 | betaowner | PASS | 404 -> 404 |
| 34 | API: Beta site list has no Alpha sites | betaowner | PASS | none -> ['PUN-1'] |
| 35 | Anonymous GET /app/sites/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> http://127.0.0.1:8098/accounts/login/?next=/app/sites/ |
| 36 | Anonymous GET /app/sites/new/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> http://127.0.0.1:8098/accounts/login/?next=/app/sites/new/ |
| 37 | Anonymous GET /app/sites/{id}/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> login/?next=/app/sites/358049f8/ |
| 38 | Anonymous GET /app/sites/{id}/edit/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> /?next=/app/sites/358049f8/edit/ |
| 39 | Anonymous GET /app/sites/{id}/locations/new/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> pp/sites/358049f8/locations/new/ |
| 40 | Anonymous GET /app/locations/{id}/edit/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> xt=/app/locations/81f005cf/edit/ |
| 41 | Anonymous GET /app/calendars/{id}/edit/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> xt=/app/calendars/ccbbfe66/edit/ |
| 42 | Anonymous GET /app/contacts/{id}/edit/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> ext=/app/contacts/44c088e3/edit/ |
| 43 | Anonymous POST /app/sites/new/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 098/accounts/login/?next=/app/sites/new/ |
| 44 | Anonymous POST /app/sites/{id}/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> es/358049f8/ |
| 45 | Anonymous POST /app/locations/{id}/status/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 05cf-74e4-4e5b-ad2d-938dda9c75cd/status/ |
| 46 | Anonymous POST /app/calendars/{id}/delete/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> fe66-d1db-4827-a89a-6a527116f956/delete/ |

## 7. Database persistence (browser action -> SQL read-back, refresh persistence, audit)

229/231 checks that carry a database/audit read-back PASS.

| # | Feature | Db | Audit | Status |
|---|---|---|---|---|
| 1 | Site list counts equal DB | zone/asset counts |  | PASS |
| 2 | Create site: every field saved | C14910\|Create Test Site 14910\|desc here\|1 Main Road/Second line\|Chennai\|TN… | site.created | PASS |
| 3 | Create site: audited |  | site.created | PASS |
| 4 | Create site: organization = Alpha | organization_id |  | PASS |
| 5 | Site validation: missing code | 0 |  | PASS |
| 6 | Site validation: whitespace-only code | 0 |  | PASS |
| 7 | Site validation: missing name | 0 |  | PASS |
| 8 | Site validation: missing timezone | 0 |  | PASS |
| 9 | Site validation: invalid timezone | 0 |  | PASS |
| 10 | Site validation: timezone with wrong case | 0 |  | PASS |
| 11 | Site validation: invalid email | 0 |  | PASS |
| 12 | Site validation: code with spaces/specials | 0 |  | PASS |
| 13 | Site validation: code over max length | 0 |  | PASS |
| 14 | Site validation: name over max length | 0 |  | PASS |
| 15 | Site validation: phone over max length | 0 |  | PASS |
| 16 | Site validation: country over max length | 0 |  | PASS |
| 17 | Site validation: duplicate code (exact) | 1 |  | PASS |
| 18 | Site validation: duplicate code (lower-case) | 1 |  | PASS |
| 19 | Site validation: duplicate code with padding | 1 |  | PASS |
| 20 | Edit site: all 11 editable fields persisted | Edited 14910\|new desc\|22 New Street\|Madurai\|KA\|625001\|LK\|Asia/Colombo\|B… | site.created,site.updated | PASS |
| 21 | Edit audited with before/after |  | {"city": "Chennai", "code": "C14910", "name": "Create … | PASS |
| 22 | No-change save writes no audit row |  | 2->2 | PASS |
| 23 | Deactivate without reason: browser validation | ACTIVE (safe) |  | PARTIAL |
| 24 | Deactivate confirmed -> INACTIVE |  | site.created,site.updated,site.updated,site.deactivated | PASS |
| 25 | Reactivate -> ACTIVE |  | site.created,site.updated,site.updated,site.deactivate… | PASS |
| 26 | Deactivate/reactivate audited |  | site.created,site.updated,site.updated,site.deactivate… | PASS |
| 27 | Create root building: all fields saved | BUILDING\|-\|BLK-A\|Main block\|ACTIVE | zone.created | PASS |
| 28 | Child created under Block A | parent_id |  | PASS |
| 29 | Six-level hierarchy created through the UI | depth=6 |  | PASS |
| 30 | Crafted POST: parent from another site rejected | 0 rows |  | PASS |
| 31 | Crafted POST: parent from another tenant rejected | 0 rows |  | PASS |
| 32 | Crafted POST: non-existent parent rejected | 0 rows |  | PASS |
| 33 | Crafted POST: malformed parent id rejected | 0 rows |  | PASS |
| 34 | Zone edit: name/type/code/description persisted | Floor One\|SERVICE_AREA\|F-1\|edited | zone.created,zone.updated | PASS |
| 35 | Zone edit audited with before/after |  | {"code": "", "name": "Floor 1", "parent_id": "a45a5dc8… | PASS |
| 36 | Move zone (with subtree) to another parent |  | zone.created,zone.updated,zone.moved | PASS |
| 37 | Cycle prevention (crafted POST): self as parent | a45a5dc8==a45a5dc8 |  | PASS |
| 38 | Cycle prevention (crafted POST): descendant as parent | a45a5dc8==a45a5dc8 |  | PASS |
| 39 | Cycle prevention (crafted POST): block (root) under its descendant | -==- |  | PASS |
| 40 | Tree 'Active assets' count reflects the asset in the zone | 1 |  | PASS |
| 41 | Deactivate leaf zone (reason stored) |  | zone.created,zone.deactivated | PASS |
| 42 | Reactivate zone clears the reason |  | zone.created,zone.deactivated,zone.reactivated | PASS |
| 43 | Create calendar: days/hours/notes saved; first calendar becomes default | [1, 2, 3, 4, 5]\|08:00:00\|17:00:00\|false\|true\|regular | calendar.created | PASS |
| 44 | 24x7 calendar: all days, no hours | [1, 2, 3, 4, 5, 6, 7]\|-\|true |  | PASS |
| 45 | Calendar edit persisted (name/days/hours/notes) | Day shift v2\|[1, 2, 3, 4, 5, 6]\|07:30:00\|16:30:00\|n2 | calendar.created,calendar.updated | PASS |
| 46 | Delete calendar confirmed |  | calendar.deleted,calendar.deleted | PASS |
| 47 | Add holiday (date+name) persisted |  | calendar.created,calendar.updated,calendar.holiday_add… | PASS |
| 48 | Remove holiday (x button) persisted |  | calendar.created,calendar.updated,calendar.holiday_add… | PASS |
| 49 | Add contact: fields saved, escalation order auto = 1 | 1\|First\|Manager\|+91 1\|first@example.com\|n | site.contact_added,site.contact_added,site.contact_add… | PASS |
| 50 | Escalation order zero (0) rejected cleanly (no server error) | 0 |  | PASS |
| 51 | Escalation order negative (-3) rejected cleanly (no server error) | 0 |  | PASS |
| 52 | Escalation order decimal (1.5) rejected cleanly (no server error) | 0 |  | PASS |
| 53 | Escalation order huge (99999999999) rejected cleanly (no server error) | 0 |  | FAIL |
| 54 | Contact edit: all fields persisted | First Edited\|Director\|+91 99\|e@example.com\|9\|x | site.contact_added,site.contact_updated | PASS |
| 55 | Remove contact confirmed |  | site.contact_removed | PASS |
| 56 | RBAC create site | 0 -> 1 |  | PASS |
| 57 | RBAC edit site | RBAC site 15865 -> RBAC site 15865 by owner |  | PASS |
| 58 | RBAC deactivate site | ACTIVE -> INACTIVE |  | PASS |
| 59 | RBAC create zone | 0 -> 1 |  | PASS |
| 60 | RBAC edit zone | RB zone -> RB zone owner |  | PASS |
| 61 | RBAC deactivate zone | ACTIVE -> INACTIVE |  | PASS |
| 62 | RBAC create calendar | 0 -> 1 |  | PASS |
| 63 | RBAC edit calendar | RB base -> RB base owner |  | PASS |
| 64 | RBAC add holiday | 0 -> 1 |  | PASS |
| 65 | RBAC delete calendar | 1 -> 0 |  | PASS |
| 66 | RBAC add contact | 0 -> 1 |  | PASS |
| 67 | RBAC edit contact | RB contact -> RB contact owner |  | PASS |
| 68 | RBAC create site | 0 -> 1 |  | PASS |
| 69 | RBAC edit site | RBAC site 15865 by owner -> RBAC site 15865 by admin |  | PASS |
| 70 | RBAC deactivate site | ACTIVE -> INACTIVE |  | PASS |
| 71 | RBAC create zone | 0 -> 1 |  | PASS |
| 72 | RBAC edit zone | RB zone owner -> RB zone admin |  | PASS |
| 73 | RBAC deactivate zone | ACTIVE -> INACTIVE |  | PASS |
| 74 | RBAC create calendar | 0 -> 1 |  | PASS |
| 75 | RBAC edit calendar | RB base owner -> RB base admin |  | PASS |
| 76 | RBAC add holiday | 1 -> 2 |  | PASS |
| 77 | RBAC delete calendar | 1 -> 0 |  | PASS |
| 78 | RBAC add contact | 0 -> 1 |  | PASS |
| 79 | RBAC edit contact | RB contact owner -> RB contact admin |  | PASS |
| 80 | RBAC create site | 0 -> 0 |  | PASS |
| 81 | RBAC edit site | RBAC site 15865 by admin -> RBAC site 15865 by admin |  | PASS |
| 82 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 83 | RBAC create zone | 0 -> 0 |  | PASS |
| 84 | RBAC edit zone | RB zone admin -> RB zone admin |  | PASS |
| 85 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 86 | RBAC create calendar | 0 -> 0 |  | PASS |
| 87 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 88 | RBAC add holiday | 2 -> 2 |  | PASS |
| 89 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 90 | RBAC add contact | 0 -> 0 |  | PASS |
| 91 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 92 | RBAC create site | 0 -> 0 |  | PASS |
| 93 | RBAC edit site | RBAC site 15865 by admin -> RBAC site 15865 by admin |  | PASS |
| 94 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 95 | RBAC create zone | 0 -> 0 |  | PASS |
| 96 | RBAC edit zone | RB zone admin -> RB zone admin |  | PASS |
| 97 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 98 | RBAC create calendar | 0 -> 0 |  | PASS |
| 99 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 100 | RBAC add holiday | 2 -> 2 |  | PASS |
| 101 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 102 | RBAC add contact | 0 -> 0 |  | PASS |
| 103 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 104 | RBAC create site | 0 -> 1 |  | PASS |
| 105 | RBAC edit site | RBAC site 15865 by admin -> RBAC site 15865 by assets |  | PASS |
| 106 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 107 | RBAC create zone | 0 -> 1 |  | PASS |
| 108 | RBAC edit zone | RB zone admin -> RB zone assets |  | PASS |
| 109 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 110 | RBAC create calendar | 0 -> 0 |  | PASS |
| 111 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 112 | RBAC add holiday | 2 -> 2 |  | PASS |
| 113 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 114 | RBAC add contact | 0 -> 0 |  | PASS |
| 115 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 116 | RBAC create site | 0 -> 0 |  | PASS |
| 117 | RBAC edit site | RBAC site 15865 by assets -> RBAC site 15865 by assets |  | PASS |
| 118 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 119 | RBAC create zone | 0 -> 0 |  | PASS |
| 120 | RBAC edit zone | RB zone assets -> RB zone assets |  | PASS |
| 121 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 122 | RBAC create calendar | 0 -> 0 |  | PASS |
| 123 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 124 | RBAC add holiday | 2 -> 2 |  | PASS |
| 125 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 126 | RBAC add contact | 0 -> 0 |  | PASS |
| 127 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 128 | RBAC create site | 0 -> 0 |  | PASS |
| 129 | RBAC edit site | RBAC site 15865 by assets -> RBAC site 15865 by assets |  | PASS |
| 130 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 131 | RBAC create zone | 0 -> 0 |  | PASS |
| 132 | RBAC edit zone | RB zone assets -> RB zone assets |  | PASS |
| 133 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 134 | RBAC create calendar | 0 -> 0 |  | PASS |
| 135 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 136 | RBAC add holiday | 2 -> 2 |  | PASS |
| 137 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 138 | RBAC add contact | 0 -> 0 |  | PASS |
| 139 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 140 | RBAC create site | 0 -> 0 |  | PASS |
| 141 | RBAC edit site | RBAC site 15865 by assets -> RBAC site 15865 by assets |  | PASS |
| 142 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 143 | RBAC create zone | 0 -> 0 |  | PASS |
| 144 | RBAC edit zone | RB zone assets -> RB zone assets |  | PASS |
| 145 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 146 | RBAC create calendar | 0 -> 0 |  | PASS |
| 147 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 148 | RBAC add holiday | 2 -> 2 |  | PASS |
| 149 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 150 | RBAC add contact | 0 -> 0 |  | PASS |
| 151 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 152 | RBAC create site | 0 -> 0 |  | PASS |
| 153 | RBAC edit site | RBAC site 15865 by assets -> RBAC site 15865 by assets |  | PASS |
| 154 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 155 | RBAC create zone | 0 -> 0 |  | PASS |
| 156 | RBAC edit zone | RB zone assets -> RB zone assets |  | PASS |
| 157 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 158 | RBAC create calendar | 0 -> 0 |  | PASS |
| 159 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 160 | RBAC add holiday | 2 -> 2 |  | PASS |
| 161 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 162 | RBAC add contact | 0 -> 0 |  | PASS |
| 163 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 164 | RBAC create site | 0 -> 0 |  | PASS |
| 165 | RBAC edit site | RBAC site 15865 by assets -> RBAC site 15865 by assets |  | PASS |
| 166 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 167 | RBAC create zone | 0 -> 0 |  | PASS |
| 168 | RBAC edit zone | RB zone assets -> RB zone assets |  | PASS |
| 169 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 170 | RBAC create calendar | 0 -> 0 |  | PASS |
| 171 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 172 | RBAC add holiday | 2 -> 2 |  | PASS |
| 173 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 174 | RBAC add contact | 0 -> 0 |  | PASS |
| 175 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 176 | RBAC create site | 0 -> 0 |  | PASS |
| 177 | RBAC edit site | RBAC site 15865 by assets -> RBAC site 15865 by assets |  | PASS |
| 178 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 179 | RBAC create zone | 0 -> 0 |  | PASS |
| 180 | RBAC edit zone | RB zone assets -> RB zone assets |  | PASS |
| 181 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 182 | RBAC create calendar | 0 -> 0 |  | PASS |
| 183 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 184 | RBAC add holiday | 2 -> 2 |  | PASS |
| 185 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 186 | RBAC add contact | 0 -> 0 |  | PASS |
| 187 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 188 | RBAC create site | 0 -> 0 |  | PASS |
| 189 | RBAC edit site | RBAC site 15865 by assets -> RBAC site 15865 by assets |  | PASS |
| 190 | RBAC deactivate site | ACTIVE -> ACTIVE |  | PASS |
| 191 | RBAC create zone | 0 -> 0 |  | PASS |
| 192 | RBAC edit zone | RB zone assets -> RB zone assets |  | PASS |
| 193 | RBAC deactivate zone | ACTIVE -> ACTIVE |  | PASS |
| 194 | RBAC create calendar | 0 -> 0 |  | PASS |
| 195 | RBAC edit calendar | RB base admin -> RB base admin |  | PASS |
| 196 | RBAC add holiday | 2 -> 2 |  | PASS |
| 197 | RBAC delete calendar | 1 -> 1 |  | PASS |
| 198 | RBAC add contact | 0 -> 0 |  | PASS |
| 199 | RBAC edit contact | RB contact admin -> RB contact admin |  | PASS |
| 200 | Tenant: Beta cannot open Alpha site detail | 1 -> 1 |  | PASS |
| 201 | Tenant: Beta cannot open Alpha site edit form | 1 -> 1 |  | PASS |
| 202 | Tenant: Beta cannot edit Alpha site (POST) | RBAC site 15865 by assets -> RBAC site 15865 by assets |  | PASS |
| 203 | Tenant: Beta cannot deactivate Alpha site | ACTIVE -> ACTIVE |  | PASS |
| 204 | Tenant: Beta cannot create a zone in an Alpha site | 4 -> 4 |  | PASS |
| 205 | Tenant: Beta cannot edit an Alpha zone | RB zone assets -> RB zone assets |  | PASS |
| 206 | Tenant: Beta cannot open an Alpha zone edit form | 1 -> 1 |  | PASS |
| 207 | Tenant: Beta cannot deactivate an Alpha zone | ACTIVE -> ACTIVE |  | PASS |
| 208 | Tenant: Beta cannot create an Alpha calendar | 13 -> 13 |  | PASS |
| 209 | Tenant: Beta cannot edit an Alpha calendar | RB base admin -> RB base admin |  | PASS |
| 210 | Tenant: Beta cannot delete an Alpha calendar | 1 -> 1 |  | PASS |
| 211 | Tenant: Beta cannot add an Alpha holiday | 2 -> 2 |  | PASS |
| 212 | Tenant: Beta cannot add an Alpha contact | 3 -> 3 |  | PASS |
| 213 | Tenant: Beta cannot edit an Alpha contact | RB contact admin -> RB contact admin |  | PASS |
| 214 | Tenant: Alpha cannot open Beta site detail | 1 -> 1 |  | PASS |
| 215 | Tenant: Alpha cannot edit Beta site (POST) | Pune Plant -> Pune Plant |  | PASS |
| 216 | Tenant: Alpha cannot deactivate Beta site | ACTIVE -> ACTIVE |  | PASS |
| 217 | Tenant: Alpha cannot create a zone in a Beta site | 3 -> 3 |  | PASS |
| 218 | Tenant: Alpha cannot edit a Beta zone | Beta zone 15865 -> Beta zone 15865 |  | PASS |
| 219 | Tenant: Alpha cannot open a Beta zone edit form | 1 -> 1 |  | PASS |
| 220 | Tenant: Alpha cannot deactivate a Beta zone | ACTIVE -> ACTIVE |  | PASS |
| 221 | Tenant: Alpha cannot edit a Beta calendar | Beta cal 15865 -> Beta cal 15865 |  | PASS |
| 222 | Tenant: Alpha cannot delete a Beta calendar | 1 -> 1 |  | PASS |
| 223 | Tenant: Alpha cannot add a Beta holiday | 0 -> 0 |  | PASS |
| 224 | Tenant: Alpha cannot edit a Beta contact | Beta contact 15865 -> Beta contact 15865 |  | PASS |
| 225 | Tenant: Alpha cannot add a Beta contact | 2 -> 2 |  | PASS |
| 226 | Audit trail lists M01 events for the site (owner) |  | site.created,site.updated,site.deactivated,site.reacti… | PASS |
| 227 | Audit rows exist for edits made through the browser |  | calendar.created,calendar.holiday_added,calendar.updat… | PASS |
| 228 | Anonymous POST /app/sites/new/ is refused (login redirect / 403) and changes nothing | 0 -> 0 |  | PASS |
| 229 | Anonymous POST /app/sites/{id}/ is refused (login redirect / 403) and changes nothing | ACTIVE -> ACTIVE |  | PASS |
| 230 | Anonymous POST /app/locations/{id}/status/ is refused (login redirect / 403) and changes nothi… | ACTIVE -> ACTIVE |  | PASS |
| 231 | Anonymous POST /app/calendars/{id}/delete/ is refused (login redirect / 403) and changes nothi… | 1 -> 1 |  | PASS |

## 8. HTMX

HTMX requests observed: `GET /app/notifications/bell/` x481. Failures observed: 0 (all injected on purpose: `-`). 5/5 HTMX-related checks PASS.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Tree shows hierarchy with child after parent | owner | PASS | Block A then Floor 1 -> ['Block A', 'Floor 1', 'Service Bay', 'Yard'] |
| 2 | Tree columns Type/Code/Active assets/Status populated | owner | PASS | values -> ['Block A', 'Building', 'BLK-A', '0', 'Active', 'Add child Edit \nDeactivate'] |
| 3 | Edit visible in tree after reload | owner | PASS | Floor One -> ok |
| 4 | Move zone (with subtree) to another parent | owner | PASS | moved -> Yard |
| 5 | Tree 'Active assets' count reflects the asset in the zone | owner | PASS | 1 -> ['Block A', 'Building', 'BLK-A', '1', 'Active', 'Add child Edit \nDeactivate'] |

## 9. Error handling

Deliberately provoked errors (forged ids, unauthorised roles, invalid input, foreign tenants) were answered with 400/403/404/405/409-style refusals and a visible message, never a stack trace; the one exception is listed in section 13. Provoked responses are counted separately from unexplained errors:

| Provoked response | Count |
|---|---|
| 403 GET /app/sites/{id}/calendars/new/ | 10 |
| 403 GET /app/calendars/{id}/edit/ | 10 |
| 403 GET /app/sites/{id}/contacts/new/ | 10 |
| 403 GET /app/contacts/{id}/edit/ | 10 |
| 403 POST /app/sites/{id}/ body=action=deactivate&reason=rbac | 10 |
| 403 POST /app/locations/{id}/status/ body=action=deactivate& | 10 |
| 403 POST /app/calendars/{id}/holidays/ body=action=add&date= | 10 |
| 403 POST /app/calendars/{id}/delete/ body= | 10 |
| 403 GET /app/sites/new/ | 9 |
| 403 GET /app/sites/{id}/edit/ | 9 |
| 403 GET /app/sites/{id}/locations/new/ | 9 |
| 403 GET /app/locations/{id}/edit/ | 9 |
| 403 POST /app/sites/{id}/edit/ body=code=RB15865&name=RBAC+s | 9 |
| 400 POST /app/sites/new/ body=code=V14910x&name=Validation+s | 6 |

45/46 error/negative-path checks PASS.

## 10. Responsive / keyboard / modal behaviour

68/70 responsive and usability checks PASS. Method: for each page and viewport the page's `scrollWidth` is compared with the window width, elements wider than the window and clipped buttons/inputs are listed (tables inside `.table-responsive` may scroll internally).

| Page | 1920x1080 | 1440x900 | 1024x768 | 390x844 |
|---|---|---|---|---|
| Site list | PASS | PASS | PASS | PASS |
| New site | PASS | PASS | PASS | PASS |
| Site detail overview | PASS | PASS | PASS | PASS |
| Locations tab | PASS | PASS | PASS | PASS |
| Calendars tab | PASS | PASS | PASS | PASS |
| Contacts tab | PASS | PASS | PASS | PASS |
| Assets tab | PASS | PASS | PASS | PASS |
| Site edit | PASS | PASS | PASS | PASS |
| New location | PASS | PASS | PASS | PASS |
| Edit location | PASS | PASS | PASS | PASS |
| New calendar | PASS | PASS | PASS | PASS |
| Edit calendar | PASS | PASS | PASS | PASS |
| New contact | PASS | PASS | PASS | PASS |
| Edit contact | PASS | PASS | PASS | PASS |

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Mobile navigation reachable at 390px | owner | PASS | reachable -> no toggle found; nav visible=True |
| 2 | Keyboard: 'skip to content' link present (sidebar has ~35 tab stops before the page content) | owner | PARTIAL | skip link available -> skip links=0 |
| 3 | Keyboard: Tab reaches the site form fields in order | owner | PASS | code/name reached -> ['code', 'name', 'description', 'address', 'city', 'state_region', 'postal_code', 'country', 'timezone', 'contact_name', 'contact_email', 'contact_phone', 'Cr… |
| 4 | Keyboard: focused controls show a visible focus indicator | owner | PASS | outline or shadow on focus -> all visible |
| 5 | Confirm modal fits the 390x844 viewport | owner | PASS | within viewport -> {'x': 15.59375, 'y': 346.71875, 'width': 358.796875, 'height': 150.5625} |
| 6 | Confirm modal closes with Escape | owner | PASS | closed -> True |
| 7 | Mobile: inline validation errors are rendered and visible | owner | PASS | errors visible -> True |
| 8 | Mobile: success message visible after save | owner | PASS | message shown -> True |
| 9 | Mobile: sidebar collapsed by default at 390px | owner | PASS | nav hidden until menu tapped -> visible nav links=0 |
| 10 | Mobile: hamburger opens the navigation | owner | PASS | nav visible -> visible=1 |
| 11 | Mobile: open menu causes no horizontal overflow | owner | PASS | no overflow -> 390 |
| 12 | Mobile: menu link navigates | owner | PASS | navigates -> http://127.0.0.1:8098/app/sites/ |
| 13 | Mobile: Escape closes the open menu (a11y) | owner | PARTIAL | closed -> visible=1 |
| 14 | Mobile: wide table scrolls inside its own container (page does not) | owner | PASS | overflow-x auto -> {'sw': 911, 'cw': 356, 'scrolls': True, 'ox': 'auto'} |

## 11. Console / network result

Console errors, page errors, failed requests and 4xx/5xx recorded outside the harness' 'provoked error' window: 3, of which **1 unexplained** and 2 are 400/404 answers to the scripted negative probes (forged id, foreign tenant, invalid input) whose console line was emitted after the suppression window closed. JavaScript page errors: 0.

Unexplained:

| Kind | Message | Count |
|---|---|---|
| console | Failed to load resource: the server responded with a status of 404 (Not Found) | 1 |

Explained (deliberate negative probes):

| Kind | Message | Count |
|---|---|---|
| http | 404 GET /api/v1/sites/{id}/ | 1 |
| console | Failed to load resource: the server responded with a status of 404 (Not Found) | 1 |

Provoked (expected) problems recorded inside the suppression window: 574; aborted requests of the polling notification bell during navigation (benign, not errors): 15; failed static assets: 0.

Notes: `GET /favicon.ico 404` (if listed) is reported as BX-ALL-02 (cosmetic).

## 12. Integration result

- Site -> Zone -> Asset (M02): the asset form offers only ACTIVE zones of ACTIVE sites; choosing a site narrows the zones; the asset page shows its zone; the zone tree counts and blocks deactivation for zones holding ACTIVE assets (PASS).
- Site/zone deactivation rules enforced against children and assets (PASS). Calendar -> M04: the generated work order's planned window moved from Sunday to Monday because the site's default calendar is Mon-Fri (PASS, see M04).
- Contact hierarchy is data only in this batch (escalation consumers are in M05/M13).

## 13. Findings

Counts for this module: Critical 0, High 0, Medium 1, Low 4, Cosmetic 1, Unverified 0.

| ID | Severity | Title | Status |
|---|---|---|---|
| BX-M01-01 | MEDIUM | Site-contact escalation order above 32767 returns HTTP 500 (UI form and API) | OPEN |
| BX-ALL-01 | LOW | Keyboard / mobile navigation accessibility: no 'skip to content' link; off-canvas sidebar links stay focusable while hidden; Esc does not c… | OPEN |
| BX-M01-02 | LOW | Deactivate site / location: the confirmation dialog opens before the mandatory reason is validated | OPEN |
| BX-M01-03 | LOW | Sites and locations have no history/audit view of their own (only the global Audit Trail) | OPEN |
| BX-M01-04 | LOW | Site list has no sorting controls (fixed order by code) | OPEN |
| BX-ALL-02 | COSMETIC | Every fresh browser session logs 'GET /favicon.ico -> 404' in the console (no favicon served) | OPEN |

### BX-M01-01 - MEDIUM - Site-contact escalation order above 32767 returns HTTP 500 (UI form and API)

- **Module:** M01
- **Page / URL:** /app/sites/{id}/contacts/new/ (and POST /api/v1/site-contacts/)
- **Role:** owner
- **Action:** Add contact with name, phone and escalation order 99999999999
- **Expected:** 400 re-render with an inline error ('Ensure this value is less than or equal to ...'), nothing saved.
- **Actual:** HTTP 500 'Server Error' page; API answers 500 as well. Log: django.db.utils.DataError: smallint out of range.
- **API / HTMX / network:** POST /app/sites/{id}/contacts/new/ -> 500; POST /api/v1/site-contacts/ -> 500
- **Console:** Failed to load resource: 500 (provoked)
- **Screenshot:** (error page, no screenshot needed - see run row)
- **Source location:** src/apps/sites/forms.py:70 and src/apps/sites/api_views.py:136 (IntegerField min_value=1, no max_value) vs src/apps/sites/models.py:130 (PositiveSmallIntegerField); error raised in services.add_contact -> _save (services.py:410-416)
- **Status:** OPEN
- **Run evidence:** [FAIL] Escalation order huge (99999999999) rejected cleanly (no server error) -> http=500; Server Error page

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
- **Run evidence:** [PARTIAL] Keyboard: 'skip to content' link present (sidebar has ~35 tab stops before the … -> skip links=0

### BX-M01-02 - LOW - Deactivate site / location: the confirmation dialog opens before the mandatory reason is validated

- **Module:** M01
- **Page / URL:** /app/sites/{id}/ and ?tab=locations
- **Role:** owner
- **Action:** Click Deactivate with an empty reason
- **Expected:** Reason validated before (or inside) the confirmation.
- **Actual:** Dialog opens first; after Confirm the browser focuses the empty required reason field (no data change). Cosmetic UX order only.
- **API / HTMX / network:** -
- **Console:** none
- **Screenshot:** -
- **Source location:** src/templates/sites/detail.html:12
- **Status:** OPEN
- **Run evidence:** [PARTIAL] Deactivate without reason: browser validation -> confirm dialog opened first=True; after Confirm the form is not submitted and focus jumps to the reason field; status=ACTIVE; [PASS] Deactivate without reason refused (server) -> 200

### BX-M01-03 - LOW - Sites and locations have no history/audit view of their own (only the global Audit Trail)

- **Module:** M01
- **Page / URL:** /app/sites/{id}/ (tabs: Overview, Locations, Calendars, Contacts, Assets)
- **Role:** owner/auditor
- **Action:** Look for a History tab as assets have
- **Expected:** HPE M01 traceability: history of changes reachable from the site.
- **Actual:** No History tab; events are visible only in /app/audit/?q=<code> (verified present for owner and auditor).
- **API / HTMX / network:** -
- **Console:** none
- **Screenshot:** -
- **Source location:** src/templates/sites/detail.html
- **Status:** OPEN
- **Run evidence:** [PARTIAL] Site detail 'History' tab -> No history tab on site detail (tabs: Overview/Locations/Calendars/Contacts/Assets); site history is only visible in the global Audit Trail …

### BX-M01-04 - LOW - Site list has no sorting controls (fixed order by code)

- **Module:** M01
- **Page / URL:** /app/sites/
- **Role:** owner
- **Action:** Look for sortable column headers / ?ordering=
- **Expected:** Sortable list (task scope lists sorting).
- **Actual:** Headers are plain text; ?ordering= is ignored; rows are ordered by site code (verified equal to the database order).
- **API / HTMX / network:** -
- **Console:** none
- **Screenshot:** -
- **Source location:** src/apps/sites/selectors.py:69 (order_by('code')), src/templates/sites/list.html
- **Status:** OPEN
- **Run evidence:** [PARTIAL] Site list column sorting -> No sort controls (header links=0); fixed order by code (first rows ['14682ZZZZZZZZZZZZZZZZZZZZZZZZZ', '14754ZZZZZZZZZZZZZZZZZZZZZZZZZ', '14…

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

## 14. Evidence

- Raw per-run result files (every row, console/network capture, click and request coverage): `evidence/M01_run_sites.json`, `evidence/M01_run_zones_calendars_contacts.json`, `evidence/M01_run_rbac_tenant_audit_links_responsive.json`, `evidence/M01_run_mobile_menu.json`, `evidence/M01_run_sorting.json`, `evidence/M01_run_anonymous_session.json`
- Discovery inventory (all pages/links/buttons/forms/tables/HTMX of M01-M04): `evidence/inventory_owner.json`; coverage computation: `evidence/coverage.json`
- Screenshots: `evidence/shots/M01_desktop_detail.png`, `evidence/shots/M01_laptop_detail.png`, `evidence/shots/M01_mobile_detail.png`, `evidence/shots/M01_mobile_menu_open.png`, `evidence/shots/M01_mobile_modal.png`, `evidence/shots/M01_mobile_nomenu.png`, `evidence/shots/M01_mobile_success.png`, `evidence/shots/M01_mobile_validation.png`, `evidence/shots/M01_tablet_detail.png`
- Scripts (Playwright, Python): `tools/playwright/` (m01a.py, m01b.py, m01c.py, m01d.py)
- Provoked-error and benign-abort logs are stored in the run files under `expected` and `benign`.

## 15. Final module status

**M01: PARTIAL (defect reproduced).** 731/738 checks PASS; 1 FAIL; 6 PARTIAL; 0 UNVERIFIED; 3 not applicable.
Open findings: BX-M01-01 (MEDIUM), BX-ALL-01 (LOW), BX-M01-02 (LOW), BX-M01-03 (LOW), BX-M01-04 (LOW), BX-ALL-02 (COSMETIC).
All M01 functionality exposed in the UI works and persists; the one reproduced defect is a server error on an absurdly large escalation order (BX-M01-01, Medium). Remaining items are Low accessibility/UX observations.
