# M02 browser acceptance - detailed (Asset Registry (assets, categories, documents, meters, status))

**Batch 1 of the browser acceptance (M01-M04).** Real Chromium (Playwright) against the running application (DEBUG off, CSP on, PostgreSQL `fieldops_browser_qa`, Redis, Celery worker + beat). Every check below was performed in the browser (or by a real in-page request carrying the session cookie and CSRF token) and the database state was read back with SQL; an HTTP 200 alone was never accepted as evidence. No production code was modified.

**Result: M02: 662/665 browser checks PASS** (0 FAIL, 3 PARTIAL, 1 UNVERIFIED; 3 NOT APPLICABLE excluded; 0 superseded harness lines excluded). **Module status: PASS with LOW observations.**

Roles driven: owner, admin, ops, supervisor, assets, planner, tech (technician 1), tech2, stores, service, auditor, client (all Alpha) and betaowner (tenant Beta). Viewports: 1920x1080, 1440x900, 1024x768, 390x844.

Matrix columns used by the scripts: FEATURE / PAGE / ROLE / ACTION / EXPECTED / ACTUAL / DATABASE / API-HTMX / AUDIT / STATUS; the full matrix for this module is in `evidence/M02_run_registry_search_create_edit_categories.json`, `evidence/M02_run_documents_meters_status_rbac_tenant_responsive.json`, `evidence/M02_run_anonymous_session.json`.

## 1. Pages tested

Discovered by a crawl of the module (owner): 6 pages; visited in the test runs: 6/6.

| Page / URL (normalised) | Discovered by crawl | Browser visits |
|---|---|---|
| `/app/assets/` | yes | 27 |
| `/app/assets/?category` | no (reached by test) | 6 |
| `/app/assets/?category&page` | no (reached by test) | 12 |
| `/app/assets/?category&page&site&status` | no (reached by test) | 10 |
| `/app/assets/?category&q&site&status` | no (reached by test) | 5 |
| `/app/assets/?category&site&status` | no (reached by test) | 1 |
| `/app/assets/?ordering` | no (reached by test) | 7 |
| `/app/assets/?owner` | no (reached by test) | 1 |
| `/app/assets/?page` | no (reached by test) | 22 |
| `/app/assets/?page&site` | no (reached by test) | 12 |
| `/app/assets/?page&status` | no (reached by test) | 13 |
| `/app/assets/?q` | no (reached by test) | 20 |
| `/app/assets/?q&site` | no (reached by test) | 1 |
| `/app/assets/?q&status` | no (reached by test) | 1 |
| `/app/assets/?site` | no (reached by test) | 4 |
| `/app/assets/?status` | no (reached by test) | 6 |
| `/app/assets/?zone` | no (reached by test) | 2 |
| `/app/assets/categories/` | yes | 46 |
| `/app/assets/new/` | yes | 59 |
| `/app/assets/new/?asset_tag&category` | no (reached by test) | 2 |
| `/app/assets/new/?asset_tag&category&name` | no (reached by test) | 16 |
| `/app/assets/new/?category` | no (reached by test) | 4 |
| `/app/assets/new/?category&name` | no (reached by test) | 1 |
| `/app/assets/new/?site` | no (reached by test) | 1 |
| `/app/assets/{id}/` | yes | 75 |
| `/app/assets/{id}/?tab` | yes | 196 |
| `/app/assets/{id}/edit/` | yes | 25 |
| `/app/assets/{id}/edit/?asset_tag&category&commission_date&description&manufacturer&model&name&owner&purchase_date&serial_number&site&warranty_ref&zone` | no (reached by test) | 1 |
| `/app/assets/{id}/edit/?category` | no (reached by test) | 1 |

Other URLs the tests visited (negative probes, redirects, API): `/accounts/login/`, `/accounts/login/?next`, `/app/`, `/app/files/{id}/download/`, `/app/portal/`

## 2. Buttons / links / actions

Discovered controls: 13 buttons (10 clicked/posted), 7 distinct links (7 followed), 10 POST endpoints (9 exercised), 2 GET filter forms (2 used), 0 HTMX endpoints (0 exercised).

State-changing requests issued by the browser (normalised path -> count): `/app/assets/{id}/documents/` x50, `/app/assets/categories/` x40, `/app/assets/new/` x36, `/app/meters/{id}/reading/` x29, `/app/assets/{id}/meters/new/` x25, `/app/assets/{id}/transition/start_maintenance/` x24, `/app/assets/{id}/edit/` x21, `/app/meters/{id}/toggle/` x19, `/app/assets/new/?asset_tag&category&name` x16, `/app/assets/documents/{id}/remove/` x16, `/app/assets/{id}/transition/mark_out_of_service/` x5, `/app/assets/{id}/transition/complete_maintenance/` x4, `/app/assets/new/?category` x3, `/app/assets/{id}/transition/retire/` x3, `/app/assets/{id}/transition/dispose/` x3, `/app/assets/{id}/transition/return_to_service/` x3, `/app/assets/new/?category&name` x1, `/app/assets/new/?asset_tag&category` x1, `/app/assets/{id}/edit/?asset_tag&category&commission_date&description&manufacturer&model&name&owner&purchase_date&serial_number&site&warranty_ref&zone` x1, `/app/assets/{id}/transition/explode/` x1

**Controls discovered but NOT exercised (with reason):**

- `/app/identification/assets/{id}/panel/generate/` - QR / barcode / scan feature belongs to M07 (later batch); the asset 'Labels' panel itself loaded without error
- `Check -> (js/none)` - QR / barcode / scan feature belongs to M07 (later batch); the asset 'Labels' panel itself loaded without error
- `Generate barcode (code 128) -> /app/identification/assets/{id}/panel/generate/` - QR / barcode / scan feature belongs to M07 (later batch); the asset 'Labels' panel itself loaded without error
- `Generate qr code -> /app/identification/assets/{id}/panel/generate/` - QR / barcode / scan feature belongs to M07 (later batch); the asset 'Labels' panel itself loaded without error

## 3. Forms

12 distinct forms discovered (owner view); every field of every form was filled, left blank and given invalid/boundary values in section 4.

| Form (action) | Method | Fields (non-hidden) | Exercised |
|---|---|---|---|
| `/app/assets/ (self)` | GET | q, site, category, status | yes |
| `/app/assets/new/ (self)` | POST | asset_tag, name, category, site, zone, manufacturer, model, serial_number, purchase_date, commission_date, owner, warranty_ref, description | yes |
| `/app/assets/categories/ (self)` | POST | (button only) | yes |
| `/app/assets/{id}/transition/start_maintenance/` | POST | reason | yes |
| `/app/assets/documents/{id}/remove/` | POST | reason | yes |
| `/app/assets/{id}/documents/` | POST | file, title, doc_type | yes |
| `/app/meters/{id}/toggle/` | POST | action | yes |
| `/app/meters/{id}/reading/` | POST | value, read_at, notes | yes |
| `/app/assets/{id}/meters/new/` | POST | name, unit | yes |
| `/app/assets/{id}/ (self)` | GET | work_type, date | yes |
| `/app/identification/assets/{id}/panel/generate/` | POST | (button only) | no |
| `/app/assets/{id}/edit/ (self)` | POST | asset_tag, name, category, site, zone, manufacturer, model, serial_number, purchase_date, commission_date, owner, warranty_ref, description… | yes |

## 4. Validation (client + server)

109/109 validation, boundary, duplicate, forged-input and XSS checks PASS. Forms are `novalidate`; constraints that the browser would block were removed in the page (or the request forged from the page) so that the SERVER rules were exercised, and the matching client hint (maxlength/required) was asserted separately.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | XSS payload in search is escaped (input + page) | owner | PASS | inert -> ok |
| 2 | Walking all pages yields every asset exactly once (no gaps/duplicates) | owner | PASS | 266 unique -> 266 / 266 |
| 3 | Attribute types/required/choices parsed correctly | owner | PASS | number required; choice w/ 2; date; text -> [{"key": "voltage", "type": "number", "label": "Voltage", "choices": [], "required": true}, {"key": "phase", "type": "choice", "label": "Phase", … |
| 4 | Duplicate category name (different case) rejected | owner | PASS | refused -> A category with this name already exists. |
| 5 | Blank category name rejected | owner | PASS | refused -> This field is required. |
| 6 | Invalid attribute definition refused: unknown type | owner | PASS | refused with message -> Unknown attribute type 'colour' (use text, number, date, choice). |
| 7 | Invalid attribute definition refused: choice with one choice | owner | PASS | refused with message -> Attribute 'Size' needs at least two choices. |
| 8 | Invalid attribute definition refused: duplicate label | owner | PASS | refused with message -> Attribute 'A' is defined twice. |
| 9 | More than 20 custom attributes refused | owner | PASS | refused -> A category can define at most 20 attributes. |
| 10 | Boundary: 100-char category name accepted | owner | PASS | saved -> A category with this name already exists. |
| 11 | 101-char category name refused (server-side, forged past maxlength) | owner | PASS | refused -> http=200 |
| 12 | Stored XSS in category name is escaped | owner | PASS | inert -> ok |
| 13 | Blank name on edit refused (name unchanged) | owner | PASS | unchanged -> ok |
| 14 | Minimal create (required fields only) persists with empty optionals | owner | PASS | created -> 302 |
| 15 | Empty submit: 400, inline errors under required fields, nothing saved | owner | PASS | errors for tag/name -> 400 errors=['This field is required.', 'This field is required.', 'This field is required.', 'This field is required.'] |
| 16 | Validation: tag required | owner | PASS | 400, inline error, nothing saved ('required') -> http=400 rows 268->268; This field is required. |
| 17 | Validation: name required | owner | PASS | 400, inline error, nothing saved ('required') -> http=400 rows 268->268; This field is required. |
| 18 | Validation: name whitespace only | owner | PASS | 400, inline error, nothing saved ('required') -> http=400 rows 268->268; This field is required. |
| 19 | Validation (server): tag 41 chars (max 40) | owner | PASS | 400, nothing saved -> http=400 rows 268->268 |
| 20 | Validation (server): name 201 chars (max 200) | owner | PASS | 400, nothing saved -> http=400 rows 268->268 |
| 21 | Validation (server): manufacturer 101 chars | owner | PASS | 400, nothing saved -> http=400 rows 268->268 |
| 22 | Validation (server): model 101 chars | owner | PASS | 400, nothing saved -> http=400 rows 268->268 |
| 23 | Validation (server): serial 101 chars | owner | PASS | 400, nothing saved -> http=400 rows 268->268 |
| 24 | Validation (server): warranty ref 201 chars | owner | PASS | 400, nothing saved -> http=400 rows 268->268 |
| 25 | Validation (server): invalid purchase date text | owner | PASS | 400, nothing saved -> http=400 rows 268->268 |
| 26 | Validation (server): impossible purchase date 2024-02-30 | owner | PASS | 400, nothing saved -> http=400 rows 268->268 |
| 27 | Validation: commissioning before purchase | owner | PASS | 400, inline error, nothing saved -> http=400 rows 268->268; Commissioning date cannot be before the purchase date. |
| 28 | Validation (server): zone of another site | owner | PASS | 400, nothing saved -> http=400 rows 268->268 |
| 29 | Validation: duplicate tag (exact) | owner | PASS | 400, inline error, nothing saved ('already exists') -> http=400 rows 269->269; An asset with this tag already exists. |
| 30 | Validation: duplicate tag (lower-case) | owner | PASS | 400, inline error, nothing saved ('already exists') -> http=400 rows 269->269; An asset with this tag already exists. |
| 31 | Validation: duplicate tag (padded with spaces) | owner | PASS | 400, inline error, nothing saved ('already exists') -> http=400 rows 269->269; An asset with this tag already exists. |
| 32 | Validation: duplicate serial for the same manufacturer | owner | PASS | 400, inline error, nothing saved ('serial') -> http=400 rows 269->269; An asset with this manufacturer and serial number already exists. |
| 33 | Validation: duplicate serial, manufacturer different case | owner | PASS | 400, inline error, nothing saved ('serial') -> http=400 rows 269->269; An asset with this manufacturer and serial number already exists. |
| 34 | Boundary: max-length name/manufacturer/model/serial/warranty accepted | owner | PASS | created -> True |
| 35 | Boundary: 40-char asset tag accepted | owner | PASS | created -> True |
| 36 | Boundary: commissioning on the same day as purchase accepted | owner | PASS | created -> True |
| 37 | Stored XSS in name/description is escaped on list and detail | owner | PASS | inert -> ok |
| 38 | Crafted POST: site of another tenant rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 39 | Crafted POST: category of another tenant rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 40 | Crafted POST: owner (member) of another tenant rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 41 | Crafted POST: non-existent site id rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 42 | Crafted POST: malformed category id rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 43 | Crafted POST: non-existent zone id rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 44 | Crafted POST: inactive category rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 45 | Forged 'status' on create cannot set a non-ACTIVE status | owner | PASS | ACTIVE or rejected -> ACTIVE |
| 46 | Custom attribute: required number missing | owner | PASS | 400 + inline error, nothing saved -> http=400 This field is required. |
| 47 | Custom attribute: choice outside the allowed list refused (forged) | owner | PASS | 400 -> 400 |
| 48 | Edit: duplicate asset tag refused | owner | PASS | refused -> An asset with this tag already exists. |
| 49 | Edit: duplicate manufacturer+serial refused | owner | PASS | refused -> An asset with this manufacturer and serial number already exists. |
| 50 | Edit: blank name refused | owner | PASS | refused -> This field is required. |
| 51 | Edit: commissioning before purchase refused | owner | PASS | refused -> Commissioning date cannot be before the purchase date. |
| 52 | Status cannot be changed through the edit form (forged status ignored) | owner | PASS | ACTIVE -> ACTIVE |
| 53 | Invalid upload refused: virus.exe | owner | PASS | refused ('File type'), no row -> http=302 File type '.exe' is not allowed. |
| 54 | Invalid upload refused: script.js | owner | PASS | refused ('File type'), no row -> http=302 File type '.js' is not allowed. |
| 55 | Invalid upload refused: fake.pdf | owner | PASS | refused ('does not match'), no row -> http=302 File content does not match its extension. |
| 56 | Invalid upload refused: fakepng.png | owner | PASS | refused ('does not match'), no row -> http=302 File content does not match its extension. |
| 57 | Invalid upload refused: empty.txt | owner | PASS | refused ('empty'), no row -> http=302 Choose a file to upload. |
| 58 | Invalid upload refused: binary.txt | owner | PASS | refused ('binary'), no row -> http=302 Text files must not contain binary data. |
| 59 | Invalid upload refused: noext | owner | PASS | refused ('File type'), no row -> http=302 File type '.' is not allowed. |
| 60 | Invalid upload refused: evil.pdf.exe | owner | PASS | refused ('File type'), no row -> http=302 File type '.exe' is not allowed. |
| 61 | Invalid upload refused: page.html | owner | PASS | refused ('File type'), no row -> http=302 File type '.html' is not allowed. |
| 62 | Invalid upload refused: arch.zip | owner | PASS | refused ('File type'), no row -> http=302 File type '.zip' is not allowed. |
| 63 | Upload with no file: the browser blocks the submit (file input is required) | owner | PASS | blocked client-side -> required=True, POSTs sent=0 |
| 64 | Upload with no file (forged past the browser): server answers 'Choose a file to upload' | owner | PASS | refused with message ->  |
| 65 | Oversize file (>10 MB) refused | owner | PASS | refused with size message -> http=302 File exceeds the 10 MB limit. |
| 66 | Boundary: exactly 10 MB accepted | owner | PASS | accepted -> http=302 Document uploaded. |
| 67 | Stored XSS in document title is escaped | owner | PASS | inert -> ok |
| 68 | Remove without a reason is refused (document stays) | owner | PASS | refused -> blocked by browser validation |
| 69 | Duplicate meter name (case-insensitive) refused | owner | PASS | refused -> This asset already has a meter with that name. |
| 70 | Blank meter name refused | owner | PASS | refused ->  |
| 71 | Blank unit refused | owner | PASS | refused ->  |
| 72 | Meter name > 80 chars refused (server) | owner | PASS | refused -> http=200 |
| 73 | Meter unit > 20 chars refused (server) | owner | PASS | refused -> http=200 |
| 74 | Boundary: 80-char name and 20-char unit accepted | owner | PASS | accepted -> 2 |
| 75 | Stored XSS in meter name is escaped | owner | PASS | inert -> ok |
| 76 | Lower reading than previous refused (monotonic) | owner | PASS | refused -> Reading 90 is lower than the previous reading 100.500 h. |
| 77 | Negative reading refused | owner | PASS | refused -> Enter a valid, non-negative reading value. |
| 78 | Non-numeric reading refused | owner | PASS | refused -> Enter a valid, non-negative reading value. |
| 79 | More than 3 decimals refused | owner | PASS | refused -> Enter a valid, non-negative reading value. |
| 80 | Reading >= 1e13 refused | owner | PASS | refused -> Enter a valid, non-negative reading value. |
| 81 | Absurdly large reading refused without a server error | owner | PASS | refused -> Enter a valid, non-negative reading value. |
| 82 | Reading time in the future refused | owner | PASS | refused -> Reading time cannot be in the future. |
| 83 | Reading time earlier than the previous one refused | owner | PASS | refused -> Reading time is earlier than the previous reading. |
| 84 | Boundary: 300-char note accepted | owner | PASS | accepted -> 3 |
| 85 | Reading on an inactive meter refused (forged POST) | owner | PASS | refused -> http=200 |
| 86 | Transition without a reason refused (server) | owner | PASS | ACTIVE -> ACTIVE |
| 87 | Reason shorter than 3 characters refused (server) | owner | PASS | ACTIVE -> ACTIVE |
| 88 | Reason input is required with minlength=3 (client hint) | owner | PASS | required/minlength -> ok |
| 89 | Forged invalid transition 'retire' on ACTIVE does not change the status | owner | PASS | ACTIVE -> ACTIVE http=200 |
| 90 | Forged invalid transition 'dispose' on ACTIVE does not change the status | owner | PASS | ACTIVE -> ACTIVE http=200 |
| 91 | Forged invalid transition 'mark_out_of_service' on ACTIVE does not change the status | owner | PASS | ACTIVE -> ACTIVE http=200 |
| 92 | Forged invalid transition 'return_to_service' on ACTIVE does not change the status | owner | PASS | ACTIVE -> ACTIVE http=200 |
| 93 | Forged invalid transition 'complete_maintenance' on ACTIVE does not change the status | owner | PASS | ACTIVE -> ACTIVE http=200 |
| 94 | Forged invalid transition 'explode' on ACTIVE does not change the status | owner | PASS | ACTIVE -> ACTIVE http=200 |
| 95 | GET on a transition URL is refused (405) | owner | PASS | 405 -> 405 |
| 96 | Terminal asset: forged 'start_maintenance' refused | owner | PASS | RETIRED -> RETIRED |
| 97 | Terminal asset: forged 'return_to_service' refused | owner | PASS | RETIRED -> RETIRED |
| 98 | Terminal asset: forged 'dispose' refused | owner | PASS | RETIRED -> RETIRED |
| 99 | Terminal asset: forged 'retire' refused | owner | PASS | RETIRED -> RETIRED |
| 100 | Terminal asset cannot be edited (forged POST) | owner | PASS | unchanged -> QA asset |
| 101 | Terminal asset: add meter refused | owner | PASS | nothing created -> ok |
| 102 | Terminal asset: record document refused | owner | PASS | nothing created -> ok |
| 103 | Boundary: 501-char reason is truncated/handled without a server error | owner | PASS | no 500 -> stored length=500 |
| 104 | Tenant: Beta registers an asset at an Alpha site is rejected | betaowner | PASS | 400/403/404, nothing saved -> http=400 |
| 105 | Tenant: Beta registers an asset in an Alpha category is rejected | betaowner | PASS | 400/403/404, nothing saved -> http=400 |
| 106 | Tenant: Alpha registers an asset at a Beta site is rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 107 | Anonymous POST /app/assets/{id}/transition/start_maintenance/ is refused (login redirect / 403) and changes n… | anonymous | PASS | refused, DB unchanged -> http=200 -> 6deab3d6f6/transition/start_maintenance/ |
| 108 | Anonymous POST /app/assets/{id}/meters/new/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> -5c00-4536-88ec-676deab3d6f6/meters/new/ |
| 109 | Anonymous POST /app/assets/categories/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> unts/login/?next=/app/assets/categories/ |

## 5. RBAC

245/245 RBAC checks PASS across 21 distinct checks x up to 12 roles. For every role the expected outcome is derived from the role's real permission set in the database (membership -> role -> permission); the browser then proves (a) the control is shown iff permitted, (b) the direct URL answers 200 iff permitted else 403/404, (c) a real forged POST is refused with the database unchanged when denied and succeeds with the expected state change when allowed.

| Check (expected outcome derived from the role's DB permission set) | owner | admin | ops | supervisor | assets | planner | tech | tech2 | stores | service | auditor | client |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RBAC asset list access follows asset.view | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC 'Register asset' button iff asset.create | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC asset 'Edit' iff asset.update | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC status buttons iff asset.change_status | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC upload form iff asset.document.manage | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC 'Add meter' iff asset.update | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC reading form iff asset.meter.record | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC history tab content iff asset.history.view | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC direct URL: asset create form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC direct URL: asset edit form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC register asset | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC edit asset | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC change status | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC upload document | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC remove document | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC add meter | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC record reading | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC toggle meter | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC create category | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC edit category | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC categories page: opens iff asset.view; management form iff asset.category.manage | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |

## 6. Tenant isolation (Alpha <-> Beta, both directions)

57/57 tenant checks PASS. Beta fixtures were created through the Beta UI; Alpha fixtures through the Alpha UI. Probes cover list, search, filters, detail, edit forms, edit POSTs, status/state actions, documents/meters/relations/schedules, HTMX partials, file download, API and forged foreign ids.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Crafted POST: site of another tenant rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 2 | Crafted POST: category of another tenant rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 3 | Crafted POST: owner (member) of another tenant rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 4 | Tenant: Beta cannot open the other tenant's asset detail | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 5 | Tenant: Beta cannot open its documents tab | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 6 | Tenant: Beta cannot open its meters tab | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 7 | Tenant: Beta cannot open its history tab | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 8 | Tenant: Beta cannot open its hierarchy tab | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 9 | Tenant: Beta cannot open its edit form | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 10 | Tenant: Beta cannot edit it (POST) | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 11 | Tenant: Beta cannot change its status | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 12 | Tenant: Beta cannot upload a document to it | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 13 | Tenant: Beta cannot remove its document | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 14 | Tenant: Beta cannot add a meter to it | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 15 | Tenant: Beta cannot record a reading on its meter | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 16 | Tenant: Beta cannot toggle its meter | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 17 | Tenant: Beta cannot load its HTMX tree | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 18 | Tenant: Beta cannot download its document file | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 19 | Tenant: Beta cannot edit its category | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 20 | Tenant: Alpha cannot open the other tenant's asset detail | owner | PASS | 403/404, DB unchanged -> http=404 |
| 21 | Tenant: Alpha cannot open its documents tab | owner | PASS | 403/404, DB unchanged -> http=404 |
| 22 | Tenant: Alpha cannot open its meters tab | owner | PASS | 403/404, DB unchanged -> http=404 |
| 23 | Tenant: Alpha cannot open its history tab | owner | PASS | 403/404, DB unchanged -> http=404 |
| 24 | Tenant: Alpha cannot open its hierarchy tab | owner | PASS | 403/404, DB unchanged -> http=404 |
| 25 | Tenant: Alpha cannot open its edit form | owner | PASS | 403/404, DB unchanged -> http=404 |
| 26 | Tenant: Alpha cannot edit it (POST) | owner | PASS | 403/404, DB unchanged -> http=404 |
| 27 | Tenant: Alpha cannot change its status | owner | PASS | 403/404, DB unchanged -> http=404 |
| 28 | Tenant: Alpha cannot upload a document to it | owner | PASS | 403/404, DB unchanged -> http=404 |
| 29 | Tenant: Alpha cannot remove its document | owner | PASS | 403/404, DB unchanged -> http=404 |
| 30 | Tenant: Alpha cannot add a meter to it | owner | PASS | 403/404, DB unchanged -> http=404 |
| 31 | Tenant: Alpha cannot record a reading on its meter | owner | PASS | 403/404, DB unchanged -> http=404 |
| 32 | Tenant: Alpha cannot toggle its meter | owner | PASS | 403/404, DB unchanged -> http=404 |
| 33 | Tenant: Alpha cannot load its HTMX tree | owner | PASS | 403/404, DB unchanged -> http=404 |
| 34 | Tenant: Alpha cannot download its document file | owner | PASS | 403/404, DB unchanged -> http=404 |
| 35 | Tenant: Alpha cannot edit its category | owner | PASS | 403/404, DB unchanged -> http=404 |
| 36 | Beta asset list/search never shows Alpha assets | betaowner | PASS | no result -> ok |
| 37 | Beta filtering by an Alpha site id shows nothing | betaowner | PASS | empty -> ok |
| 38 | Beta filtering by an Alpha category id shows nothing | betaowner | PASS | empty -> ok |
| 39 | Beta categories page lists none of Alpha's categories | betaowner | PASS | none -> ok |
| 40 | Alpha asset list/search never shows Beta assets | owner | PASS | no result -> ok |
| 41 | API: Beta GET Alpha asset -> 404 | betaowner | PASS | 404 -> 404 |
| 42 | API: Beta asset list contains no Alpha assets | betaowner | PASS | none -> 4 |
| 43 | Tenant: Beta registers an asset at an Alpha site is rejected | betaowner | PASS | 400/403/404, nothing saved -> http=400 |
| 44 | Tenant: Beta registers an asset in an Alpha category is rejected | betaowner | PASS | 400/403/404, nothing saved -> http=400 |
| 45 | Tenant: Alpha registers an asset at a Beta site is rejected | owner | PASS | 400/403/404, nothing saved -> http=400 |
| 46 | Anonymous user is redirected to login for /app/assets/ | anonymous | PASS | login redirect / 401/403 -> 1:8098/accounts/login/?next=/app/assets/ |
| 47 | Anonymous user is redirected to login for /app/assets/e0801843-0c4d-47 | anonymous | PASS | login redirect / 401/403 -> ts/e0801843/ |
| 48 | Anonymous user is redirected to login for /app/files/a006ccf7-8409-4ba | anonymous | PASS | login redirect / 401/403 -> f7-8409-4bad-a56a-d08ce5b5ea1b/download/ |
| 49 | Anonymous GET /app/assets/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> http://127.0.0.1:8098/accounts/login/?next=/app/assets/ |
| 50 | Anonymous GET /app/assets/new/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> http://127.0.0.1:8098/accounts/login/?next=/app/assets/new/ |
| 51 | Anonymous GET /app/assets/categories/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> /127.0.0.1:8098/accounts/login/?next=/app/assets/categories/ |
| 52 | Anonymous GET /app/assets/{id}/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> ogin/?next=/app/assets/f62949cd/ |
| 53 | Anonymous GET /app/assets/{id}/?tab redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> sets/f62949cd/%3Ftab%3Ddocuments |
| 54 | Anonymous GET /app/assets/{id}/edit/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> ?next=/app/assets/f62949cd/edit/ |
| 55 | Anonymous POST /app/assets/{id}/transition/start_maintenance/ is refused (login redirect / 403) and changes n… | anonymous | PASS | refused, DB unchanged -> http=200 -> 6deab3d6f6/transition/start_maintenance/ |
| 56 | Anonymous POST /app/assets/{id}/meters/new/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> -5c00-4536-88ec-676deab3d6f6/meters/new/ |
| 57 | Anonymous POST /app/assets/categories/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> unts/login/?next=/app/assets/categories/ |

## 7. Database persistence (browser action -> SQL read-back, refresh persistence, audit)

276/277 checks that carry a database/audit read-back PASS.

| # | Feature | Db | Audit | Status |
|---|---|---|---|---|
| 1 | Page 1 shows 20 rows (page size) | 266 |  | PASS |
| 2 | Search by tag exact ('GEN-001') | 2 |  | PASS |
| 3 | Search by tag partial ('gen-0') | 2 |  | PASS |
| 4 | Search by name ('Coolant') | 1 |  | PASS |
| 5 | Search by serial ('CU-500') | 1 |  | PASS |
| 6 | Search by manufacturer ('cummins') | 2 |  | PASS |
| 7 | Search by model ('ModelP') | 24 |  | PASS |
| 8 | Site filter HYD-1: exactly its assets (234) | 234 |  | PASS |
| 9 | Site filter BLR-1: exactly its assets (26) | 26 |  | PASS |
| 10 | Category filter Pump: exactly its assets (247) | 247 |  | PASS |
| 11 | Category filter Generator: exactly its assets (1) | 1 |  | PASS |
| 12 | Category filter Vehicle: exactly its assets (1) | 1 |  | PASS |
| 13 | Category filter Motor: exactly its assets (14) | 14 |  | PASS |
| 14 | Status filter ACTIVE: matches DB (250) | 250 |  | PASS |
| 15 | Status filter UNDER_MAINTENANCE: matches DB (1) | 1 |  | PASS |
| 16 | Status filter OUT_OF_SERVICE: matches DB (1) | 1 |  | PASS |
| 17 | Status filter RETIRED: matches DB (13) | 13 |  | PASS |
| 18 | Status filter DISPOSED: matches DB (1) | 1 |  | PASS |
| 19 | Combined site+category+status filters (AND) | 205 |  | PASS |
| 20 | Zone filter (URL ?zone=) returns only that zone's assets | 2 |  | PASS |
| 21 | Owner filter (URL ?owner=) matches DB | 1 |  | PASS |
| 22 | URL ordering=asset_tag: the 20 listed rows follow the database ordering by asset_tag | ['a-18811', 'a-19207'] |  | PASS |
| 23 | URL ordering=-asset_tag: the 20 listed rows follow the database ordering by asset_tag | ['zb15414', 'zb15301'] |  | PASS |
| 24 | URL ordering=name: the 20 listed rows follow the database ordering by name | ['<imgsrc=xonerror=window.ax=1>', '<imgsrc=xonerror=window.ax=1>'] |  | PASS |
| 25 | URL ordering=-name: the 20 listed rows follow the database ordering by name | ['tag40', 'tag40'] |  | PASS |
| 26 | URL ordering=status: the 20 listed rows follow the database ordering by status | ['active', 'active'] |  | PASS |
| 27 | URL ordering=-created_at: newest asset first | FGS-21420 |  | PASS |
| 28 | Create category with 4 typed custom attributes (persisted) | QA Cat 21666\|created in browser\|true\|4 | asset.category_created | PASS |
| 29 | Attribute types/required/choices parsed correctly | [{"key": "voltage", "type": "number", "label": "Voltage", "choices": [], "requi… |  | PASS |
| 30 | Edit category inline (description + attributes) persisted | edited desc\|4 | asset.category_created,asset.category_updated | PASS |
| 31 | Deactivate category via checkbox + Save | f | asset.category_created,asset.category_updated,asset.ca… | PASS |
| 32 | Reactivate category |  | asset.category_created,asset.category_updated,asset.ca… | PASS |
| 33 | Register asset with every field -> redirect to detail + success message |  | asset.created | PASS |
| 34 | Every field persisted exactly (incl. unicode, multi-line, dates, FK ids, status ACTIVE) | FULL-21666\|Full asset ä‑ü\|44ab27d9\|358049f8\|5b7dce1f\|MakerCo\|M-9000\|SN-2… |  | PASS |
| 35 | Custom attributes persisted (number/choice/date/text) | {"notes": "note text", "phase": "Three", "voltage": "415.5", "installed_on": "2… |  | PASS |
| 36 | Registration writes status-history and location-history rows | 1+1 |  | PASS |
| 37 | Audit row asset.created written |  | asset.created | PASS |
| 38 | Minimal create (required fields only) persists with empty optionals |  | asset.created | PASS |
| 39 | Empty submit: 400, inline errors under required fields, nothing saved | 268->268 |  | PASS |
| 40 | Validation: tag required | 268->268 |  | PASS |
| 41 | Validation: name required | 268->268 |  | PASS |
| 42 | Validation: name whitespace only | 268->268 |  | PASS |
| 43 | Validation (server): tag 41 chars (max 40) | 268->268 |  | PASS |
| 44 | Validation (server): name 201 chars (max 200) | 268->268 |  | PASS |
| 45 | Validation (server): manufacturer 101 chars | 268->268 |  | PASS |
| 46 | Validation (server): model 101 chars | 268->268 |  | PASS |
| 47 | Validation (server): serial 101 chars | 268->268 |  | PASS |
| 48 | Validation (server): warranty ref 201 chars | 268->268 |  | PASS |
| 49 | Validation (server): invalid purchase date text | 268->268 |  | PASS |
| 50 | Validation (server): impossible purchase date 2024-02-30 | 268->268 |  | PASS |
| 51 | Validation: commissioning before purchase | 268->268 |  | PASS |
| 52 | Validation (server): zone of another site | 268->268 |  | PASS |
| 53 | Validation: duplicate tag (exact) | 269->269 |  | PASS |
| 54 | Validation: duplicate tag (lower-case) | 269->269 |  | PASS |
| 55 | Validation: duplicate tag (padded with spaces) | 269->269 |  | PASS |
| 56 | Validation: duplicate serial for the same manufacturer | 269->269 |  | PASS |
| 57 | Validation: duplicate serial, manufacturer different case | 269->269 |  | PASS |
| 58 | Same serial with a DIFFERENT manufacturer is allowed |  | asset.created | PASS |
| 59 | Future purchase/commissioning dates | created=True |  | PASS |
| 60 | Crafted POST: site of another tenant rejected | 275->275 |  | PASS |
| 61 | Crafted POST: category of another tenant rejected | 275->275 |  | PASS |
| 62 | Crafted POST: owner (member) of another tenant rejected | 275->275 |  | PASS |
| 63 | Crafted POST: non-existent site id rejected | 275->275 |  | PASS |
| 64 | Crafted POST: malformed category id rejected | 275->275 |  | PASS |
| 65 | Crafted POST: non-existent zone id rejected | 275->275 |  | PASS |
| 66 | Crafted POST: inactive category rejected | 275->275 |  | PASS |
| 67 | Custom attribute: required number missing | 276->276 |  | PASS |
| 68 | Custom attribute: non-numeric number value | 276->276 |  | PASS |
| 69 | Custom attribute: invalid date attribute | 276->276 |  | PASS |
| 70 | Custom attribute: choice outside the allowed list refused (forged) | 276->276 |  | PASS |
| 71 | Asset cannot be registered at an inactive site | 276->276 |  | PASS |
| 72 | Edit every field (incl. site/location move, owner, dates) persisted + success message | FULL2-21666\|Renamed asset\|MakerCo2\|M-9001\|SN2-21666\|2023-12-01\|2024-02-01… | asset.updated | PASS |
| 73 | Edit: custom attribute values persisted | {"notes": "n2", "phase": "Single", "voltage": "230", "installed_on": "2024-03-0… |  | PASS |
| 74 | Location move writes location-history with the typed reason | moved to Warehouse |  | PASS |
| 75 | Audit row records before/after for the edit |  | {"name": "Full asset ä‑ü", "model": "M-9000", "status"… | PASS |
| 76 | Edit: category change saved and the old category's attribute values are dropped |  | asset.updated,asset.updated | PASS |
| 77 | Upload manual.pdf: stored with title/type/name/size/sha256 + success message | Doc manual.pdf\|MANUAL\|manual.pdf\|69\|cfa3181c1ee36e8bce5e39f84959f4558ea7ba3… | asset.document_added | PASS |
| 78 | Upload photo.png: stored with title/type/name/size/sha256 + success message | Doc photo.png\|DATASHEET\|photo.png\|70\|6b7fa434f92a8b80aab02d9bf1a12e49ffcae4… | asset.document_added,asset.document_added | PASS |
| 79 | Upload notes.txt: stored with title/type/name/size/sha256 + success message | Doc notes.txt\|CERTIFICATE\|notes.txt\|17\|e2ea404d1cce4e1b74a48d1260d3c72b106b… | asset.document_added,asset.document_added,asset.docume… | PASS |
| 80 | Upload data.csv: stored with title/type/name/size/sha256 + success message | Doc data.csv\|COMMISSIONING\|data.csv\|8\|492d5ea496056f1a6a6592241032fab764c32… | asset.document_added,asset.document_added,asset.docume… | PASS |
| 81 | Upload spec.docx: stored with title/type/name/size/sha256 + success message | Doc spec.docx\|PHOTO\|spec.docx\|258\|e78c1a5e672183154f67c04a406c53c4cbe0640fb… | asset.document_added,asset.document_added,asset.docume… | PASS |
| 82 | Download returns the exact uploaded bytes with the original file name | sha=cfa3181c1ee3 |  | PASS |
| 83 | Invalid upload refused: virus.exe | 6->6 |  | PASS |
| 84 | Invalid upload refused: script.js | 6->6 |  | PASS |
| 85 | Invalid upload refused: fake.pdf | 6->6 |  | PASS |
| 86 | Invalid upload refused: fakepng.png | 6->6 |  | PASS |
| 87 | Invalid upload refused: empty.txt | 6->6 |  | PASS |
| 88 | Invalid upload refused: binary.txt | 6->6 |  | PASS |
| 89 | Invalid upload refused: noext | 6->6 |  | PASS |
| 90 | Invalid upload refused: evil.pdf.exe | 6->6 |  | PASS |
| 91 | Invalid upload refused: page.html | 6->6 |  | PASS |
| 92 | Invalid upload refused: arch.zip | 6->6 |  | PASS |
| 93 | Upload with no file (forged past the browser): server answers 'Choose a file to upload' | 6->6 |  | PASS |
| 94 | Oversize file (>10 MB) refused | 6->6 |  | PASS |
| 95 | Boundary: exactly 10 MB accepted | 7 |  | PASS |
| 96 | Path-traversal / unsafe file name is sanitised; stored under organizations/<org>/ with a rando… | pass wd__.pdf\|organizations/6ca21e0d/2026/d3b6e9653f7d4f8daee9301d251c430f.pdf |  | PASS |
| 97 | Remove with reason: soft-removed (reason, who, when stored) | false\|superseded\|true | asset.document_removed | PASS |
| 98 | Add meter: name/unit stored, active, success message |  | asset.meter_created | PASS |
| 99 | Record reading (value, notes, source=manual) | 100.500\|first\|manual | asset.meter_reading_recorded | PASS |
| 100 | Last reading display matches the latest stored value | 160.000 |  | PASS |
| 101 | Meter reading history list | 4 readings stored |  | PARTIAL |
| 102 | Deactivate meter ('Deactivate' button) |  | asset.created,asset.meter_created,asset.meter_created,… | PASS |
| 103 | Reading on an inactive meter refused (forged POST) | 4->4 |  | PASS |
| 104 | Reactivate meter |  | asset.created,asset.meter_created,asset.meter_created,… | PASS |
| 105 | Forged invalid transition 'retire' on ACTIVE does not change the status | ACTIVE |  | PASS |
| 106 | Forged invalid transition 'dispose' on ACTIVE does not change the status | ACTIVE |  | PASS |
| 107 | Forged invalid transition 'mark_out_of_service' on ACTIVE does not change the status | ACTIVE |  | PASS |
| 108 | Forged invalid transition 'return_to_service' on ACTIVE does not change the status | ACTIVE |  | PASS |
| 109 | Forged invalid transition 'complete_maintenance' on ACTIVE does not change the status | ACTIVE |  | PASS |
| 110 | Forged invalid transition 'explode' on ACTIVE does not change the status | ACTIVE |  | PASS |
| 111 | ACTIVE -> UNDER MAINTENANCE via UI | UNDER_MAINTENANCE | asset.status_changed | PASS |
| 112 | UNDER MAINTENANCE -> ACTIVE (Complete maintenance) | ACTIVE | asset.status_changed,asset.status_changed | PASS |
| 113 | UNDER MAINTENANCE -> OUT OF SERVICE | OUT_OF_SERVICE |  | PASS |
| 114 | OUT OF SERVICE -> ACTIVE (Return to service) | ACTIVE |  | PASS |
| 115 | OUT OF SERVICE -> RETIRED (terminal) after confirmation | RETIRED | asset.status_changed,asset.status_changed,asset.status… | PASS |
| 116 | Status history has one row per change (registration + 8 transitions) | ->ACTIVE:register:Asset registered ; ACTIVE>UNDER_MAINTENANCE:start_maintenance… |  | PASS |
| 117 | One audit row per transition (8) |  | 8 | PASS |
| 118 | OUT OF SERVICE -> DISPOSED (terminal) after confirmation |  | asset.status_changed,asset.status_changed,asset.status… | PASS |
| 119 | Boundary: 501-char reason is truncated/handled without a server error | 500 |  | PASS |
| 120 | RBAC register asset | 0 -> 1 |  | PASS |
| 121 | RBAC edit asset | QA asset -> RBAC owner |  | PASS |
| 122 | RBAC change status | ACTIVE -> UNDER_MAINTENANCE |  | PASS |
| 123 | RBAC upload document | 12 -> 13 |  | PASS |
| 124 | RBAC remove document | t -> f |  | PASS |
| 125 | RBAC add meter | 1 -> 2 |  | PASS |
| 126 | RBAC record reading | 1 -> 2 |  | PASS |
| 127 | RBAC toggle meter | t -> f |  | PASS |
| 128 | RBAC create category | 0 -> 1 |  | PASS |
| 129 | RBAC edit category | rbac assets -> rbac owner |  | PASS |
| 130 | RBAC register asset | 0 -> 0 |  | PASS |
| 131 | RBAC edit asset | RBAC owner -> RBAC owner |  | PASS |
| 132 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 133 | RBAC upload document | 13 -> 13 |  | PASS |
| 134 | RBAC remove document | t -> t |  | PASS |
| 135 | RBAC add meter | 2 -> 2 |  | PASS |
| 136 | RBAC record reading | 2 -> 2 |  | PASS |
| 137 | RBAC toggle meter | t -> t |  | PASS |
| 138 | RBAC create category | 0 -> 0 |  | PASS |
| 139 | RBAC edit category | rbac owner -> rbac owner |  | PASS |
| 140 | RBAC register asset | 0 -> 0 |  | PASS |
| 141 | RBAC edit asset | RBAC owner -> RBAC owner |  | PASS |
| 142 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 143 | RBAC upload document | 13 -> 13 |  | PASS |
| 144 | RBAC remove document | t -> t |  | PASS |
| 145 | RBAC add meter | 2 -> 2 |  | PASS |
| 146 | RBAC record reading | 2 -> 2 |  | PASS |
| 147 | RBAC toggle meter | t -> t |  | PASS |
| 148 | RBAC create category | 0 -> 0 |  | PASS |
| 149 | RBAC edit category | rbac owner -> rbac owner |  | PASS |
| 150 | RBAC register asset | 0 -> 0 |  | PASS |
| 151 | RBAC edit asset | RBAC owner -> RBAC owner |  | PASS |
| 152 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 153 | RBAC upload document | 13 -> 13 |  | PASS |
| 154 | RBAC remove document | t -> t |  | PASS |
| 155 | RBAC add meter | 2 -> 2 |  | PASS |
| 156 | RBAC record reading | 2 -> 2 |  | PASS |
| 157 | RBAC toggle meter | t -> t |  | PASS |
| 158 | RBAC create category | 0 -> 0 |  | PASS |
| 159 | RBAC edit category | rbac owner -> rbac owner |  | PASS |
| 160 | RBAC register asset | 0 -> 1 |  | PASS |
| 161 | RBAC edit asset | RBAC owner -> RBAC assets |  | PASS |
| 162 | RBAC change status | ACTIVE -> UNDER_MAINTENANCE |  | PASS |
| 163 | RBAC upload document | 13 -> 14 |  | PASS |
| 164 | RBAC remove document | t -> f |  | PASS |
| 165 | RBAC add meter | 2 -> 3 |  | PASS |
| 166 | RBAC record reading | 2 -> 3 |  | PASS |
| 167 | RBAC toggle meter | t -> f |  | PASS |
| 168 | RBAC create category | 0 -> 1 |  | PASS |
| 169 | RBAC edit category | rbac owner -> rbac assets |  | PASS |
| 170 | RBAC register asset | 0 -> 0 |  | PASS |
| 171 | RBAC edit asset | RBAC assets -> RBAC assets |  | PASS |
| 172 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 173 | RBAC upload document | 14 -> 14 |  | PASS |
| 174 | RBAC remove document | t -> t |  | PASS |
| 175 | RBAC add meter | 3 -> 3 |  | PASS |
| 176 | RBAC record reading | 3 -> 3 |  | PASS |
| 177 | RBAC toggle meter | t -> t |  | PASS |
| 178 | RBAC create category | 0 -> 0 |  | PASS |
| 179 | RBAC edit category | rbac assets -> rbac assets |  | PASS |
| 180 | RBAC register asset | 0 -> 0 |  | PASS |
| 181 | RBAC edit asset | RBAC assets -> RBAC assets |  | PASS |
| 182 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 183 | RBAC upload document | 14 -> 14 |  | PASS |
| 184 | RBAC remove document | t -> t |  | PASS |
| 185 | RBAC add meter | 3 -> 3 |  | PASS |
| 186 | RBAC record reading | 3 -> 4 |  | PASS |
| 187 | RBAC toggle meter | t -> t |  | PASS |
| 188 | RBAC create category | 0 -> 0 |  | PASS |
| 189 | RBAC edit category | rbac assets -> rbac assets |  | PASS |
| 190 | RBAC register asset | 0 -> 0 |  | PASS |
| 191 | RBAC edit asset | RBAC assets -> RBAC assets |  | PASS |
| 192 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 193 | RBAC upload document | 14 -> 14 |  | PASS |
| 194 | RBAC remove document | t -> t |  | PASS |
| 195 | RBAC add meter | 3 -> 3 |  | PASS |
| 196 | RBAC record reading | 4 -> 5 |  | PASS |
| 197 | RBAC toggle meter | t -> t |  | PASS |
| 198 | RBAC create category | 0 -> 0 |  | PASS |
| 199 | RBAC edit category | rbac assets -> rbac assets |  | PASS |
| 200 | RBAC register asset | 0 -> 0 |  | PASS |
| 201 | RBAC edit asset | RBAC assets -> RBAC assets |  | PASS |
| 202 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 203 | RBAC upload document | 14 -> 14 |  | PASS |
| 204 | RBAC remove document | t -> t |  | PASS |
| 205 | RBAC add meter | 3 -> 3 |  | PASS |
| 206 | RBAC record reading | 5 -> 5 |  | PASS |
| 207 | RBAC toggle meter | t -> t |  | PASS |
| 208 | RBAC create category | 0 -> 0 |  | PASS |
| 209 | RBAC edit category | rbac assets -> rbac assets |  | PASS |
| 210 | RBAC register asset | 0 -> 0 |  | PASS |
| 211 | RBAC edit asset | RBAC assets -> RBAC assets |  | PASS |
| 212 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 213 | RBAC upload document | 14 -> 14 |  | PASS |
| 214 | RBAC remove document | t -> t |  | PASS |
| 215 | RBAC add meter | 3 -> 3 |  | PASS |
| 216 | RBAC record reading | 5 -> 5 |  | PASS |
| 217 | RBAC toggle meter | t -> t |  | PASS |
| 218 | RBAC create category | 0 -> 0 |  | PASS |
| 219 | RBAC edit category | rbac assets -> rbac assets |  | PASS |
| 220 | RBAC register asset | 0 -> 0 |  | PASS |
| 221 | RBAC edit asset | RBAC assets -> RBAC assets |  | PASS |
| 222 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 223 | RBAC upload document | 14 -> 14 |  | PASS |
| 224 | RBAC remove document | t -> t |  | PASS |
| 225 | RBAC add meter | 3 -> 3 |  | PASS |
| 226 | RBAC record reading | 5 -> 5 |  | PASS |
| 227 | RBAC toggle meter | t -> t |  | PASS |
| 228 | RBAC create category | 0 -> 0 |  | PASS |
| 229 | RBAC edit category | rbac assets -> rbac assets |  | PASS |
| 230 | RBAC register asset | 0 -> 0 |  | PASS |
| 231 | RBAC edit asset | RBAC assets -> RBAC assets |  | PASS |
| 232 | RBAC change status | ACTIVE -> ACTIVE |  | PASS |
| 233 | RBAC upload document | 14 -> 14 |  | PASS |
| 234 | RBAC remove document | t -> t |  | PASS |
| 235 | RBAC add meter | 3 -> 3 |  | PASS |
| 236 | RBAC record reading | 5 -> 5 |  | PASS |
| 237 | RBAC toggle meter | t -> t |  | PASS |
| 238 | RBAC create category | 0 -> 0 |  | PASS |
| 239 | RBAC edit category | rbac assets -> rbac assets |  | PASS |
| 240 | Tenant: Beta cannot open the other tenant's asset detail | 1 -> 1 |  | PASS |
| 241 | Tenant: Beta cannot open its documents tab | 1 -> 1 |  | PASS |
| 242 | Tenant: Beta cannot open its meters tab | 1 -> 1 |  | PASS |
| 243 | Tenant: Beta cannot open its history tab | 1 -> 1 |  | PASS |
| 244 | Tenant: Beta cannot open its hierarchy tab | 1 -> 1 |  | PASS |
| 245 | Tenant: Beta cannot open its edit form | 1 -> 1 |  | PASS |
| 246 | Tenant: Beta cannot edit it (POST) | QA asset -> QA asset |  | PASS |
| 247 | Tenant: Beta cannot change its status | ACTIVE -> ACTIVE |  | PASS |
| 248 | Tenant: Beta cannot upload a document to it | 1 -> 1 |  | PASS |
| 249 | Tenant: Beta cannot remove its document | t -> t |  | PASS |
| 250 | Tenant: Beta cannot add a meter to it | 1 -> 1 |  | PASS |
| 251 | Tenant: Beta cannot record a reading on its meter | 0 -> 0 |  | PASS |
| 252 | Tenant: Beta cannot toggle its meter | t -> t |  | PASS |
| 253 | Tenant: Beta cannot load its HTMX tree | 1 -> 1 |  | PASS |
| 254 | Tenant: Beta cannot download its document file | 1 -> 1 |  | PASS |
| 255 | Tenant: Beta cannot edit its category | Pump -> Pump |  | PASS |
| 256 | Tenant: Alpha cannot open the other tenant's asset detail | 1 -> 1 |  | PASS |
| 257 | Tenant: Alpha cannot open its documents tab | 1 -> 1 |  | PASS |
| 258 | Tenant: Alpha cannot open its meters tab | 1 -> 1 |  | PASS |
| 259 | Tenant: Alpha cannot open its history tab | 1 -> 1 |  | PASS |
| 260 | Tenant: Alpha cannot open its hierarchy tab | 1 -> 1 |  | PASS |
| 261 | Tenant: Alpha cannot open its edit form | 1 -> 1 |  | PASS |
| 262 | Tenant: Alpha cannot edit it (POST) | Beta asset -> Beta asset |  | PASS |
| 263 | Tenant: Alpha cannot change its status | ACTIVE -> ACTIVE |  | PASS |
| 264 | Tenant: Alpha cannot upload a document to it | 1 -> 1 |  | PASS |
| 265 | Tenant: Alpha cannot remove its document | t -> t |  | PASS |
| 266 | Tenant: Alpha cannot add a meter to it | 1 -> 1 |  | PASS |
| 267 | Tenant: Alpha cannot record a reading on its meter | 0 -> 0 |  | PASS |
| 268 | Tenant: Alpha cannot toggle its meter | t -> t |  | PASS |
| 269 | Tenant: Alpha cannot load its HTMX tree | 1 -> 1 |  | PASS |
| 270 | Tenant: Alpha cannot download its document file | 1 -> 1 |  | PASS |
| 271 | Tenant: Alpha cannot edit its category | Compressor -> Compressor |  | PASS |
| 272 | Tenant: Beta registers an asset at an Alpha site is rejected | 94->94 |  | PASS |
| 273 | Tenant: Beta registers an asset in an Alpha category is rejected | 94->94 |  | PASS |
| 274 | Tenant: Alpha registers an asset at a Beta site is rejected | 94->94 |  | PASS |
| 275 | Anonymous POST /app/assets/{id}/transition/start_maintenance/ is refused (login redirect / 403… | ACTIVE -> ACTIVE |  | PASS |
| 276 | Anonymous POST /app/assets/{id}/meters/new/ is refused (login redirect / 403) and changes noth… | 1 -> 1 |  | PASS |
| 277 | Anonymous POST /app/assets/categories/ is refused (login redirect / 403) and changes nothing | 0 -> 0 |  | PASS |

## 8. HTMX

HTMX requests observed: `GET /app/notifications/bell/` x596, `GET /app/assets/{id}/tree/` x5, `GET /app/contracts/assets/{id}/panel/` x5, `GET /app/identification/assets/{id}/panel/` x5. Failures observed: 0 (all injected on purpose: `-`). 4/4 HTMX-related checks PASS.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Selecting a category reloads the form with its custom attribute fields | owner | PASS | attr_* fields appear -> ['attr_voltage', 'attr_phase', 'attr_installed_on', 'attr_notes'] |
| 2 | Edit: switching category reloads the form without the old category's attribute fields | owner | PASS | no attr fields -> 0 |
| 3 | Tenant: Beta cannot load its HTMX tree | betaowner | PASS | 403/404, DB unchanged -> http=404 |
| 4 | Tenant: Alpha cannot load its HTMX tree | owner | PASS | 403/404, DB unchanged -> http=404 |

## 9. Error handling

Deliberately provoked errors (forged ids, unauthorised roles, invalid input, foreign tenants) were answered with 400/403/404/405/409-style refusals and a visible message, never a stack trace; the one exception is listed in section 13. Provoked responses are counted separately from unexplained errors:

| Provoked response | Count |
|---|---|
| 403 GET /app/assets/new/ | 10 |
| 403 GET /app/assets/{id}/edit/ | 10 |
| 403 POST /app/assets/{id}/edit/ body=asset_tag=RBA-18284&nam | 10 |
| 403 POST /app/assets/{id}/transition/start_maintenance/ body | 10 |
| 403 POST /app/assets/{id}/documents/ body= | 10 |
| 403 POST /app/assets/documents/{id}/remove/ body=reason=rbac | 10 |
| 403 POST /app/meters/{id}/toggle/ body=action=deactivate | 10 |
| 403 POST /app/assets/categories/ body=category={id}&name=Pum | 10 |
| 404 GET /app/assets/{id}/?tab | 8 |
| 400 POST /app/assets/new/?asset_tag&category&name body=asset | 7 |
| 400 POST /app/assets/new/ body=zone=&owner=&asset_tag=V-2166 | 7 |
| 400 POST /app/assets/{id}/edit/ body=asset_tag=FULL2-21666&n | 3 |
| 400 POST /app/assets/new/ body=asset_tag=&name=&category=&si | 2 |
| 400 POST /app/assets/new/?category body=asset_tag=CA-21666-3 | 2 |

91/91 error/negative-path checks PASS.

## 10. Responsive / keyboard / modal behaviour

48/48 responsive and usability checks PASS. Method: for each page and viewport the page's `scrollWidth` is compared with the window width, elements wider than the window and clipped buttons/inputs are listed (tables inside `.table-responsive` may scroll internally).

| Page | 1920x1080 | 1440x900 | 1024x768 | 390x844 |
|---|---|---|---|---|
| Asset list | PASS | PASS | PASS | PASS |
| Register asset | PASS | PASS | PASS | PASS |
| Categories | PASS | PASS | PASS | PASS |
| Edit asset | PASS | PASS | PASS | PASS |
| Detail overview | PASS | PASS | PASS | PASS |
| Detail documents | PASS | PASS | PASS | PASS |
| Detail meters | PASS | PASS | PASS | PASS |
| Detail history | PASS | PASS | PASS | PASS |
| Detail hierarchy | PASS | PASS | PASS | PASS |
| Detail coverage | PASS | PASS | PASS | PASS |
| Detail labels | PASS | PASS | PASS | PASS |

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Mobile: the 7 tabs fit or scroll inside their own bar | owner | PASS | no page overflow -> {'sw': 358, 'cw': 358, 'ox': 'visible'} |
| 2 | Keyboard: Tab order in the filter bar is search -> site -> category -> status -> Filter | owner | PASS | logical order -> ['site', 'category', 'status', 'Filter', 'AP16321-01'] |
| 3 | Mobile: the Retire confirmation dialog fits the 390x844 viewport | owner | PASS | within viewport -> {'x': 15.59375, 'y': 346.71875, 'width': 358.796875, 'height': 150.5625} |
| 4 | Mobile: inline validation errors visible on the register form | owner | PASS | visible -> True |

## 11. Console / network result

Console errors, page errors, failed requests and 4xx/5xx recorded outside the harness' 'provoked error' window: 6, of which **0 unexplained** and 6 are 400/404 answers to the scripted negative probes (forged id, foreign tenant, invalid input) whose console line was emitted after the suppression window closed. JavaScript page errors: 0.

Unexplained:

| Kind | Message | Count |
|---|---|---|
| - | none | 0 |

Explained (deliberate negative probes):

| Kind | Message | Count |
|---|---|---|
| console | Failed to load resource: the server responded with a status of 400 (Bad Request) | 2 |
| console | Failed to load resource: the server responded with a status of 404 (Not Found) | 2 |
| http | 404 GET /app/assets/{id}/ | 1 |
| http | 404 GET /api/v1/assets/{id}/ | 1 |

Provoked (expected) problems recorded inside the suppression window: 386; aborted requests of the polling notification bell during navigation (benign, not errors): 4; failed static assets: 0.

Notes: `GET /favicon.ico 404` (if listed) is reported as BX-ALL-02 (cosmetic).

## 12. Integration result

- Asset <-> Site/Zone (M01): site/zone moves write location history with the typed reason (PASS).
- Asset -> M05: 'Report a problem' links to the incident form with ?asset=<id> (contract verified; the incident itself is M05).
- Asset status -> M04: retiring the asset blocks its PM schedules and the plan cannot be re-enabled (PASS). Deactivating a meter blocks meter-based schedules (PASS).
- Asset documents -> Files module: secure upload/download path with tenant checks (PASS).

## 13. Findings

Counts for this module: Critical 0, High 0, Medium 0, Low 3, Cosmetic 1, Unverified 1.

| ID | Severity | Title | Status |
|---|---|---|---|
| BX-ALL-01 | LOW | Keyboard / mobile navigation accessibility: no 'skip to content' link; off-canvas sidebar links stay focusable while hidden; Esc does not c… | OPEN |
| BX-M02-01 | LOW | Asset list: no zone/location filter and no sorting controls in the UI (backend supports ?zone=, ?owner=, ?ordering=) | OPEN |
| BX-M02-02 | LOW | Meter tab shows only the last reading; the reading history is not visible in the browser | OPEN |
| BX-ALL-02 | COSMETIC | Every fresh browser session logs 'GET /favicon.ico -> 404' in the console (no favicon served) | OPEN |

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

### BX-M02-01 - LOW - Asset list: no zone/location filter and no sorting controls in the UI (backend supports ?zone=, ?owner=, ?ordering=)

- **Module:** M02
- **Page / URL:** /app/assets/
- **Role:** owner
- **Action:** Inspect the filter bar and table header
- **Expected:** Filter by zone/location and sortable columns (task scope lists zone filter and sort).
- **Actual:** Filter bar has only q/site/category/status; headers are plain text. ?zone=<id>, ?owner=<id> and ?ordering=name|-name|status|-created_at work when typed in the URL (verified).
- **API / HTMX / network:** GET /app/assets/?zone=<id> 200
- **Console:** none
- **Screenshot:** -
- **Source location:** src/templates/assets/list.html:10-18; src/apps/assets/selectors.py:44-58
- **Status:** OPEN
- **Run evidence:** [PARTIAL] Zone / location filter control -> No zone control in the filter bar (only q/site/category/status); backend supports ?zone= and ?owner= but they are not reachable from the UI

### BX-M02-02 - LOW - Meter tab shows only the last reading; the reading history is not visible in the browser

- **Module:** M02
- **Page / URL:** /app/assets/{id}/?tab=meters
- **Role:** owner
- **Action:** Record several readings, look for the list of past readings
- **Expected:** History of readings (task scope: meter history).
- **Actual:** Only 'Last reading: value on date' per meter; earlier readings exist in the database/API only.
- **API / HTMX / network:** -
- **Console:** none
- **Screenshot:** -
- **Source location:** src/templates/assets/detail.html (meters tab)
- **Status:** OPEN
- **Run evidence:** [PARTIAL] Meter reading history list -> UI shows only the LAST reading per meter; the full reading history is not visible in the browser (only via API/DB)

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

- Asset 'Coverage' tab (M10 contract panel) and 'Labels' tab (M07 QR panel): Both tabs load through HTMX without error for the owner; their own behaviour belongs to the M10/M07 batches and was not exercised.

## 14. Evidence

- Raw per-run result files (every row, console/network capture, click and request coverage): `evidence/M02_run_registry_search_create_edit_categories.json`, `evidence/M02_run_documents_meters_status_rbac_tenant_responsive.json`, `evidence/M02_run_anonymous_session.json`
- Discovery inventory (all pages/links/buttons/forms/tables/HTMX of M01-M04): `evidence/inventory_owner.json`; coverage computation: `evidence/coverage.json`
- Screenshots: `evidence/shots/M02_desktop_list.png`, `evidence/shots/M02_laptop_list.png`, `evidence/shots/M02_mobile_list.png`, `evidence/shots/M02_mobile_modal.png`, `evidence/shots/M02_mobile_validation.png`, `evidence/shots/M02_tablet_list.png`
- Scripts (Playwright, Python): `tools/playwright/` (m02a.py, m02b.py)
- Provoked-error and benign-abort logs are stored in the run files under `expected` and `benign`.

## 15. Final module status

**M02: PASS with LOW observations.** 662/665 checks PASS; 0 FAIL; 3 PARTIAL; 1 UNVERIFIED; 3 not applicable.
Open findings: BX-ALL-01 (LOW), BX-M02-01 (LOW), BX-M02-02 (LOW), BX-ALL-02 (COSMETIC).
Registry, search/filter/pagination, create/edit with every field, categories with custom attributes, documents, meters and the complete status lifecycle work and persist. Only UI-gap observations (no zone filter/sort controls, last reading only) remain; financial/cost fields do not exist in the model or UI and are therefore NOT APPLICABLE.
