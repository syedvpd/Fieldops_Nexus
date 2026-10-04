# M09: Inventory (spare parts)

**What it answers:** Which parts do we have, where, and where did they go?
**Full part-request walkthrough: `workflows/W4_PART_REQUEST.md`.**
**Account:** `stores@alpha.test` (Stores Manager).

## Screens (Inventory menu)
| Screen | Use |
|---|---|
| **Parts** | Catalogue: Part no., Name, Unit, Min/Max, Reorder qty, Active/Inactive |
| **Warehouses** | Stock locations per site |
| **Stock** | On hand / Reserved / Available per warehouse; **Receive stock**, **Transfer**, *Low stock only* |
| **Reservations** | Stock set aside for work orders |
| **Movements** | Append-only ledger: Receipt, Issue, Return, Transfer out/in, Adjustment, Reserve, Release |

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | **Warehouses → New warehouse** `BLR-STORE` at site BLR-OPS | Listed |
| 2 | **Parts → New part** `BRG-6205` Bearing 6205, unit pcs, min 2 | Listed; duplicate part number refused |
| 3 | **Stock → Receive stock** 10 | On hand 10; Movements *Receipt* |
| 4 | **Transfer** 2 to a second warehouse | Two ledger lines (out/in); totals unchanged |
| 5 | Manual **Adjustment** with a reason (e.g. count correction) | Ledger line with reason; reason required |
| 6 | Reserve / issue / return against a work order | See W4 |
| 7 | Set min stock above on-hand → **Low stock only** filter | Part appears |
| 8 | Reserve more than available | Red "insufficient stock" |

## Negative
Planner/technician cannot receive or adjust; Stores has no access to incidents or plans (403); Beta cannot see Alpha parts.

## Connected modules
M06 (work orders reserve/issue/return) · M07 (technician records material) · M03 (replaceable parts) · M14 (parts consumption) · M15 (movement audit).

## Pass when
Stock figures always equal the sum of ledger lines and invalid quantities are refused.
