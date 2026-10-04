# W1: Service Request workflow (module M05, with M06 and M13)

**HPE state machine:** NEW → TRIAGED → APPROVED / REJECTED → WORK ORDER CREATED → IN SERVICE → RESOLVED → CONFIRMED → CLOSED

**Plain meaning:** someone reports a problem or asks for service. A manager checks it, decides yes or no, a work order is created for the job, the work is done, the reporter confirms the fix, and the request is closed.

## Who does what
| Step | Role | Account (Alpha) |
|---|---|---|
| Report | Anyone with "report incident": Technician, Client, Owner | tech@alpha.test, client@alpha.test, owner@alpha.test |
| Triage / approve / reject / create work order | Operations Manager or Owner | ops@alpha.test or owner@alpha.test |
| Do the work | Technician | tech@alpha.test |
| Confirm the fix | The reporter (client) or manager | client@alpha.test |
| Close | Manager | ops@alpha.test |

## Walkthrough (happy path)
1. **Report.** Sign in as `owner@alpha.test`. Left menu → **Incidents & Requests** → **Report incident**.
   Fill: Asset `GEN-001`, Type *Incident / breakdown*, Title `Generator will not start`, Description (anything), Severity *High*, Service impact *Partial outage* → **Submit report**.
   Expect: green "INC-00000N reported". Status badge **New**. The **SLA** tab shows Response and Resolution targets with due times (see M11).
2. **Triage.** On the request page the blue **Next:** bar offers **Triage**. Click it.
   Expect: status **Triaged**; the Timeline shows "Triaged" with time and user.
3. **Approve.** Click **Approve** (or **Reject** to test the other branch: it needs a written reason).
   Expect: **Approved**. A rejected request ends here as **Rejected** and cannot go further.
4. **Create work order.** Click **Create work order**. Pick a Technician and planned start/finish if asked.
   Expect: status **Work Order Created**; the *Work orders* box shows `WO-00000N`. Open the WO: its title is "INC-00000N: ..." and "from INC-00000N" is shown. (Continue in **W2**.)
5. **In service.** When the technician starts the WO, the request moves to **In Service** automatically.
6. **Resolved.** When the work order is completed/closed, the request becomes **Resolved**.
7. **Confirm.** The reporter confirms (client sees **Confirm resolution** or **Reopen** on the portal, see M13). Expect **Confirmed**.
8. **Close.** Manager clicks **Close**. Expect **Closed**; page is read-only.

## Things to check along the way
- **History tab / Timeline:** every status change with who, when, reason.
- **Notifications (bell, top right):** the right people are told (e.g. technician "WO assigned to you").
- **Audit Trail:** entries `incident.created`, `incident.status_changed`.
- **Client portal view:** log in as `client@alpha.test`: the client sees only their own requests, status and visit date, never internal notes, stock or SLA settings.

## Negative checks (must be refused)
| Try | Expected |
|---|---|
| Reject without a reason | Red "reason required" |
| Click Create work order on a request that is only **New** | Not offered / refused ("not allowed from this status") |
| A Stores Manager opens `/app/incidents/` | Access denied (403) |
| Beta user opens an Alpha request URL | Not found (404) |
| Edit a **Closed** request | Read-only, no buttons |

## Connected modules
M02 asset (the broken asset) · M06 work order · M11 SLA clock starts at report time and can breach/escalate · M13 client portal creates the same requests · M10 coverage (warranty/AMC) is checked when the WO is created · M15 audit.

## Pass when
Every state in the chain was reached in order, a skipped step is impossible, the request and its work order stay linked, and each step appears in the history and audit.
