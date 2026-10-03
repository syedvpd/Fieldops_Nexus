# UI Navigation & Actions

One FieldOps Nexus ERP shell; not 15 separate applications.

## Platform navigation
Super Admin:
- Organizations
- Platform Monitoring
- Platform Audit
- Settings

## Organization navigation
- Dashboard
- Organization
- Users & Roles
- Sites & Locations
- Assets
- Asset Hierarchy
- Preventive Maintenance
- Incidents / Requests
- Work Orders
- Technician Workspace
- Inspections
- Inventory
- Warranty / AMC / Contracts
- SLA
- QR / Barcode
- Client Portal / Requests
- Reports
- Audit / Compliance

## Key actions

M01: list/create/edit sites, zones, service areas, calendars, contacts.

M02: list/create/edit assets, documents, meters, history/status.

M03: hierarchy tree, add component/child, relationship management.

M04: plan, schedule, due/overdue, reminders, generate/preview WO.

M05: create, triage, approve/reject, evidence, downtime, create/link WO, resolve/confirm/close request. Do not execute detailed WO lifecycle here.

M06: create, plan, prioritize, assign, dispatch, start, hold/resume, labor/time, materials, complete, supervisor review, close.

M07: My Jobs, start, checklist, notes, files, parts, time, resolution, evidence, complete.

M08: template builder, inspection, mandatory validation, findings, exceptions.

M09: warehouses, parts, stock, reserve, issue, return, transfer, movements, min/max.

M10: warranties/contracts, coverage, exclusions, expiry, renewal, eligibility.

M11: SLA profiles, targets, pause rules, escalations, breaches.

M12: generate label, preview/print, scan, asset resolution, service event.

M13: create request, status, attachments, schedule, closure/confirmation.

M14: KPI/operations/maintenance/SLA/inventory/technician/asset dashboards.

M15: audit list/detail, history, approvals/evidence, export, reports.

## Button rule

Every state-changing button must invoke a real backend action that checks permission, tenant, object and state, persists the transaction, audits where required and has tests. No dead buttons.
