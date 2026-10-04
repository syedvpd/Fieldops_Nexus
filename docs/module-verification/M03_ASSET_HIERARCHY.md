# M03: Asset Hierarchy

**What it answers:** What is this machine made of (parent → assembly → component → replaceable part)?
**Accounts:** `assets@alpha.test` (or owner).

## Walkthrough (on asset `GEN-001`)
| # | Do | Expect |
|---|---|---|
| 1 | Open GEN-001 → **Hierarchy** tab → **Register a new child asset**: Tag `GEN-001-ENG`, Name `Engine assembly`, relationship *Assembly* | Child created and attached in one step; its breadcrumb shows GEN-001 |
| 2 | Register `GEN-001-COOL`, then on GEN-001 use **Add existing asset as a child** (relationship *Assembly*) | Appears under GEN-001 |
| 3 | On COOL register child `GEN-001-PMP` (relationship *Component*) | 3-level tree |
| 4 | On ENG register `GEN-001-FLT` as *Replaceable part*, quantity `2`, part number | Shown with quantity |
| 5 | Open `GEN-001-PMP` → Hierarchy | Parent card shows the path `GEN-001 › GEN-001-COOL` |
| 6 | On COOL look at the "existing asset" list | Does **not** offer GEN-001 (its ancestor) or itself: no loops |
| 7 | **Move** PMP under ENG | Tree updated |
| 8 | **Detach** FLT (confirm) | Leaves the tree but still exists in Assets |
| 9 | Try to add an asset from another site as a child | Not offered (same site only) |
| 10 | Edit ENG and change its Site while attached | Red "Detach the asset from its hierarchy before moving it to another site" |

## Negative / security
Technician cannot attach/detach (403). Beta user cannot open the tree address (404). Retired assets cannot get new components.

## Connected modules
M02 (each node is a normal asset) · M05/M06 (work can be raised on a component and rolls up to its parent for history) · M09 (replaceable parts link to the parts catalogue).

## Pass when
Parent/child changes work and loops, cross-site links and orphan site moves are refused.
