# Phase 4 manual test: M09 Spare Parts & Inventory

Run against a database that has the Phase 0-3 data plus migrations `inventory.0001` and `workorders.0002`. Use QA users of one organization: a **Stores Manager** (S), a **Technician** (T, assigned to a work order that is IN PROGRESS), a **Maintenance Planner** (P) and an **Auditor** (R); plus one user of a second organization (B). Do not paste passwords anywhere.

| # | Steps | Expected | Result |
|---|---|---|---|
| 1 | S: Parts > New part: `SEAL-100`, "Mechanical seal", min 2, max 20, reorder 10 | Part page shown, status Active; same number again (any case) is refused with a message | |
| 2 | S: Warehouses > New warehouse: site PLANT1, code `MAIN` | Warehouse page; a duplicate code is refused | |
| 3 | S: Stock > Receive stock: MAIN, SEAL-100, quantity 10, reference PO-1. Try 0, -1, `abc` | 10 on hand, 0 reserved, 10 available, one RECEIPT movement; bad quantities refused, stock unchanged | |
| 4 | T: open the work order in My Jobs > Spare parts > request SEAL-100 x 4 | Line REQUESTED; stock unchanged (Stores sees 10) | |
| 5 | T: open /app/inventory/stock/ and a Reserve/Issue endpoint | 403 Access denied; no Reserve/Issue buttons in the workspace | |
| 6 | S: work order > Parts page > Reserve 3 from MAIN | Reserved 3, available 7; RESERVE movement | |
| 7 | S: Issue 4 from MAIN | On hand 6, reserved 0; ISSUE movement (-4 / -3 reserved); line ISSUED, outstanding 4 | |
| 8 | S: Issue 1 more | Refused ("more than the requirement"); stock unchanged | |
| 9 | S: Return 99 | Refused (more than outstanding); stock unchanged | |
| 10 | T: workspace > Used 3 | Consumed 3; work order > Labor & material shows the line with a "stock" badge; stock unchanged | |
| 11 | S: Return 1; Reconcile | On hand 7; line RECONCILED | |
| 12 | Supervisor: try to close a work order that still has issued, unconsumed parts | Closure blocker lists the part | |
| 13 | S: Transfer 2 of SEAL-100 MAIN > VAN1 | Two movements (OUT / IN), balances 5 / 2 | |
| 14 | S: Stock detail > Adjust -1 with reason "count"; try -50 | Adjusted; -50 refused | |
| 15 | P / R: try Receive, Transfer, Adjust | 403 (R may view stock) | |
| 16 | B: open S's part, warehouse, stock, work-order parts URLs | 404 for each | |
| 17 | S: Movements page, filter by type and warehouse | Ledger rows match steps 3-14 (who, when, deltas) | |
| 18 | Resize to 1920x1080, 1366x768, 768x1024, 390x844 on Parts, Stock, WO Parts | No horizontal page scroll, tables scroll inside their card | |

Database spot checks (read-only SQL): `on_hand` of a balance equals the sum of its movements' `on_hand_delta`; `reserved` equals the sum of ACTIVE reservations; no movement where the warehouse organization differs from the movement's; no negative balances.

Result sheet: tester, date, build/commit, pass/fail per row, defects found.
