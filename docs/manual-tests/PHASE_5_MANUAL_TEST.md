# Phase 5 manual test: M04 Preventive Maintenance

Run against a database with Phases 0-4 plus migrations `maintenance.0001` and `workorders.0003`. Users of one organization: a **Maintenance Planner** (P), a **Supervisor** (S), a **Technician** (T); a user of a second organization (B). Use a site with a default operating calendar and an asset with a meter ("Run hours", reading 1200). Do not paste passwords anywhere.

| # | Steps | Expected | Result |
|---|---|---|---|
| 1 | P: Maintenance plans > New plan: the asset, "500h service", priority High, checklist (optional) | Plan page, Active; duplicate name on the same asset refused | |
| 2 | P: Add schedule: meter-based, Run hours, every 500, counting from 0 | Next due **1500 h**, state Scheduled | |
| 3 | P: Add schedule: time-based, monthly, interval 1, first due date today | Next due = today, state **Due** | |
| 4 | P: Add the same time schedule again | Refused ("identical schedule") | |
| 5 | Wait for the scheduler (or run `generate_due_maintenance`) | One work order for the monthly schedule, PLANNED, planned window at the schedule's start time (site time; a non-working day moves to the next working day); PM history shows the cycle; the planner got a notification | |
| 6 | Run the scheduler again | Nothing new (one cycle, one work order) | |
| 7 | Open the generated work order | "Source: Preventive maintenance: 500h service, cycle #0"; type Preventive; required checklist listed in My Jobs once assigned; closure blocked until the checklist is completed | |
| 8 | T: record meter reading 1500 on the asset; run the scheduler | A second work order (meter cycle #3, threshold 1500); next threshold 2000 | |
| 9 | Record 2600; run the scheduler | One work order for threshold 2500 describing 1 missed occurrence; next 3000 | |
| 10 | Plan page > Generate now while a cycle's work order is open | Refused ("previous cycle's work order is still open") | |
| 11 | P: Disable the plan; run the scheduler after the next due date; re-enable | No order while disabled; after enabling, the next due is the next future occurrence (nothing replayed) | |
| 12 | S / T: open Maintenance plans | S may view only (no create / edit / generate buttons work: 403); T gets 403 | |
| 13 | B: open P's plan, schedule, history URLs | 404 | |
| 14 | Resize to 1920x1080, 1366x768, 768x1024, 390x844 on plans, plan, due, history | No horizontal page scroll | |

Database spot checks (read-only SQL): one `maintenance_maintenancecycle` per (schedule, sequence); every cycle has a work order whose `source_id` equals the cycle id and the same organization; no `source_id` appears twice among PM work orders; no cycle without a work order.

Result sheet: tester, date, build/commit, pass/fail per row, defects found.
