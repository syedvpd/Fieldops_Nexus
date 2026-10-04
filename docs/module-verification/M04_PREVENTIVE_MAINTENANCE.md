# M04: Preventive Maintenance

**What it answers:** What routine work must happen, when, and was it done?
**Accounts:** `planner@alpha.test` creates; the scheduler generates; `tech@alpha.test` executes; `supervisor@alpha.test` verifies.
**The full step-by-step with states is in `workflows/W3_PREVENTIVE_MAINTENANCE.md`.** This page is the module checklist.

## Screens
| Menu | What it shows |
|---|---|
| Maintenance → **Maintenance plans** | One plan per asset: priority, estimated hours, optional required checklist (M08) |
| Maintenance → **Due & upcoming** | Enabled schedules soonest first, state *Scheduled* or *Due*, **Generate now** |
| Maintenance → **PM history** | Completed cycles and their work orders |

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | **New plan** for an asset (Priority, Estimated hours, optional checklist) | Plan page with "Add a schedule" prompt |
| 2 | **Add schedule** time-based: every 1 week/day, first due date, window start/length, "generate N days early", reminder days | "Schedule created"; state Scheduled (future) or Due (today/past) |
| 3 | Meter-based schedule: pick the asset's meter and "every N units" | Becomes Due when readings pass the threshold |
| 4 | Wait for the scheduler (every 15 min) | New WO with source **scheduler**; next due advances (W3) |
| 5 | **Generate now** | Same outcome, source **manual** |
| 6 | Disable the schedule | No more work orders |
| 7 | Close the generated WO as supervisor | PM state **Verified** |

## Negative
Retired asset refused; zero/blank interval refused; technician cannot open plans (403); scheduler run twice makes one WO per cycle.

## Connected modules
M02 assets/meters · M06 generated work orders · M08 checklist · M11 SLA · M14 PM compliance KPI · Celery Beat (the real scheduler on Render).

## Pass when
A work order appears without anyone pressing a button and the cycle advances after verification.
