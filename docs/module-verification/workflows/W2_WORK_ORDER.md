# W2: Work Order workflow (module M06, with M07, M08, M09)

**HPE state machine:** DRAFT → PLANNED → ASSIGNED → DISPATCHED → IN PROGRESS → ON HOLD → COMPLETED → SUPERVISOR REVIEW → CLOSED

**Plain meaning:** a job is drafted, planned (when/where), given to a technician, sent out, worked on (it can be paused), finished by the technician, checked by a supervisor, and closed.

## Who does what
| Step | Role | Account (Alpha) |
|---|---|---|
| Create, plan, assign, dispatch | Planner / Operations Manager / Owner | planner@alpha.test, ops@alpha.test |
| Execute (start, hold, labor, parts, complete) | Technician | tech@alpha.test (Tom) |
| Review, close or return for rework | Maintenance Supervisor | supervisor@alpha.test (Sam) |

## Walkthrough
1. **Create (Draft).** Sign in as `ops@alpha.test` (or owner). **Work Orders → New work order**. Fill: Title `Bearing and service check`, Asset `GEN-001`, Type *Preventive*, Priority *Medium*. Save. Expect status **Draft**, number `WO-00000N`.
2. **Plan.** On the WO page click **Plan**; enter planned start and finish (e.g. tomorrow 09:00-12:00). Expect **Planned**.
3. **Assign.** Click **Assign** → choose *Tom Technician*. Expect **Assigned**; Tom gets the notification "WO assigned to you".
4. **Dispatch.** Click **Dispatch**. Expect **Dispatched**; Tom is told "ready to start".
5. **Execute.** Sign out, sign in as `tech@alpha.test`. **My Jobs** shows the job (also under Work Orders → *Mine*). Open it.
   - Click **Start** → **In Progress**.
   - (Optional) **Put on hold** with a reason → **On Hold**; **Resume** → back to **In Progress**.
   - Open the **Labor & material** tab. **Labor**: Date today, Hours `2`, Notes `Bearing replaced` → **Record labor** (total shows 2.00 h).
   - **Material used**: item, quantity → **Record material**; or use **Spare parts & stock** to reserve/issue real stock (see W4).
   - Type **Resolution notes** and click **Complete** → **Completed**. (Corrective/installation jobs also need at least one file on the **Evidence** tab; a required checklist must be finished first, see M08.)
6. **Supervisor review.** Sign in as `supervisor@alpha.test`. Open the WO → **Start supervisor review** → **Supervisor Review**.
7. **Decide.** Either **Close** → **Closed** (read-only, "This work order is closed and read-only"), or **Return for rework** (reason required) → back to **In Progress**; the technician is notified and repeats step 5.

## Rules to prove (these are real checks, not decoration)
| Try | Expected |
|---|---|
| Supervisor clicks **Close** when no labor was recorded | Red "The work order cannot be closed yet: No labor / time has been recorded." (enforced by the server) |
| **Return for rework** with empty reason | Refused ("Reason (required)") |
| Technician opens a WO assigned to someone else | Not found |
| Skip a state (e.g. Dispatch a Draft) | Button not offered / refused |
| Edit a **Closed** WO | Read-only |
| Complete a WO whose checklist is not finished | Refused with the missing items listed |

## What changes elsewhere
- **Asset (W5):** WO start/finish can move the asset Under Maintenance and back (rule in M06/M02).
- **Service request (W1):** request becomes In Service / Resolved with the WO.
- **Inventory (W4):** reserved/issued/returned parts show in Stock and Movements, tagged with the WO number.
- **SLA (M11):** the resolution clock stops when the WO completes.
- **Audit:** every transition is recorded; the **History** tab shows who/when.

## Pass when
All states were reached via the buttons, the close rule and the rework loop worked, the technician only saw their own jobs, and the audit trail shows each step.
