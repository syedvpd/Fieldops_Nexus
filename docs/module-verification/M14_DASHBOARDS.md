# M14: Operational Dashboards

**What it answers:** How is operations performing, with numbers I can trace to real records?
**Accounts:** `ops@alpha.test`, `owner@alpha.test` (full); `tech@alpha.test` (personal summary only).

## Screens
- **Insights → Dashboards** (`/app/dashboards/`): sections for MTTR, MTBF, downtime, open work orders, technician utilization, SLA breaches, PM compliance, parts consumption. Filters at the top: **Site**, **From / To** dates.
- **Insights → My work summary**: the signed-in user's own numbers.
- Overview → **Dashboard** (home): users, pending invitations, roles, recent activity.

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | Open Dashboards | Cards and tables filled from real data (no fixed numbers) |
| 2 | Change **Site** and date range | Figures change accordingly |
| 3 | Cross-check one number: e.g. "Open work orders" equals the count of non-closed items on Work Orders | Same |
| 4 | Close a work order and refresh | The open count drops and the closed/MTTR figures change |
| 5 | SLA breaches card after a breach (M11) | Count increases |
| 6 | PM compliance after a generated PM WO is verified | Moves |
| 7 | Hover/open the KPI definition | Formula and source are stated |
| 8 | Technician: Dashboards address | Access denied; **My work summary** works |
| 9 | Site-limited user | Only figures for their sites |
| 10 | Beta user | Only Beta's figures |

## Connected modules
Reads from M02, M04, M05, M06, M09, M11; shows only what the user's role and site scope allow.

## Pass when
Every figure can be traced to its records and responds to filters, role, site and company.
