# M10: Warranty / AMC / Contract

**What it answers:** Is this asset covered (warranty, annual maintenance contract, service contract), by whom, until when, and is a claim eligible?
**Accounts:** `owner@alpha.test` / `service@alpha.test` manage; others view.

## Screens (Coverage menu)
**Warranties & contracts** (agreements) · **Expiring coverage** (what ends soon) · **Providers** (vendors).

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | **Providers → New provider** (name, contact) | Listed |
| 2 | **Warranties & contracts → New**: type (Warranty / AMC / Service contract), provider, covered asset(s), start and end dates, terms, **exclusions**, optional SLA profile | Saved; status Active |
| 3 | Open the asset → **Coverage** tab | "Covered by ..." with dates; outside the dates: "Not covered" |
| 4 | Create a work order on a covered asset | A **coverage decision** is stored with the work order (eligible / excluded and why) |
| 5 | Agreement ending soon | Shows in **Expiring coverage**; a renewal alert is sent automatically (every 6 h task) |
| 6 | End date before start date; retired asset | Refused |
| 7 | Agreement with an SLA profile | The incident on that asset uses that SLA (M11) |

## Negative
Planner cannot create agreements (403); Beta cannot see Alpha agreements.

## Connected modules
M02 assets (coverage tab) · M05/M06 (coverage decision on work orders) · M11 (coverage SLA) · Celery Beat (renewal alerts) · M15 audit.

## Pass when
Coverage appears on the asset and work order, dates and exclusions are respected, and expiry alerts fire.
