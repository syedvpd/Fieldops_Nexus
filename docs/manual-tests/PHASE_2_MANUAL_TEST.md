# Phase 2 manual test guide: Incidents / Requests (M05) and Work Orders (M06)

Goal: prove by hand the complete reactive breakdown journey (report -> triage -> approve -> work order -> plan -> assign -> dispatch -> execute -> labor/material/evidence -> complete -> review -> close -> confirm -> close) with real persistence, audit, RBAC and tenant isolation.
Time: about 60 minutes.

**Prerequisites:** Phase 1 data exists (site, an active asset), e.g. the Supabase QA data: Alpha Industries, site `BLR-OPS`, create one asset first (Assets > Register asset, e.g. `GEN-BLR-001`). Phase 2 migrations must be applied (`core.0001`, `incidents.0001`, `workorders.0001`): `powershell -File .claude/run_prod.ps1 manage.py migrate --noinput`.
Phase 2 is **not yet applied to Supabase and not yet exercised in the browser pane**; do that first (migrate, collectstatic, restart the app).

**Accounts** (passwords: see your git-ignored `.env.qa-users`; never paste them anywhere):

| Who | Email | Role | Used for |
|---|---|---|---|
| Alice | `owner@alpha.test` | Organization Owner | everything |
| Tom | `tech@alpha.test` | Technician | reports, executes assigned work |
| Pat | `planner@alpha.test` | Maintenance Planner | creates / plans / assigns / dispatches |
| (add) Sue | `supervisor@alpha.test` | Maintenance Supervisor | review and close (invite via Users > Invite) |
| (add) Olly | `ops@alpha.test` | Operations Manager | triage / approve / confirm |
| Rita | `reader@alpha.test` | Auditor | read-only |
| Bob | `owner@beta.test` | Org B owner | tenant isolation |

Create Sue and Olly in the UI (Users > Invite user, choose the role, activate via the link) or give those roles to existing test users.

## 1. Menus and empty states
| # | Do | Expect |
|---|---|---|
| 1.1 | Sign in as Alice | Menu section **Operations** with *Incidents & Requests* and *Work Orders*. |
| 1.2 | Open both | Empty lists with "No requests match" / "No work orders match" and the **Report incident** / **New work order** buttons. |
| 1.3 | Sign in as Rita (reader) | Both lists visible; **no** Report / New buttons. |

## 2. Report the breakdown (M05)
| # | Do | Expect |
|---|---|---|
| 2.1 | As Tom: Incidents > **Report incident**: Asset `GEN-BLR-001`, Type *Incident*, Title `Generator tripped`, Severity *High*, Service impact *Full outage*, Downtime started = 1 hour ago | Redirect to the request page, number `INC-000001`, status **New**, severity High. Overview shows downtime "still down". |
| 2.2 | Report again with title `ab` | Red error, nothing created (HTTP 400). |
| 2.3 | Tom opens the request | No Triage / Approve buttons. Typing `/app/incidents/<id>/transition/triage/` is not possible by GET; the POST would be 403 (covered by automated tests). |
| 2.4 | Tom: **Evidence** tab, upload a small `.txt`/`.jpg`; then try an `.exe` | First stored (listed, Download works), second red error. |
| 2.5 | As Olly/Alice: open the request, **Edit**, change severity to *Critical*, Save | Saved; History tab / Audit Trail shows `incident.updated`. |

## 3. Triage and approval
| # | Do | Expect |
|---|---|---|
| 3.1 | As Olly: **Triage** | Status **Triaged**; History tab: New -> Triaged, actor Olly. |
| 3.2 | **Reject** with an empty reason (button asks for a reason) | Nothing changes. (Do NOT reject this one; use a second request to test reject: reason `Duplicate`, status **Rejected**, no further buttons.) |
| 3.3 | **Approve** | Status **Approved**; the green panel "Approved: create the work order" appears; Edit disappears. |

## 4. Work order from the request (M05 -> M06)
| # | Do | Expect |
|---|---|---|
| 4.1 | As Pat: open the request > **Create work order** (leave fields blank) | Redirect to work order `WO-000001`, status **Draft**, priority *Critical -> Urgent*, source request link to INC-000001. The request shows **Work Order Created** and lists the WO. |
| 4.2 | Try **Create work order** again | The panel is gone; a second one is refused (409). |
| 4.3 | Work order page as Pat: next steps show only **Plan** and **Cancel** (no Close) | Correct. |
| 4.4 | **Plan**: start/end tomorrow 09:00-13:00, estimated 3.5 h, priority High | Status **Planned**. End before start -> red error. |
| 4.5 | **Assign**: choose Tom | Status **Assigned**; Tom gets a notification (bell). Assigning a user who cannot execute work (e.g. Rita) is not offered. |
| 4.6 | **Dispatch** | Status **Dispatched**. |

## 5. Execution (M06, as the technician)
| # | Do | Expect |
|---|---|---|
| 5.1 | As Tom: Work Orders shows only WO-000001 (his assignment). Open it, **Start work** | Status **In Progress**; the request is now **In Service**. |
| 5.2 | **Put on hold** with reason `Waiting for hose`; then **Resume** | **On Hold** (reason shown) -> **In Progress**. Hold without a reason is refused. |
| 5.3 | **Labor & material** tab: Date today, hours `2.5`; material `Coolant hose`, qty `2` | Rows listed, total hours 2.5. Hours `0`, `25`, `-1` and a future date are refused. |
| 5.4 | **Complete** with notes `Replaced the hose and bled the system.` before attaching evidence | Refused: evidence required. |
| 5.5 | **Evidence** tab: upload a file (an `.exe` is refused); then **Complete** again | Status **Completed**; the request becomes **Resolved**; downtime shows an end time (ended by the work order). |

## 6. Review, close, confirm
| # | Do | Expect |
|---|---|---|
| 6.1 | As Sue: **Start supervisor review** | Status **Supervisor Review**. |
| 6.2 | **Close** | Closed (labor exists, notes exist, evidence exists). To see the guard, repeat the journey on a second work order and try to close without labor: red "cannot be closed yet: No labor / time has been recorded". |
| 6.3 | Optional rework: **Return for rework** (reason) instead of close | Work order back to In Progress, request back to In Service. |
| 6.4 | As Olly: on the request **Confirm resolved**, then **Close** | **Confirmed** -> **Closed**; History tab lists all 8 states with actors. Reopen (reason) from *Resolved* instead sends it back to **Approved** so a new work order can be made. |

## 7. Negative, RBAC and tenant checks
| # | Do | Expect |
|---|---|---|
| 7.1 | As Rita (reader): open the request and work order | Visible, **no** action buttons; direct POSTs return 403. |
| 7.2 | As Tom: paste the URL of a work order not assigned to him | **Not found**. |
| 7.3 | As Bob (Beta): paste Alice's request/work-order URLs, their `?tab=history`, the evidence download URL | **Not found** every time; Bob's lists show none of Alice's data. |
| 7.4 | A site-scoped user (Asset Manager/Operations Manager limited to one site) | Sees only that site's requests and work orders; others are Not found. |
| 7.5 | Audit Trail (Alice): search `incident.` and `work_order.` | Entries for created, updated, status_changed (with action/reason/source), downtime_recorded/updated, labor_recorded, material_recorded, evidence_added, reassigned, each with actor and before/after. |

## 8. API checks (OpenAPI at `/api/v1/docs/`, groups `service-requests` and `work-orders`)
Get a token as in the Phase 1 guide, then (with `X-Organization: alpha-industries`):
| # | Call | Expect |
|---|---|---|
| 8.1 | `GET /api/v1/work-orders/?status=IN_PROGRESS&q=pump&ordering=-created_at` | Paginated, filtered. |
| 8.2 | `PATCH /api/v1/work-orders/<id>/` `{"status":"CLOSED"}` (also on service-requests) | **400** "Status cannot be edited". |
| 8.3 | `POST /api/v1/work-orders/<draft id>/transition/` `{"action":"close"}` | **409** `invalid_transition` (403 first if the caller lacks `work_order.close`). |
| 8.4 | `POST /api/v1/service-requests/<id>/transition/` `{"action":"resolve"}` | **400** (work-order driven step). |
| 8.5 | `POST /api/v1/work-orders/<id>/transition/` `{"action":"assign","technician":"<Beta membership id>"}` | **404**, nothing changes. |
| 8.6 | Tom's token: `POST /api/v1/work-orders/` | **403**; reads of unassigned orders **404**. |

## Result sheet
| Area | Steps | Result |
|---|---|---|
| Menus, empty states | 1 | |
| Report + evidence + edit | 2 | |
| Triage / approve / reject | 3 | |
| Work order from request | 4 | |
| Execution, hold, labor, material, evidence, complete | 5 | |
| Review, close, confirm, reopen | 6 | |
| Negative / RBAC / tenant / site scope | 7 | |
| API | 8 | |

When everything passes, tell me "Phase 2 approved". Phase 3 (M08/M07) starts only after that.
