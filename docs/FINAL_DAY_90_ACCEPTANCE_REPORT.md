# Final Day-90 acceptance report (2026-10-03)

Two layers. **Automated** = real services / HTTP entry points, no direct row injection except where noted. **Browser** = built-in pane on the
local QA database. A journey is VERIFIED only when both layers cover its principal path.

| # | HPE journey | Automated evidence | Browser evidence | Status |
|---|---|---|---|---|
| 1 | Register site / asset hierarchy; status and change history | `test_one_asset_lives_through_every_module` (zone, asset, component, QR, status history), Phase 1 tests | seed built through services; asset page, Hierarchy / History tabs not driven in this run | PARTIALLY VERIFIED |
| 2 | PM plan > scheduler generates WO (no duplicate) | same test (scheduler twice = 1 order), `test_m04_*`, concurrency | QA DB (Phase 5 report) | VERIFIED |
| 3 | Assign technician > checklist > parts > labor > complete WO | same test (checklist, reserve / issue / consume, labor, evidence, review, close), Phase 3-4 journeys | QA DB (Phase 4); staff screens for checklist / WO not re-driven | PARTIALLY VERIFIED |
| 4 | High-priority request > SLA timers > escalation | `test_m11_*`, `test_integration_p456` | QA DB (Phase 6 report) | VERIFIED |
| 5 | Inventory issue / return > movement > WO linkage | `test_m09_*`, ledger consistency in the final journey (stock 10 > 8) | QA DB (Phase 4 report) | VERIFIED |
| 6 | QR / barcode > open asset > create service event | `test_m12_identification`, final journey | **this run**: generate, label, scan (barcode typed), QR link, report, cross-tenant denial; DB rows + audit verified | VERIFIED (camera path not exercised) |
| 7 | Client request > technician completion > client confirmation > closure; audit and dashboard | `test_full_client_journey_over_ui_and_backend`, final journey | **this run**: client submits (mobile width), sees progress / visit, confirms; staff close; auditor sees dashboards and audit; all values reconciled with SQL. Staff-side execution steps were driven by a service script, not by clicks | VERIFIED (staff clicks not driven) |

Master journeys beyond the seven: tenant isolation (two-tenant fuzz + browser denial) VERIFIED; RBAC persona matrix VERIFIED (API); site
scope VERIFIED (automated); continuous M01-M15 scenario VERIFIED (automated, `tests/test_final_integration.py`).
