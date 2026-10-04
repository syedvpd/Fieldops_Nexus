# M05: Incident / Breakdown & Service Request

**What it answers:** Something broke or someone needs service: what is the status and who owns it?
**Accounts:** report as `tech@alpha.test` / `owner@alpha.test`; manage as `ops@alpha.test`.
**Full state-by-state walkthrough: `workflows/W1_SERVICE_REQUEST.md`.**

## Screens
**Operations → Incidents & Requests** (list, filter by site/status/severity/type) → **Report incident** (form) → request page with tabs **Overview · Evidence · History · SLA**, the **Next:** action bar and a Timeline.

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | Report: Asset, Type (*Incident / breakdown* or *Service request*), Title, Description, Severity, Service impact, optional "when did it happen" and "downtime started" | "INC-00000N reported", status **New**; downtime start marks the asset's downtime |
| 2 | **Evidence** tab → upload a photo/PDF | Listed; disallowed type refused |
| 3 | Triage → Approve (or Reject with reason) → Create work order | Chain of W1 |
| 4 | **Edit** the request (title/description) while open | Saved; History records it |
| 5 | **Downtime** box: set started/ended and **Save downtime** | Feeds M14 downtime/MTTR |
| 6 | **SLA** tab | Response and Resolution due times and state (M11) |
| 7 | Report from a QR scan (M12) | Request created with the asset prefilled |
| 8 | Client portal request (M13) | Appears here as a normal request |

## Negative
Stores Manager gets 403 on the list; Beta cannot open Alpha requests (404); closed requests are read-only; reject needs a reason.

## Connected modules
M02 asset · M06 work order · M11 SLA clock · M12 scan-to-report · M13 portal · M10 coverage check · M14 MTTR/downtime/open incidents · M15 audit.

## Pass when
A report travels New → Closed with its work order, SLA clock and history intact.
