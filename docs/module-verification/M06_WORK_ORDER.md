# M06: Work Order

**What it answers:** What work is being done, by whom, and has it been verified?
**Full walkthrough with every state: `workflows/W2_WORK_ORDER.md`.**
**Accounts:** `ops@alpha.test` / `planner@alpha.test` plan; `tech@alpha.test` executes; `supervisor@alpha.test` reviews.

## Screens
**Operations → Work Orders**: filters (site, status, priority, type: Corrective / Preventive / Inspection / Installation / Other, **Mine**). A work order page has tabs **Overview · Labor & material · Evidence · History** and the **Next steps** bar.

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | **New work order** (Title, Asset, Type, Priority) | Draft, `WO-00000N` |
| 2 | Plan → Assign → Dispatch → Start → (Hold/Resume) → Complete → Supervisor review → Close | W2 |
| 3 | **Labor** and **Material** forms (Labor & material tab) | Totals update |
| 4 | **Evidence** tab upload | Required for corrective/installation completion |
| 5 | Close without labor | Refused with the reason shown |
| 6 | **Return for rework** (reason) | Back In Progress; technician notified |
| 7 | **History** tab | Every transition with who/when/why |
| 8 | Work orders created from an incident / by PM / by hand all look the same | Source line shows "from INC-..." or "PM: ... (cycle N)" |

## Negative
Skipped states refused; closed WO read-only; technician sees only own jobs (Mine) and gets 404 on others'; Beta gets 404; stores user has read access to the list only.

## Connected modules
M05 (source request) · M04 (generated WOs) · M07 (technician screens) · M08 (checklist must be complete to finish) · M09 (parts) · M10 (coverage decision at creation) · M11 (SLA stops at completion) · M02 (asset status) · M14/M15.

## Pass when
Every state is reachable only in order, closing rules hold, and the audit/history list the full life of a WO.
