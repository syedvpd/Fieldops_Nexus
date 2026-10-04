# M08: Inspection & Checklist Engine

**What it answers:** What must be checked, and what was found?
**Accounts:** `planner@alpha.test` or `owner@alpha.test` designs templates; `tech@alpha.test` fills them in.

## Screens
**Operations → Checklists** (templates) and **Operations → Inspections** (filled-in instances).

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | **Checklists → New checklist**: Name `Generator preventive service`, add items of different types (pass/fail, number, text, choice), mark some **mandatory** | Template saved; items ordered |
| 2 | Attach the checklist to a PM plan ("Required checklist" field) or a work order | Shown on the plan/WO |
| 3 | Technician opens the job → checklist: answer items; give a numeric value outside limits or choose *Fail* | A **finding / exception** is recorded for the failed item |
| 4 | Leave a mandatory item blank → try **Complete** the work order | Refused, missing items listed |
| 5 | Fill all mandatory items → **Complete** | Allowed |
| 6 | **Inspections** list: open the filled inspection | Responses, findings and evidence visible; read-only after completion |
| 7 | Edit a template that already has inspections | Old inspections keep their original version |

## Negative
Technician cannot edit templates (403); Beta cannot open Alpha templates (404); a completed inspection cannot be changed.

## Connected modules
M06 (required checklist blocks completion) · M04 (plan requires a checklist each cycle) · M02 (inspections are per asset) · M15 (audit of responses).

## Pass when
Mandatory items block completion, failed items create findings, and completed inspections are locked.
