# M13: Client / Requester Portal

**What it answers:** How does an outside customer ask for service and follow it?
**Accounts:** staff set up clients with `owner@alpha.test` / `service@alpha.test`; the client signs in as `client@alpha.test` (Carla Client).

## Staff side (Service menu → **Portal clients**)
| # | Do | Expect |
|---|---|---|
| 1 | **Portal clients → Add client**: client name, user email/name, the **assets or sites the client may see** | Client user invited (activation email via Brevo); listed with their assets |
| 2 | Change the assets a client may see; deactivate a client | Takes effect at once |

## Client side
| # | Do | Expect |
|---|---|---|
| 3 | Sign in as `client@alpha.test` | A simple **portal**, not the staff menu: dashboard, requests, new request |
| 4 | **New request**: choose one of **their** assets, title, description, severity, attach a photo → submit | Request created (appears for staff as a normal incident in M05, status New) |
| 5 | Open the request | Status, scheduled **visit** date, timeline and files, closure details. No internal notes, stock, SLA settings or technician controls |
| 6 | When staff finish (resolved), client clicks **Confirm** (or **Reopen** with a reason) | Confirmed → staff can Close; Reopen returns it to work |
| 7 | Try another client's request address, or an asset not assigned | Not found |
| 8 | Try staff addresses (`/app/work-orders/`, `/app/users/`) | Access denied |

## Connected modules
M05 (client requests are service requests; W1 states) · M06 (visit comes from the work order) · M02 (only authorised assets) · M11 (SLA runs on portal requests) · M15 (audit).

## Pass when
A client can raise, track and confirm their own requests only, and sees nothing internal.
