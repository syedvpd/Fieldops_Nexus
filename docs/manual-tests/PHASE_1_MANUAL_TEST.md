# Phase 1 manual test guide: Sites & Locations (M01), Asset Registry (M02), Asset Hierarchy (M03)

Goal: prove by hand that sites, locations, calendars, contacts, assets, lifecycle status, history, documents, meters, hierarchy and **site-scoped access** work end to end, with real persistence, audit and tenant isolation.
Time: about 75 minutes. Everything runs locally; nothing touches Supabase/production.

**Prerequisite:** Phase 0 steps 0-6 of `PHASE_0_MANUAL_TEST.md` are done (stack up, Super Admin, organizations **Alpha Industries** and **Beta Utilities**, owners activated, `tech@alpha.test` invited and activated). If you want a shortcut for the *data* only, step 2.9 shows an optional demo-data command, but the manual steps below create data through the UI so every button is exercised.

**Test data (fake):**

| Who | Email | Role | Scope |
|---|---|---|---|
| Alice (Org A owner) | `owner@alpha.test` | Organization Owner | all sites |
| Tom (Org A technician) | `tech@alpha.test` | Technician | organization-wide (from Phase 0) |
| Sam (new, Org A) | `sam@alpha.test` | Asset Manager | **site PUNE-1 only** (created in 6.1) |
| Bob (Org B owner) | `owner@beta.test` | Organization Owner | Org B |

Passwords: the ones you chose in Phase 0 (Sam chooses his own at activation). Never type a password inside a double-quoted PowerShell string (see `docs/INCIDENT_2026-10-03_LOGIN.md`).

Test records used below: sites **PUNE-1** "Pune Plant" and **PUNE-2** "Pune Annex"; categories **Generator**, **Pump**; assets **GEN-001** (generator), **GEN-001-ENG** (engine), **GEN-001-PMP** (pump), **ANX-001** (at PUNE-2).

---
## 0. Start the stack and run the automated checks
```powershell
cd C:\Users\HP\Downloads\fieldops-nexus
docker compose -p fieldops up -d --build
docker compose -p fieldops ps            # migrate = Exited (0) is normal
python scripts/smoke_stack.py http://localhost:8080
```
Open `http://localhost:8080/health/ready/`: `{"status": "ok", ...}`.
Then check that the new migrations were applied: `docker compose -p fieldops logs migrate --tail 15` shows `Applying sites.0001_initial`, `assets.0001_initial`, `rbac.0002_membership_role_site_scope`.
**Pass:** all PASS lines, health ok, migrations applied.

## 1. Sign in as Alice and find the new menu
| # | Do | Expect |
|---|---|---|
| 1.1 | Sign in as `owner@alpha.test` | Dashboard of Alpha Industries. Left menu has a new section **Assets & Locations** with *Sites & Locations* and *Assets*. |
| 1.2 | Click **Sites & Locations** | Empty list with the message "No sites match" and a **New site** button. |
| 1.3 | Click **Assets** | Empty list, **Categories** and **Register asset** buttons. |

## 2. M01: sites, locations, calendars, contacts
| # | Do | Expect |
|---|---|---|
| 2.1 | **New site**: Code `pune-1`, Name `Pune Plant`, City `Pune`, Country `in`, Timezone `Asia/Kolkata` → **Create site** | Green "Site PUNE-1 created." Detail page shows code in capitals, status **Active**, country `IN`. |
| 2.2 | Repeat 2.1 with code `PUNE-1` again | Red "A site with this code already exists." Nothing new is listed. Try an invalid time zone `Mars/Base` → red "Unknown timezone". |
| 2.3 | **Locations** tab → **Add location**: Name `Block A`, Type *Building*, parent *(top level)* | Success; row *Block A / Building / Active*. |
| 2.4 | **Add child** on Block A: Name `Ground floor`, Type *Zone / area*; then **Add child** on Ground floor: Name `Generator hall`, Type *Service area* | Tree rows are indented 3 levels. |
| 2.5 | Edit **Block A** → set Parent to *Generator hall* | Not offered in the list (a location cannot go below its own descendant). |
| 2.6 | Try to create a *Building* below *Block A* (Add child → Type Building) | Red "A building must be a top-level location". |
| 2.7 | **Calendars** tab → **New calendar**: Name `Day shift`, tick Mon-Sat, 08:00-18:00, tick *Default* → create. Add holiday `2026-12-25` / `Christmas`; add the same date again | First works (badge shown). Second: red "already has a holiday on that date". Remove the holiday with × works. Create a calendar with end time before start → red error, nothing saved. |
| 2.8 | **Contacts** tab → **Add contact**: `Site Manager`, phone `+91 20 5550 0101` (level empty); add `Regional Head`, email `regional@example.test` | Levels 1 and 2 appear in order. Adding a third with level 1 → red "Escalation level 1 is already used". |
| 2.9 | (Optional) Fast demo data: `docker compose -p fieldops exec web python manage.py seed_phase1_demo --org alpha-industries` | "Phase 1 demo data ready". Creates PUNE-1/MUM-1, locations, calendars, 5-level generator hierarchy, a meter with 3 readings. It uses the real services and is idempotent. Skip it if you want a clean test. |
| 2.10 | Create a second site **PUNE-2** `Pune Annex` (same way as 2.1) | Listed. The list shows *Locations* and *Active assets* counts. |

## 3. M02: categories and assets
| # | Do | Expect |
|---|---|---|
| 3.1 | **Assets → Categories**: create `Generator` and `Pump` | Listed. Creating `generator` again → red "already exists". Untick *Active* on Pump → Save, then tick again. |
| 3.2 | **Register asset**: Tag `GEN-001`, Name `Diesel generator 500 kVA`, Category Generator, Site PUNE-1, Location *Block A*, Manufacturer `Cummins`, Serial `CU-1`, Warranty ref `AMC-2026-14` → **Register asset** | Detail page "Asset GEN-001 registered", status **Active**, the Next bar offers only **Start maintenance**. The *Location* list only shows locations of the chosen site (change Site to PUNE-2 and the PUNE-1 locations disappear). |
| 3.3 | Register `GEN-001` again; then `gen-002` with serial `CU-1` and manufacturer `cummins` | Both refused: duplicate tag / "manufacturer and serial number already exists". Purchase date after commissioning date → red "cannot be before". |
| 3.4 | Register `ANX-001` (Generator) at **PUNE-2** | Success. |
| 3.5 | Assets list: use the filters (Site, Category, Status, search `cu-1`) and the paging | Only matching rows; "No assets match" when empty. |
| 3.6 | Open GEN-001 → **Edit** → change Name → Save | "Asset saved."; **History → Change log** shows `asset.updated` with `name: old → new`. |
| 3.7 | Edit GEN-001, change Site to PUNE-2 and put "Moved to annex" in *Reason*, then move it back | History → *Location history* lists both moves with the reason. (Moving is blocked while the asset has parents/children: tested in 5.8.) |

## 4. M02: lifecycle status, history, documents, meters
| # | Do | Expect |
|---|---|---|
| 4.1 | On GEN-001 type reason `Quarterly service` in the Next bar → **Start maintenance** | Status badge **Under Maintenance**; the bar now offers *Complete maintenance* and *Mark out of service* (no Retire/Dispose: not allowed from here). |
| 4.2 | Click **Mark out of service** with an empty reason | The browser asks for a reason (required); nothing changes. |
| 4.3 | **Complete maintenance** (reason `Done`), then **Start maintenance**, **Mark out of service**, **Return to service** | Each works with a reason. |
| 4.4 | **History** tab | *Status history* shows every change newest first: from → to, who, when, reason. *Change log* shows `asset.status_changed` with `status: ACTIVE → UNDER_MAINTENANCE` etc. Status cannot be edited anywhere else (the Edit form has no status field). |
| 4.5 | **Documents** tab → choose a small `.txt`/`.pdf`, Title `Manual`, Type *Manual* → **Upload** | Row with name, size, uploader. **Download** saves the file. Try a `.exe` or a renamed executable → red error, nothing stored. |
| 4.6 | **Meters** tab → Add meter `Run hours` / `h`; record `100`, then `120.5` | "Last reading 120.5 h" with date. Record `110` → red "lower than the previous reading". Record `-5` → rejected. A time in the future → rejected. |
| 4.7 | **Deactivate** the meter, try to record a reading | Refused ("meter is inactive"). Activate again. |
| 4.8 | (Retire path) On a spare asset: Start maintenance → Mark out of service → **Retire** (confirm dialog) | Status **Retired**; page says "read-only"; no Edit button; recording meter readings / adding components is refused. Retired assets cannot go back (no buttons). |

## 5. M03: hierarchy
| # | Do | Expect |
|---|---|---|
| 5.1 | On GEN-001 → **Hierarchy** tab → **Register a new child asset**: Tag `GEN-001-ENG`, Name `Engine assembly`, relationship *Assembly* | Created and attached in one step; its breadcrumb shows GEN-001. |
| 5.2 | Register another asset `GEN-001-COOL`; on GEN-001 use **Add existing asset as a child** (relationship *Assembly*); then on COOL register a child `GEN-001-PMP` (Pump, *Component*); on ENG register `GEN-001-FLT` as *Replaceable part*, quantity 2, part number `LF-3000` | **Asset tree** (loads via HTMX) shows GEN-001 → ENG (→ FLT ×2), COOL (→ PMP) with relationship and status badges; the current asset is marked "this asset". Assets list shows a *Parent* column. |
| 5.3 | Open GEN-001-PMP → Hierarchy | Parent card shows the path `GEN-001 › GEN-001-COOL`. |
| 5.4 | Self / cycle: on GEN-001-COOL, the *existing asset* list does not offer GEN-001 (its ancestor) or itself | Correct. (Forced attempts via API are in section 9.) |
| 5.5 | Move: open GEN-001-PMP → *Move* to `GEN-001-ENG` | Success; tree updated. Moving it onto itself is not offered. |
| 5.6 | **Detach** FLT from ENG (confirm) | FLT disappears from the tree but still exists in the Assets list. |
| 5.7 | Try to add `ANX-001` (site PUNE-2) as a child of GEN-001 | Not offered (different site). |
| 5.8 | Edit GEN-001-ENG and change its Site while it is in the hierarchy | Red "Detach the asset from its hierarchy before moving it to another site". |

## 6. Site-scoped access (the important security part)
| # | Do | Expect |
|---|---|---|
| 6.1 | As Alice: **Users → Invite user**: `sam@alpha.test`, name `Sam Scoped`, tick role **Asset Manager**, and under *Limit to sites* tick **PUNE-1 only**. Get Sam's activation link as in Phase 0 step 3.5 and activate | User detail shows the role as `Asset Manager @ PUNE-1`. In *Role assignments* you can also add/remove roles for one site or the whole organization. |
| 6.2 | Sign in as Sam | Menu shows Sites and Assets. **Sites** lists only PUNE-1. **Assets** lists only PUNE-1 assets (not ANX-001); the Site filter only offers PUNE-1. |
| 6.3 | Paste the ANX-001 detail URL (copy it from Alice's session, `/app/assets/<uuid>/`) and the PUNE-2 site URL | Both show **Not found** (same page as a non-existent record). Same for `/app/assets/<uuid>/tree/`, `?tab=history`, and the document download URL of an ANX-001 document. |
| 6.4 | Sam registers an asset at PUNE-1; edits PUNE-1 | Works. The site dropdown in the asset form only contains PUNE-1. |
| 6.5 | Sam tries `/app/sites/new/`, `/app/users/`, `/app/assets/categories/` (create) | **Access denied (403)** for site creation and users; categories page is view-only without a form. |
| 6.6 | In Alice's session change Sam's scope: add role Asset Manager for PUNE-2, remove the PUNE-1 assignment | Sam (refresh) now sees only PUNE-2. Audit trail shows `membership.roles_changed`. |
| 6.7 | Tom (organization-wide Technician) | Sees assets/sites of **both** sites, can open them, can **record meter readings**, but has no Edit/Register/status/upload buttons and gets 403 on those URLs. |

## 7. Tenant isolation (Org A vs Org B)
| # | Do | Expect |
|---|---|---|
| 7.1 | Sign in as Bob (`owner@beta.test`); create a site `B-1` and an asset `BX-1` | Bob sees only his own data. Copy the BX-1 URL and Beta's site URL. |
| 7.2 | In Alice's session open Bob's asset URL, site URL, `…/tree/`, `…?tab=history` | **Not found** every time. |
| 7.3 | Alice's lists/search/filters | Never contain Beta's records, counts or names. |
| 7.4 | Register an asset in Org A while submitting a location/site/category/owner id of Org B (API check in 9.4) | Rejected (404 / validation); nothing created. |

## 8. Audit trail
As Alice open **Audit Trail**. Search for `site.`, `zone.`, `asset.`, `calendar.`, `membership.`.
**Expect** entries for: `site.created/updated/deactivated`, `zone.created/updated`, `calendar.created/holiday_added/…`, `site.contact_added`, `asset.created/updated/location_changed/status_changed`, `asset.document_added`, `asset.meter_created/meter_reading_recorded`, `asset.component_added/moved/removed`, `membership.roles_changed` (with `@ PUNE-1`), each with the actor and before/after values. Tom and Sam (no audit permission) cannot open the audit page, but the asset **History → Change log** (permission *asset history*) shows the asset's own changes.

Also test the deactivation rules (as Alice):
- Site PUNE-1 → **Deactivate** with a reason while it has active assets → red message "Site has N active asset(s)…". Nothing changes.
- Retire/dispose or move all assets, then deactivate: badge **Inactive**, the reason is shown, *Add location / New calendar / Register asset* disappear, existing assets and history are intact. **Reactivate** brings it back.
- Deactivate a location that has an active child or asset → refused with the reason.

## 9. API checks (OpenAPI docs and security)
Open `http://localhost:8080/api/v1/docs/`: groups for **sites, zones, calendars, calendar-holidays, site-contacts, assets, asset-categories, asset-components, meters** are present, with typed `{id}` parameters (`GET /api/v1/schema/` generates without warnings).
Get a token (type the password in the prompt; do not put it in the command line):
```powershell
$cred = Get-Credential -UserName owner@alpha.test -Message "Alice"
$body = @{ email = $cred.UserName; password = $cred.GetNetworkCredential().Password } | ConvertTo-Json
$tok  = (Invoke-RestMethod http://localhost:8080/api/v1/auth/token/ -Method Post -ContentType application/json -Body $body).access
$h = @{ Authorization = "Bearer $tok"; "X-Organization" = "alpha-industries" }
Invoke-RestMethod http://localhost:8080/api/v1/assets/ -Headers $h | ConvertTo-Json -Depth 4
```
| # | Call | Expect |
|---|---|---|
| 9.1 | `GET /api/v1/assets/?site=<PUNE-1 id>&status=ACTIVE&q=gen&ordering=-asset_tag&page_size=2` | Paginated `{count,next,previous,results}`, filtered. |
| 9.2 | `PATCH /api/v1/assets/<id>/` with `{"status":"RETIRED"}` | **400**: "Status cannot be edited; use POST /assets/{id}/transition/". |
| 9.3 | `POST /api/v1/assets/<id>/transition/` `{"action":"retire","reason":"x"}` on an ACTIVE asset | **409** `invalid_transition`. A valid action returns 200 and `GET /api/v1/assets/<id>/history/` shows the new row; `/changes/` shows before/after. |
| 9.4 | `POST /api/v1/assets/` with a Beta `site`/`zone`/`category` id | **404** (not found), nothing created. |
| 9.5 | `POST /api/v1/assets/<GEN-001>/components/` `{"child":"<GEN-001 id>"}` / a descendant's parent | **400** `self_parent` / `hierarchy_cycle`. `POST …/validate-link/` is a dry run; `GET …/validate/` reports integrity. |
| 9.6 | `POST /api/v1/meters/<id>/readings/` `{"value": "50"}` below the last reading | **400** `meter_not_monotonic`. |
| 9.7 | Same calls with Tom's token | Reads **200**; writes **403**; unauthenticated **401**; `X-Organization: beta-utilities` **403** `not_a_member`. |
| 9.8 | Sam's token: `GET /api/v1/assets/<ANX-001 id>/` and `/history/` | **404**. `GET /api/v1/assets/` lists only PUNE-1 assets. |

## 10. Responsive layout, keyboard, session
1. Resize the browser (or use the dev tools device toolbar) to about 375 px wide: the sidebar collapses behind the menu button; pages (sites, assets list/detail/history/hierarchy) do not scroll sideways; tables scroll inside their card.
2. Tab through the Register asset form: focus outlines are visible, labels are read for every field, buttons are reachable.
3. Sign out and back in as Alice: data and history are unchanged (it comes from PostgreSQL). Inspect with `docker compose -p fieldops exec db psql -U fieldops -d fieldops -c "select asset_tag,status,site_id from assets_asset;"` (use the DB name from your `.env`).

## 11. Database integrity (optional, advanced)
`docker compose -p fieldops exec db psql -U fieldops -d fieldops -c "\d assets_assetcomponent"` shows the unique index on `child_id`, the check constraint `component_not_self` and `component_quantity_gte_1`; `\d assets_asset` shows `uniq_asset_tag_per_org` and `asset_commission_after_purchase`.

## Result sheet
Mark each PASS / FAIL (note the step number and what you saw).

| Area | Steps | Result |
|---|---|---|
| Stack, migrations, smoke | 0 | |
| Menu and empty states | 1 | |
| Sites, locations, calendars, contacts, deactivation rules | 2, 8 (deactivation) | |
| Categories and asset registration, uniqueness, move | 3 | |
| Lifecycle status, history, documents, meters | 4 | |
| Hierarchy, tree, move, detach, rules | 5 | |
| Site-scoped user (UI) | 6 | |
| Tenant isolation | 7 | |
| Audit trail | 8 | |
| API behaviour and security | 9 | |
| Responsive / keyboard / persistence | 10, 11 | |

When everything passes, tell me "Phase 1 approved" and I will mark it APPROVED in `docs/MODULE_STATUS.md`. Do not start Phase 2 until then.
