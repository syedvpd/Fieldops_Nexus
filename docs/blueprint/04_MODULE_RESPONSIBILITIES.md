# M01-M15 Responsibilities

M01 Site & Location: sites, buildings/zones, service areas, operating calendars, contacts.

M02 Asset Registry: asset master, category, serial/model, dates, location, owner, warranty reference, status, documents, meters.

M03 Asset Hierarchy: parent/child assemblies, components, replaceable parts, relationship tree.

M04 PM: plans, time/meter schedules, maintenance windows, reminders, recurring generation. Does not own detailed WO execution.

M05 Incident/Breakdown: failure, severity, evidence, asset linkage, downtime, service impact, triage/approval, service-request lifecycle, create/link WO.
Boundary: M05 = why service is needed; M06 = how work is planned/executed.

M06 Work Orders: create, plan, prioritize, assign, dispatch, start, hold, labor/time/material, complete, supervisor review, close.

M07 Technician Workspace: technician-facing jobs, site/route, checklist, notes, evidence, parts/time and completion. M06 remains authoritative for WO state.

M08 Checklist/Inspection: templates, items, inspections, responses, findings, mandatory fields, exceptions.

M09 Inventory: warehouse/site stock, parts, balances, reservations, issue/return/transfer, min-max, consumption and movements.

M10 Warranty/AMC/Contract: coverage, provider, terms, exclusions, expiry, renewal and eligibility.

M11 SLA: response/resolution targets, pause rules, escalations, breaches and alerts.

M12 QR/Barcode: opaque identifier, label, scan, asset resolution, service event.

M13 Client Portal: client/requester request, status, attachments, schedule, closure/confirmation.

M14 Dashboards: real-data KPIs and role-scoped analytics.

M15 Audit/Compliance: audit views, history, approvals/evidence, exports and role-controlled reports.

No module may bypass tenant isolation, backend RBAC, another module's authoritative workflow or required audit.
