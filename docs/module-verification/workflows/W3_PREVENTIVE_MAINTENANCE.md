# W3: Preventive Maintenance (PM) workflow (module M04)

**HPE state machine:** SCHEDULED → DUE → GENERATED → ASSIGNED → COMPLETED → VERIFIED → NEXT CYCLE

**Plain meaning:** a repeating service is scheduled (e.g. every week). When the date arrives it becomes due, the system automatically creates a work order, the work is assigned and completed, a supervisor verifies it, and the next cycle is scheduled.

## Who does what
| Step | Who | Account |
|---|---|---|
| Create plan + schedule | Maintenance Planner / Ops / Owner | planner@alpha.test |
| Generate work order | **The scheduler (Celery Beat) automatically**, every 15 minutes | no user |
| Assign + execute | Planner assigns; Technician works | tech@alpha.test |
| Verify | Supervisor (closing the WO) | supervisor@alpha.test |

## Walkthrough
1. **Plan.** Sign in as `planner@alpha.test` (or owner). **Maintenance → Maintenance plans → New plan**. Asset `ENG-001`, Name `ENG-001 inspection`, Priority *Medium*, Estimated hours `1` → **Create plan**.
2. **Schedule.** On the plan page click **Add schedule**. Based on *Time-based*, Repeats every `1` *Day(s)*, **First due date = today**, window length 2 h → **Create schedule**.
   Expect: "Schedule created: every 1 day". Schedule state **Due** (today's date has arrived). If the date were in the future the state would read **Scheduled**.
3. **Wait for generation (do not click "Generate now").** The scheduler runs every 15 minutes. Refresh the plan page; after the next tick the **Generated work** table shows a row: source **scheduler**, a `WO-00000N`, PM state **Generated**, and the schedule's Next due moves to tomorrow (that is NEXT CYCLE). The Work Orders list now has `PM: ENG-001 inspection (cycle 0)`.
   *(Manual alternative for demos: **Generate now** on the schedule. It is the same code, but source will say "manual".)*
4. **Assign and execute.** Open the generated WO → assign Tom → dispatch → Tom starts, records labor, completes (exactly as W2).
5. **Verify.** Supervisor starts review and **Closes** the WO. On the plan page the PM state becomes **Verified**.
6. **Next cycle.** The following tick generates cycle 1 on the next due date.

## Other schedule types and rules
- **Meter-based:** pick a meter on the asset (e.g. run hours) and "every N units". When recorded readings pass the threshold the schedule becomes Due.
- **Generate early:** "Generate the work order N days early" creates the WO ahead of the due date; **Remind planners N days before** sends reminders.
- **Missed cycles:** if the system was down, one catch-up work order is created (not one per missed day).
- **Disable** a schedule or plan to stop generation. Disabled items do not generate.
- **Due & upcoming** page (Maintenance menu) lists enabled schedules, soonest first, with *Generate now*.
- **PM history** lists completed cycles.

## Negative checks
| Try | Expected |
|---|---|
| Plan for a Retired asset | Refused |
| Schedule with interval blank or 0 | Red message |
| Technician opens Maintenance plans | Access denied (403) |
| Run the scheduler twice | Only one WO per cycle (idempotent) |

## Connected modules
M02 asset and meters · M06 work order (the generated job) · M08 required checklist on the plan · M11 SLA profile if configured · M14 PM compliance KPI on the dashboard · M15 audit.

## Pass when
A WO appears from the scheduler on its own (source "scheduler"), the next due date advances, and verification happens only after the supervisor closes the job.
