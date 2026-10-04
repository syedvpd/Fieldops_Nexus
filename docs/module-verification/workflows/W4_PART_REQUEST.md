# W4: Part Request (spare parts) workflow (module M09 with M06)

**HPE state machine:** REQUESTED → RESERVED → ISSUED → CONSUMED / RETURNED → RECONCILED

**Plain meaning:** a job needs a spare part. The part is requested, stock is set aside (reserved) so nobody else takes it, the storekeeper hands it out (issued), it is either used up (consumed) or brought back (returned), and finally stock and job records are matched (reconciled).

## Who does what
| Step | Who | Account |
|---|---|---|
| Set up parts, warehouses, receive stock | Stores Manager | stores@alpha.test |
| Request / reserve for a work order | Planner, Ops, Technician | planner@alpha.test / tech@alpha.test |
| Issue, return | Stores Manager | stores@alpha.test |

## One-time setup (Stores Manager)
1. **Inventory → Warehouses → New warehouse**: code `BLR-STORE`, name `Bangalore Main Store`, site `BLR-OPS`.
2. **Inventory → Parts → New part**: Part no. `BRG-6205`, Name `Bearing 6205`, Unit `pcs`; optional Min/Max/Reorder qty (drives "Low stock").
3. **Inventory → Stock → Receive stock**: warehouse BLR-STORE, part BRG-6205, quantity `10`, note `Initial receipt`. Expect On hand = 10, Reserved 0, Available 10. The **Movements** ledger gets a *Receipt* line.

## Walkthrough on a work order (W2 job, e.g. `GEN-001 bearing and service check`)
1. Open the work order → **Labor & material** tab → link **Spare parts & stock** (path `/app/work-orders/<id>/parts/`).
2. **Request + reserve:** choose part `BRG-6205`, quantity `3`, warehouse → reserve. Expect request **Reserved**; Stock page: On hand 10, **Reserved 3**, Available 7. Movements: *Reserve* (reserved Δ +3).
3. **Issue:** Stores Manager issues the reserved quantity → **Issued**. Expect On hand 7, Reserved 0 (Movements: *Issue*, on-hand Δ −3, tagged with the WO number).
4. **Consume or return:**
   - Used 2 of 3 → record consumption of `2` (the material appears under *Material used*: "Bearing 6205 · 2 pcs"): **Consumed**.
   - Bring the unused 1 back → **Return**: Movements *Return*, On hand +1: **Returned**.
5. **Reconcile:** when the WO is closed the quantities (issued = consumed + returned) are matched: **Reconciled**. A mismatch is reported instead of silently closing.

## Rules to prove
| Try | Expected |
|---|---|
| Reserve more than Available | Red "insufficient stock" |
| Issue more than reserved | Refused |
| Return more than issued | Refused |
| Negative or zero quantity | Refused |
| Technician opens Stock/Warehouses | Allowed to view (inventory.view) but cannot receive/adjust |
| Planner opens Stock adjustments | Not offered |
| Beta user searches `BRG-6205` | No result (separate company) |

## Also in this module
- **Transfer** between warehouses (Transfer out / Transfer in lines) and **Adjustment** (manual correction, always with a reason, always in the ledger).
- **Reservations** page lists open reservations; **Movements** is the append-only ledger (every change, who, why, on-hand before/after, work order).
- **Low stock only** filter on Stock.

## Connected modules
M06 (the work order owns the parts request; closing checks material) · M07 (technician sees/records parts on their job) · M14 (parts consumption KPI) · M15 (audit of each movement).

## Pass when
Stock figures follow every step arithmetically (receipt +10, reserve 3 → available 7, issue → on hand 7, return 1 → on hand 8), the ledger shows each line with the WO number, and invalid quantities are refused.
