# Manual test: Phases 7-9 (M10 warranty / AMC / contract, M12 QR / barcode, M13 client portal, M14 dashboards, M15 audit)

Use a QA database (never production). Users per role come from the seed (Owner, Operations, Planner, Technician, Supervisor, Stores,
Asset Manager, Service Manager, Auditor, site-scoped Auditor, two Clients) in organization Alpha and one Beta owner; passwords: the
test value of your seed. Result sheet at the end.

## M10 Warranty / AMC / contract (Asset Manager)
1. Providers > New provider "Grundfos Service" > saved, listed. Duplicate name > error, nothing created.
2. Asset P-100 > Coverage tab: "Not covered". Add warranty / contract (site and asset pre-filled): number GF-2026-001, 2026-01-01 to 2028-01-01, exclude "Preventive" > created. Expected: agreement page shows the asset, the exclusion; audit row `contract.agreement_created`.
3. Coverage tab again: work type Corrective > "Eligible. covered by warranty GF-2026-001"; Preventive > "Not eligible ... excludes preventive"; date 2029-01-01 > "expired".
4. Create a second WARRANTY for the same asset with overlapping dates > refused (overlap). An AMC with overlapping dates > allowed.
5. Edit an agreement; Deactivate with a reason (reason required); Reactivate; Renew (new number + end date) > renewal starts the day after; Renew again > refused. Expiring coverage page lists agreements ending within the window.
6. Open a work order for P-100: the coverage panel shows eligibility; "Record this check" appends a row (history).
7. Negative: technician / planner open `/app/contracts/agreements/` > 403; Operations can view but has no New / Edit buttons; Beta owner opening an Alpha agreement id > 404.

## M12 QR / barcode (Asset Manager, Technician, Beta owner)
1. Asset > Labels > Generate QR code, Generate barcode; "Printable label" shows both; Download SVG / PNG works. Generate QR again > refused (already active). Replace with a reason > old code stops working.
2. Scan page (or open the QR link while signed out > sign-in, then the asset page). Type the barcode code in lowercase > asset opens.
3. As Technician: from the scanned page create a problem report > INC-xxxxxx; the asset's Labels tab lists the scan with that request.
4. Beta owner opens an Alpha QR link > "Label not recognised"; revoked code > "revoked" notice, no report form; a client user > not recognised.
5. Phone with camera (optional): Start camera on the scan page > scanning a printed label submits the code.

## M13 Client portal (Service Manager, Client A, Client B)
1. Service Manager > Portal clients: enable Client A (only users with the Client / Requester role are offered), grant asset P-100; disable / enable works.
2. Client A signs in > lands on the portal; only P-100 is offered; submit a request with photos (max 5) > INC created, staff get a notification.
3. Staff triage, approve, create the work order, assign, dispatch (Technician name appears for the client only from dispatch), complete. Client sees progress, planned visit; "Resolved: please confirm" appears only after completion.
4. Client: "No, still not working" without reason > error; with reason > request returns to staff. Confirm > "Confirmed"; staff close it.
5. Negative: Client A opens Client B's request URL > 404; `/app/work-orders/`, `/app/audit/`, `/api/v1/work-orders/` > denied; a client cannot download staff files.

## M14 Dashboards (Operations, Auditor, Technician, site-scoped Auditor)
1. Create known data (e.g. 10 work orders, close 3). Operations dashboard: Open / Created / Completed / Closed equal your counts; change the dates and the site filter and re-check; compare with SQL.
2. Assets: record downtime on incidents (start / end) > downtime hours, MTTR, MTBF (needs a failure) as defined on the page; empty period shows "n/a".
3. Maintenance (PM compliance), Service (requests, SLA), Inventory (net parts issued) agree with the source pages.
4. Technician: only "My work". Site-scoped auditor: only his site; other site id in the URL > 404. Invalid dates > message, no crash.

## M15 Audit (Auditor, Operations, site-scoped Auditor)
1. Audit trail: filter by actor, record type, site, dates, category (Security, Approvals, Closures ...). Open an entry: before / after visible.
2. Compliance reports: open "Closures"; asset history by tag; work-order lifecycle by number.
3. Export results as CSV / XLSX / PDF: contents equal the filtered list; an `audit.exported` row appears. Operations can view but has no Export button; direct URL > 403.
4. No edit / delete control exists anywhere; `PATCH`/`DELETE` on `/api/v1/audit-logs/<id>/` > 405.

## Result sheet
| Step | Pass / Fail | Notes |
|---|---|---|
