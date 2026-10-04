# M03 browser acceptance - detailed (Asset Hierarchy (components & assemblies))

**Batch 1 of the browser acceptance (M01-M04).** Real Chromium (Playwright) against the running application (DEBUG off, CSP on, PostgreSQL `fieldops_browser_qa`, Redis, Celery worker + beat). Every check below was performed in the browser (or by a real in-page request carrying the session cookie and CSRF token) and the database state was read back with SQL; an HTTP 200 alone was never accepted as evidence. No production code was modified.

**Result: M03: 229/234 browser checks PASS** (2 FAIL, 3 PARTIAL, 0 UNVERIFIED; 0 NOT APPLICABLE excluded; 0 superseded harness lines excluded). **Module status: PARTIAL (defect reproduced).**

Roles driven: owner, admin, ops, supervisor, assets, planner, tech (technician 1), tech2, stores, service, auditor, client (all Alpha) and betaowner (tenant Beta). Viewports: 1920x1080, 1440x900, 1024x768, 390x844.

Matrix columns used by the scripts: FEATURE / PAGE / ROLE / ACTION / EXPECTED / ACTUAL / DATABASE / API-HTMX / AUDIT / STATUS; the full matrix for this module is in `evidence/M03_run_hierarchy.json`, `evidence/M03_run_anonymous_session.json`.

## 1. Pages tested

Discovered by a crawl of the module (owner): 1 pages; visited in the test runs: 1/1.

| Page / URL (normalised) | Discovered by crawl | Browser visits |
|---|---|---|
| `/app/assets/new/?parent` | no (reached by test) | 24 |
| `/app/assets/{id}/?tab` | yes | 190 |
| `/app/assets/{id}/tree/` | no (reached by test) | 1 |

Other URLs the tests visited (negative probes, redirects, API): `/accounts/login/`, `/accounts/login/?next`, `/app/`, `/app/assets/?q`, `/app/assets/{id}/`, `/app/portal/`

## 2. Buttons / links / actions

Discovered controls: 6 buttons (6 clicked/posted), 0 distinct links (0 followed), 5 POST endpoints (5 exercised), 0 GET filter forms (0 used), 1 HTMX endpoints (1 exercised).

State-changing requests issued by the browser (normalised path -> count): `/app/assets/{id}/components/add/` x82, `/app/components/{id}/move/` x22, `/app/components/{id}/remove/` x20, `/app/components/{id}/edit/` x18, `/app/assets/new/?parent` x3

All discovered controls were exercised.

## 3. Forms

5 distinct forms discovered (owner view); every field of every form was filled, left blank and given invalid/boundary values in section 4.

| Form (action) | Method | Fields (non-hidden) | Exercised |
|---|---|---|---|
| `/app/assets/{id}/transition/start_maintenance/` | POST | reason | yes |
| `/app/components/{id}/remove/` | POST | (button only) | yes |
| `/app/assets/{id}/components/add/` | POST | child, relationship_type, quantity, part_number, notes | yes |
| `/app/components/{id}/edit/` | POST | relationship_type, quantity, part_number, notes | yes |
| `/app/components/{id}/move/` | POST | parent | yes |

## 4. Validation (client + server)

35/35 validation, boundary, duplicate, forged-input and XSS checks PASS. Forms are `novalidate`; constraints that the browser would block were removed in the page (or the request forged from the page) so that the SERVER rules were exercised, and the matching client hint (maxlength/required) was asserted separately.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Validation: quantity 0 refused without a server error | owner | PASS | refused with message, nothing saved -> Choose an asset and a valid relationship. |
| 2 | Validation: quantity -3 refused without a server error | owner | PASS | refused with message, nothing saved -> Choose an asset and a valid relationship. |
| 3 | Validation: quantity 1.5 refused without a server error | owner | PASS | refused with message, nothing saved -> Choose an asset and a valid relationship. |
| 4 | Validation: quantity 10001 (service cap) refused without a server error | owner | PASS | refused with message, nothing saved -> Quantity must be a whole number from 1 to 10000. |
| 5 | Validation: quantity 100000 refused without a server error | owner | PASS | refused with message, nothing saved -> Quantity must be a whole number from 1 to 10000. |
| 6 | Validation: quantity 99999999999 refused without a server error | owner | PASS | refused with message, nothing saved -> Quantity must be a whole number from 1 to 10000. |
| 7 | Validation: quantity abc refused without a server error | owner | PASS | refused with message, nothing saved -> Choose an asset and a valid relationship. |
| 8 | Notes longer than 300 characters refused (server, past the maxlength attribute) | owner | PASS | refused -> http=200 |
| 9 | Part number longer than 100 characters refused (server) | owner | PASS | refused -> http=200 |
| 10 | Unknown relationship type refused (forged) | owner | PASS | refused -> http=200 |
| 11 | Boundary: quantity 10000 + 100-char part number + 300-char notes accepted | owner | PASS | saved -> 10000 |
| 12 | Stored XSS in notes/part number is escaped on the hierarchy page | owner | PASS | inert -> ok |
| 13 | Negative: asset as its own parent | owner | PASS | no link created -> http=200 |
| 14 | Negative: asset at another site as child | owner | PASS | no link created -> http=200 |
| 15 | Negative: child that already has a parent (A under P) added to another parent | owner | PASS | no link created -> http=200 |
| 16 | Negative: non-existent child id | owner | PASS | no link created -> http=200 |
| 17 | Negative: malformed child id | owner | PASS | no link created -> http=200 |
| 18 | Circular reference: parent cannot become a child of its own child (UI-form forged) | owner | PASS | refused -> http=200 |
| 19 | Circular reference through 3 levels (P > A > X, then X > P) refused | owner | PASS | refused -> http=200 |
| 20 | Depth limit: a 9th level is refused ('limited to 8 levels') | owner | PASS | refused -> The hierarchy is limited to 8 levels. \|\| |
| 21 | Retired asset cannot be attached (forged POST) | owner | PASS | refused -> http=200 |
| 22 | Duplicate tag: neither asset nor link is created (atomic) | owner | PASS | refused, nothing saved -> This asset will be registered and attached as a child of NP-19207 in o |
| 23 | Edit relationship: quantity 0 refused without a server error | owner | PASS | refused -> Check the relationship type and quantity. \|\| Detac |
| 24 | Edit relationship: quantity 10001 refused without a server error | owner | PASS | refused -> Quantity must be a whole number from 1 to 10000. \| |
| 25 | Edit relationship: quantity 99999999999 refused without a server error | owner | PASS | refused -> Quantity must be a whole number from 1 to 10000. \| |
| 26 | Cycle prevention (forged POST): move A under its own child C (cycle) | owner | PASS | unchanged -> http=200 |
| 27 | Cycle prevention (forged POST): move A under itself | owner | PASS | unchanged -> http=200 |
| 28 | Cycle prevention (forged POST): move C under C | owner | PASS | unchanged -> http=200 |
| 29 | Cycle prevention (forged POST): move B under its descendant C | owner | PASS | unchanged -> http=200 |
| 30 | Moving to the current parent is a no-op/refused | owner | PASS | unchanged -> MB-19207 |
| 31 | Move to a parent at another site refused | owner | PASS | unchanged -> MB-19207 |
| 32 | Tenant: Alpha parent + Beta child id is refused | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=200 |
| 33 | Tenant: Alpha move to a Beta parent is refused | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=200 |
| 34 | Anonymous POST /app/assets/{id}/components/add/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 0-4536-88ec-676deab3d6f6/components/add/ |
| 35 | Anonymous POST /app/components/{id}/remove/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 089a-67e4-48d3-9b0e-74d7d077ffe8/remove/ |

## 5. RBAC

115/115 RBAC checks PASS across 10 distinct checks x up to 12 roles. For every role the expected outcome is derived from the role's real permission set in the database (membership -> role -> permission); the browser then proves (a) the control is shown iff permitted, (b) the direct URL answers 200 iff permitted else 403/404, (c) a real forged POST is refused with the database unchanged when denied and succeeds with the expected state change when allowed.

| Check (expected outcome derived from the role's DB permission set) | owner | admin | ops | supervisor | assets | planner | tech | tech2 | stores | service | auditor | client |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RBAC tree visible to every asset viewer | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC 'Add existing asset' form iff asset.hierarchy.manage | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC 'Register a new child asset' link iff asset.hierarchy.manage | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC tree 'Detach' buttons iff asset.hierarchy.manage | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC edit/move controls on a child iff asset.hierarchy.manage | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | - |
| RBAC direct URL: register-child form | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC attach child | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC edit relationship | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC move component | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| RBAC detach component | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |

## 6. Tenant isolation (Alpha <-> Beta, both directions)

22/22 tenant checks PASS. Beta fixtures were created through the Beta UI; Alpha fixtures through the Alpha UI. Probes cover list, search, filters, detail, edit forms, edit POSTs, status/state actions, documents/meters/relations/schedules, HTMX partials, file download, API and forged foreign ids.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Setup: Beta hierarchy exists (BP > BC) | betaowner | PASS | link -> ok |
| 2 | Tenant: Beta cannot open Alpha's tree partial | betaowner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 3 | Tenant: Beta cannot open Alpha's hierarchy tab | betaowner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 4 | Tenant: Beta cannot attach under an Alpha parent | betaowner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 5 | Tenant: Beta cannot edit an Alpha link | betaowner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 6 | Tenant: Beta cannot move an Alpha link | betaowner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 7 | Tenant: Beta cannot detach an Alpha link | betaowner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 8 | Tenant: Alpha cannot open Beta's tree partial | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 9 | Tenant: Alpha cannot attach under a Beta parent | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 10 | Tenant: Alpha cannot edit a Beta link | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 11 | Tenant: Alpha cannot move a Beta link | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 12 | Tenant: Alpha cannot detach a Beta link | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 13 | Tenant: Alpha parent + Beta child id is refused | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=200 |
| 14 | Tenant: Alpha move to a Beta parent is refused | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=200 |
| 15 | Tenant: Alpha register-child with a Beta ?parent= | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 16 | Beta candidate list/tree never contains Alpha assets | betaowner | PASS | none -> ok |
| 17 | API: Beta GET Alpha components -> 404 | betaowner | PASS | 404 -> 404 |
| 18 | Anonymous GET /app/assets/{id}/?tab redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> sets/f62949cd/%3Ftab%3Dhierarchy |
| 19 | Anonymous GET /app/assets/{id}/tree/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> ?next=/app/assets/f62949cd/tree/ |
| 20 | Anonymous GET /app/assets/new/?parent redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> /assets/new/%3Fparent%3Df62949cd |
| 21 | Anonymous POST /app/assets/{id}/components/add/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 0-4536-88ec-676deab3d6f6/components/add/ |
| 22 | Anonymous POST /app/components/{id}/remove/ is refused (login redirect / 403) and changes nothing | anonymous | PASS | refused, DB unchanged -> http=200 -> 089a-67e4-48d3-9b0e-74d7d077ffe8/remove/ |

## 7. Database persistence (browser action -> SQL read-back, refresh persistence, audit)

93/95 checks that carry a database/audit read-back PASS.

| # | Feature | Db | Audit | Status |
|---|---|---|---|---|
| 1 | Add existing asset as component (type/quantity/part number/notes persisted) | COMPONENT\|2\|PN-1\|first | asset.component_added | PASS |
| 2 | Validation: quantity 0 refused without a server error | 41->41 |  | PASS |
| 3 | Validation: quantity -3 refused without a server error | 41->41 |  | PASS |
| 4 | Validation: quantity 1.5 refused without a server error | 41->41 |  | PASS |
| 5 | Validation: quantity 10001 (service cap) refused without a server error | 41->41 |  | PASS |
| 6 | Validation: quantity 100000 refused without a server error | 41->41 |  | PASS |
| 7 | Validation: quantity 99999999999 refused without a server error | 41->41 |  | PASS |
| 8 | Validation: quantity abc refused without a server error | 41->41 |  | PASS |
| 9 | Notes longer than 300 characters refused (server, past the maxlength attribute) | 41->41 |  | PASS |
| 10 | Boundary: quantity 10000 + 100-char part number + 300-char notes accepted |  | asset.component_added | PASS |
| 11 | Negative: asset as its own parent | 43->43 |  | PASS |
| 12 | Negative: asset at another site as child | 43->43 |  | PASS |
| 13 | Negative: child that already has a parent (A under P) added to another parent | 43->43 |  | PASS |
| 14 | Negative: non-existent child id | 43->43 |  | PASS |
| 15 | Negative: malformed child id | 43->43 |  | PASS |
| 16 | Circular reference: parent cannot become a child of its own child (UI-form forged) | 43->43 |  | PASS |
| 17 | Circular reference through 3 levels (P > A > X, then X > P) refused | 44->44 |  | PASS |
| 18 | Depth limit: a 9th level is refused ('limited to 8 levels') | 51->51 |  | PASS |
| 19 | Register child: asset + link created together with the entered relationship data | NP-19207\|REPLACEABLE_PART\|3\|PN-NC3 | asset.created / asset.component_added | PASS |
| 20 | Edit relationship: all four fields persisted + message | ASSEMBLY\|7\|PN-A2\|edited | asset.component_updated | PASS |
| 21 | Edit relationship audit has before/after |  | {"notes": "na", "child_id": "4836ee3e", "quantity": 2,… | PASS |
| 22 | Move A (with its subtree) under B; its child C stays under A | MB-19207 | asset.component_moved | PASS |
| 23 | Move audit records old and new parent |  | {"notes": "edited", "child_id": "4836ee3e-20b9-4ea5-ae… | PASS |
| 24 | Cycle prevention (forged POST): move A under its own child C (cycle) | 2382991a |  | PASS |
| 25 | Cycle prevention (forged POST): move A under itself | 2382991a |  | PASS |
| 26 | Cycle prevention (forged POST): move C under C | 4836ee3e |  | PASS |
| 27 | Cycle prevention (forged POST): move B under its descendant C | 9e1d2bca |  | PASS |
| 28 | Confirm detaches D, keeps the asset and returns to D's own page | link removed | asset.component_removed | PASS |
| 29 | Detach button inside the tree removes that link and returns to the parent page |  | asset.component_removed,asset.component_removed | PASS |
| 30 | Retire a parent that still has a live child | parent=RETIRED, link=True |  | FAIL |
| 31 | Detach the live child K from the retired parent | link=True |  | FAIL |
| 32 | RBAC attach child | 0 -> 1 |  | PASS |
| 33 | RBAC edit relationship | 1 -> 2owner |  | PASS |
| 34 | RBAC move component | 60254546 -> 1671c8a1 |  | PASS |
| 35 | RBAC detach component | 1 -> 0 |  | PASS |
| 36 | RBAC attach child | 0 -> 0 |  | PASS |
| 37 | RBAC edit relationship | 2owner -> 2owner |  | PASS |
| 38 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 39 | RBAC detach component | 1 -> 1 |  | PASS |
| 40 | RBAC attach child | 0 -> 0 |  | PASS |
| 41 | RBAC edit relationship | 2owner -> 2owner |  | PASS |
| 42 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 43 | RBAC detach component | 1 -> 1 |  | PASS |
| 44 | RBAC attach child | 0 -> 0 |  | PASS |
| 45 | RBAC edit relationship | 2owner -> 2owner |  | PASS |
| 46 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 47 | RBAC detach component | 1 -> 1 |  | PASS |
| 48 | RBAC attach child | 0 -> 1 |  | PASS |
| 49 | RBAC edit relationship | 2owner -> 6assets |  | PASS |
| 50 | RBAC move component | 60254546 -> 1671c8a1 |  | PASS |
| 51 | RBAC detach component | 1 -> 0 |  | PASS |
| 52 | RBAC attach child | 0 -> 0 |  | PASS |
| 53 | RBAC edit relationship | 6assets -> 6assets |  | PASS |
| 54 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 55 | RBAC detach component | 1 -> 1 |  | PASS |
| 56 | RBAC attach child | 0 -> 0 |  | PASS |
| 57 | RBAC edit relationship | 6assets -> 6assets |  | PASS |
| 58 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 59 | RBAC detach component | 1 -> 1 |  | PASS |
| 60 | RBAC attach child | 0 -> 0 |  | PASS |
| 61 | RBAC edit relationship | 6assets -> 6assets |  | PASS |
| 62 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 63 | RBAC detach component | 1 -> 1 |  | PASS |
| 64 | RBAC attach child | 0 -> 0 |  | PASS |
| 65 | RBAC edit relationship | 6assets -> 6assets |  | PASS |
| 66 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 67 | RBAC detach component | 1 -> 1 |  | PASS |
| 68 | RBAC attach child | 0 -> 0 |  | PASS |
| 69 | RBAC edit relationship | 6assets -> 6assets |  | PASS |
| 70 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 71 | RBAC detach component | 1 -> 1 |  | PASS |
| 72 | RBAC attach child | 0 -> 0 |  | PASS |
| 73 | RBAC edit relationship | 6assets -> 6assets |  | PASS |
| 74 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 75 | RBAC detach component | 1 -> 1 |  | PASS |
| 76 | RBAC attach child | 0 -> 0 |  | PASS |
| 77 | RBAC edit relationship | 6assets -> 6assets |  | PASS |
| 78 | RBAC move component | 60254546 -> 60254546 |  | PASS |
| 79 | RBAC detach component | 1 -> 1 |  | PASS |
| 80 | Tenant: Beta cannot open Alpha's tree partial | 1 -> 1 |  | PASS |
| 81 | Tenant: Beta cannot open Alpha's hierarchy tab | 1 -> 1 |  | PASS |
| 82 | Tenant: Beta cannot attach under an Alpha parent | 1 -> 1 |  | PASS |
| 83 | Tenant: Beta cannot edit an Alpha link | 1 -> 1 |  | PASS |
| 84 | Tenant: Beta cannot move an Alpha link | 4d3d8135 -> 4d3d8135 |  | PASS |
| 85 | Tenant: Beta cannot detach an Alpha link | 1 -> 1 |  | PASS |
| 86 | Tenant: Alpha cannot open Beta's tree partial | 1 -> 1 |  | PASS |
| 87 | Tenant: Alpha cannot attach under a Beta parent | 1 -> 1 |  | PASS |
| 88 | Tenant: Alpha cannot edit a Beta link | 1 -> 1 |  | PASS |
| 89 | Tenant: Alpha cannot move a Beta link | 01a7b1e6 -> 01a7b1e6 |  | PASS |
| 90 | Tenant: Alpha cannot detach a Beta link | 1 -> 1 |  | PASS |
| 91 | Tenant: Alpha parent + Beta child id is refused | 0 -> 0 |  | PASS |
| 92 | Tenant: Alpha move to a Beta parent is refused | 4d3d8135 -> 4d3d8135 |  | PASS |
| 93 | Tenant: Alpha register-child with a Beta ?parent= | 1 -> 1 |  | PASS |
| 94 | Anonymous POST /app/assets/{id}/components/add/ is refused (login redirect / 403) and changes … | 83 -> 83 |  | PASS |
| 95 | Anonymous POST /app/components/{id}/remove/ is refused (login redirect / 403) and changes noth… | 83 -> 83 |  | PASS |

## 8. HTMX

HTMX requests observed: `GET /app/notifications/bell/` x234, `GET /app/assets/{id}/tree/` x185. Failures observed: 1 (all injected on purpose: `/app/assets/{id}/tree/`). 42/44 HTMX-related checks PASS.

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Standalone asset: tree loads (HTMX) and shows only the asset itself | owner | PASS | tree with 'this asset' -> SOLO-19207 Hier SOLO-19207 Active this asset |
| 2 | Tree is fetched by an HTMX request to /tree/ | owner | PASS | HTMX GET /assets/<id>/tree/ -> request made |
| 3 | Tree shows every node, relationship badges and quantity (×2, ×4) | owner | PASS | 5 nodes + badges -> ROOT-19207 Hier ROOT-19207 Active this asset C1-19207 Hier C1-19207 Component ×2 Active Detach G1-19207 Hier G1-19207 Replaceable part ×4 Ac |
| 4 | Tree opened from a deep node still shows the whole assembly from its root | owner | PASS | root...G2 with G2 highlighted -> ROOT-19207 Hier ROOT-19207 Active C1-19207 Hier C1-19207 Component ×2 Active Detach G1-192 |
| 5 | Tree panel when the HTMX request fails (HTTP 500) | owner | PARTIAL | visible error or retry, not a silent infinite 'Loading…' -> panel text: 'Loading hierarchy…' |
| 6 | Tree panel when the network request is aborted | owner | PARTIAL | graceful message -> panel text: 'Loading hierarchy…' |
| 7 | Tree endpoint returns the HTML partial | owner | PASS | fragment -> 200 |
| 8 | An 8-level tree renders completely | owner | PASS | 8 nodes -> 8 |
| 9 | New child appears in the parent's tree with ×3 | owner | PASS | visible -> ok |
| 10 | Move A (with its subtree) under B; its child C stays under A | owner | PASS | A under B -> MB-19207 |
| 11 | Tree reflects the move after reload | owner | PASS | A under B -> ok |
| 12 | Detached asset disappears from the tree | owner | PASS | gone -> ok |
| 13 | Detach button inside the tree removes that link and returns to the parent page | owner | PASS | link gone -> f0-ef2c3f6fa176/?tab=hierarchy |
| 14 | RBAC tree visible to every asset viewer | owner | PASS | tree -> ok |
| 15 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | owner | PASS | True -> ok |
| 16 | RBAC tree visible to every asset viewer | admin | PASS | tree -> ok |
| 17 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | admin | PASS | False -> ok |
| 18 | RBAC tree visible to every asset viewer | ops | PASS | tree -> ok |
| 19 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | ops | PASS | False -> ok |
| 20 | RBAC tree visible to every asset viewer | supervisor | PASS | tree -> ok |
| 21 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | supervisor | PASS | False -> ok |
| 22 | RBAC tree visible to every asset viewer | assets | PASS | tree -> ok |
| 23 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | assets | PASS | True -> ok |
| 24 | RBAC tree visible to every asset viewer | planner | PASS | tree -> ok |
| 25 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | planner | PASS | False -> ok |
| 26 | RBAC tree visible to every asset viewer | tech | PASS | tree -> ok |
| 27 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | tech | PASS | False -> ok |
| 28 | RBAC tree visible to every asset viewer | tech2 | PASS | tree -> ok |
| 29 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | tech2 | PASS | False -> ok |
| 30 | RBAC tree visible to every asset viewer | stores | PASS | tree -> ok |
| 31 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | stores | PASS | False -> ok |
| 32 | RBAC tree visible to every asset viewer | service | PASS | tree -> ok |
| 33 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | service | PASS | False -> ok |
| 34 | RBAC tree visible to every asset viewer | auditor | PASS | tree -> ok |
| 35 | RBAC tree 'Detach' buttons iff asset.hierarchy.manage | auditor | PASS | False -> ok |
| 36 | Tenant: Beta cannot open Alpha's tree partial | betaowner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 37 | Tenant: Alpha cannot open Beta's tree partial | owner | PASS | refused (403/404, or error message after redirect), DB unchanged -> http=404 |
| 38 | Beta candidate list/tree never contains Alpha assets | betaowner | PASS | none -> ok |
| 39 | Responsive desktop: Hierarchy tab (8-level tree) (no horizontal overflow / clipped controls) | owner | PASS | no overflow -> sw=1920 iw=1920 wide=[] clipped=[] |
| 40 | Responsive laptop: Hierarchy tab (8-level tree) (no horizontal overflow / clipped controls) | owner | PASS | no overflow -> sw=1440 iw=1440 wide=[] clipped=[] |
| 41 | Responsive tablet: Hierarchy tab (8-level tree) (no horizontal overflow / clipped controls) | owner | PASS | no overflow -> sw=1024 iw=1024 wide=[] clipped=[] |
| 42 | Responsive mobile: Hierarchy tab (8-level tree) (no horizontal overflow / clipped controls) | owner | PASS | no overflow -> sw=390 iw=390 wide=[] clipped=[] |
| 43 | Mobile: Detach button in the tree has a usable tap target | owner | PASS | >=24x16 px -> {'x': 226.59375, 'y': 694.890625, 'width': 52.046875, 'height': 23} |
| 44 | Anonymous GET /app/assets/{id}/tree/ redirects to login with ?next= | anonymous | PASS | redirect to /accounts/login/?next= -> ?next=/app/assets/f62949cd/tree/ |

## 9. Error handling

Deliberately provoked errors (forged ids, unauthorised roles, invalid input, foreign tenants) were answered with 400/403/404/405/409-style refusals and a visible message, never a stack trace; the one exception is listed in section 13. Provoked responses are counted separately from unexplained errors:

| Provoked response | Count |
|---|---|
| 403 GET /app/assets/new/?parent | 10 |
| 403 POST /app/assets/{id}/components/add/ body=child={id}&re | 10 |
| 403 POST /app/components/{id}/edit/ body=relationship_type=A | 10 |
| 403 POST /app/components/{id}/move/ body=parent={id} | 10 |
| 403 POST /app/components/{id}/remove/ body=next_asset=parent | 10 |
| 404 POST /app/components/{id}/remove/ body=next_asset=parent | 3 |
| 400 POST /app/assets/new/?parent body=parent={id}&asset_tag= | 2 |
| 404 GET /app/assets/new/?parent | 2 |
| 404 GET /app/assets/{id}/tree/ | 2 |
| 404 POST /app/assets/{id}/components/add/ body=child={id}&re | 2 |
| 404 POST /app/components/{id}/edit/ body=relationship_type=A | 2 |
| 404 POST /app/components/{id}/move/ body=parent={id} | 2 |
| 500 GET /app/assets/{id}/tree/ | 1 |
| 404 GET /app/assets/{id}/?tab | 1 |

33/34 error/negative-path checks PASS.

## 10. Responsive / keyboard / modal behaviour

13/13 responsive and usability checks PASS. Method: for each page and viewport the page's `scrollWidth` is compared with the window width, elements wider than the window and clipped buttons/inputs are listed (tables inside `.table-responsive` may scroll internally).

| Page | 1920x1080 | 1440x900 | 1024x768 | 390x844 |
|---|---|---|---|---|
| Hierarchy tab (8-level tree) | PASS | PASS | PASS | PASS |
| Hierarchy tab (deep node) | PASS | PASS | PASS | PASS |
| Register child form | PASS | PASS | PASS | PASS |

| # | Feature | Role | Status | Expected -> actual |
|---|---|---|---|---|
| 1 | Mobile: Detach button in the tree has a usable tap target | owner | PASS | >=24x16 px -> {'x': 226.59375, 'y': 694.890625, 'width': 52.046875, 'height': 23} |

## 11. Console / network result

Console errors, page errors, failed requests and 4xx/5xx recorded outside the harness' 'provoked error' window: 4, of which **0 unexplained** and 4 are 400/404 answers to the scripted negative probes (forged id, foreign tenant, invalid input) whose console line was emitted after the suppression window closed. JavaScript page errors: 0.

Unexplained:

| Kind | Message | Count |
|---|---|---|
| - | none | 0 |

Explained (deliberate negative probes):

| Kind | Message | Count |
|---|---|---|
| console | Failed to load resource: the server responded with a status of 404 (Not Found) | 2 |
| http | 404 GET /app/assets/new/?parent | 1 |
| http | 404 GET /api/v1/assets/{id}/components/ | 1 |

Provoked (expected) problems recorded inside the suppression window: 139; aborted requests of the polling notification bell during navigation (benign, not errors): 1; failed static assets: 0.

Notes: `GET /favicon.ico 404` (if listed) is reported as BX-ALL-02 (cosmetic).

## 12. Integration result

- Parent/child assets share the site (enforced), cross-tenant ids rejected, hierarchy is shown on the asset list (Parent column), breadcrumbs and the History tab change log (PASS).
- Asset retire (M02) vs hierarchy (M03): integrity gap reproduced (BX-M03-01).
- Part numbers are stored as free text; the bridge to M09 inventory parts is a later batch (UNVERIFIED).

## 13. Findings

Counts for this module: Critical 0, High 0, Medium 1, Low 3, Cosmetic 1, Unverified 0.

| ID | Severity | Title | Status |
|---|---|---|---|
| BX-M03-01 | MEDIUM | Retiring/disposing a parent that still has live children is accepted; the live child can then never be detached, yet the UI still shows Det… | OPEN (same defect as F-M06) |
| BX-M03-02 | LOW | Hierarchy tree panel stays on 'Loading hierarchy…' forever when its HTMX request fails | OPEN |
| BX-ALL-01 | LOW | Keyboard / mobile navigation accessibility: no 'skip to content' link; off-canvas sidebar links stay focusable while hidden; Esc does not c… | OPEN |
| BX-M03-03 | LOW | No single-step 'Replace component' action (replace = Detach + Add) | OPEN (design gap, not a malfunction) |
| BX-ALL-02 | COSMETIC | Every fresh browser session logs 'GET /favicon.ico -> 404' in the console (no favicon served) | OPEN |

### BX-M03-01 - MEDIUM - Retiring/disposing a parent that still has live children is accepted; the live child can then never be detached, yet the UI still shows Detach (F-M06 reproduced)

- **Module:** M03
- **Page / URL:** /app/assets/{parent}/ (Retire) then /app/assets/{child}/?tab=hierarchy
- **Role:** owner
- **Action:** Retire parent P (child K attached) -> open K's Hierarchy tab -> Detach
- **Expected:** Retire refused (or links detached first) so no live asset hangs under a terminal one; any Detach button shown must work.
- **Actual:** Retire accepted (RETIRED). K stays linked to the retired parent; Edit/Move/Detach controls are still rendered for K but every attempt is refused server-side with asset_terminal ('Retired or disposed assets cannot take part in the hierarchy').
- **API / HTMX / network:** POST /app/components/{id}/remove/ -> 302 with error flash; link row remains
- **Console:** none
- **Screenshot:** evidence/shots/M03_mobile_tree.png (tree) - result is textual, see run rows 'Retire a parent that still has a live child'
- **Source location:** src/apps/assets/services.py:207 (change_status has no hierarchy guard); src/apps/assets/hierarchy.py:133,158 (update/remove refuse terminal assets); src/templates/assets/detail.html (controls rendered regardless)
- **Status:** OPEN (same defect as F-M06)
- **Run evidence:** [FAIL] Retire a parent that still has a live child -> retire accepted (RETIRED); link to live child K remains=True

### BX-M03-02 - LOW - Hierarchy tree panel stays on 'Loading hierarchy…' forever when its HTMX request fails

- **Module:** M03
- **Page / URL:** /app/assets/{id}/?tab=hierarchy
- **Role:** owner
- **Action:** Make GET /app/assets/{id}/tree/ fail (HTTP 500, then aborted) -> open the tab
- **Expected:** A visible error / retry message in the panel.
- **Actual:** Panel text remains 'Loading hierarchy…' (no timeout, no error). The same pattern applies to the Coverage and Labels panels (hx-trigger=load, no error handler).
- **API / HTMX / network:** GET /app/assets/{id}/tree/ -> 500 (injected)
- **Console:** Failed to load resource 500 / net::ERR_FAILED (injected)
- **Screenshot:** evidence/shots/M03_tree_htmx_fail.png
- **Source location:** src/templates/assets/detail.html (#tree-host, #coverage-host, #labels-host); no htmx:responseError handler in src/static/js/app.js
- **Status:** OPEN
- **Run evidence:** [PARTIAL] Tree panel when the HTMX request fails (HTTP 500) -> panel text: 'Loading hierarchy…'; [PARTIAL] Tree panel when the network request is aborted -> panel text: 'Loading hierarchy…'

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

### BX-M03-03 - LOW - No single-step 'Replace component' action (replace = Detach + Add)

- **Module:** M03
- **Page / URL:** /app/assets/{id}/?tab=hierarchy
- **Role:** owner
- **Action:** Look for a replace control
- **Expected:** Replace relationship (task scope).
- **Actual:** Replacement is done with two audited steps (Detach, then attach another asset); both steps verified.
- **API / HTMX / network:** -
- **Console:** none
- **Screenshot:** -
- **Source location:** src/templates/assets/detail.html (hierarchy tab)
- **Status:** OPEN (design gap, not a malfunction)
- **Run evidence:** [PARTIAL] Single-step 'Replace component' action -> No replace button: replacement is done by Detach + Add (two audited steps)

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

- Raw per-run result files (every row, console/network capture, click and request coverage): `evidence/M03_run_hierarchy.json`, `evidence/M03_run_anonymous_session.json`
- Discovery inventory (all pages/links/buttons/forms/tables/HTMX of M01-M04): `evidence/inventory_owner.json`; coverage computation: `evidence/coverage.json`
- Screenshots: `evidence/shots/M03_mobile_tree.png`, `evidence/shots/M03_tree_htmx_fail.png`
- Scripts (Playwright, Python): `tools/playwright/` (m03.py)
- Provoked-error and benign-abort logs are stored in the run files under `expected` and `benign`.

## 15. Final module status

**M03: PARTIAL (defect reproduced).** 229/234 checks PASS; 2 FAIL; 3 PARTIAL; 0 UNVERIFIED; 0 not applicable.
Open findings: BX-M03-01 (MEDIUM), BX-M03-02 (LOW), BX-ALL-01 (LOW), BX-M03-03 (LOW), BX-ALL-02 (COSMETIC).
Tree, attach/edit/move/detach, cycle/depth/cross-tenant/site rules, atomic child registration and RBAC all work; the integrity gap with retire (BX-M03-01, Medium) and the missing HTMX error state (BX-M03-02) remain open.
