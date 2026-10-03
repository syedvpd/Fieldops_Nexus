# HPE Traceability — FieldOps Nexus

## HPE project facts

- FieldOps Nexus — Enterprise Asset, Maintenance & Field Service ERP.
- Project code: HPE-PRD-2026-FOPS02.
- Minimum duration: 90 calendar days.
- Review gates: Day 30, Day 60, Day 90.
- GitHub evidence every 15 days.
- Stack: Python 3.11+, Django 4.2+, DRF, PostgreSQL 15+, Redis 7+, Celery 5+, REST/OpenAPI.
- The supplied HPE document is explicitly a draft technical project-allocation specification, not an executed commercial contract.

## HPE non-negotiables

Business workflows must use:
- database persistence;
- auditable state changes;
- backend-enforced RBAC.

HPE rejects:
- hardcoded mock screens;
- frontend-only workflows;
- fake form success messages;
- UI controls with no persistent backend action.

## Modules

1. M01 Site & Location Master
2. M02 Asset Registry
3. M03 Asset Hierarchy
4. M04 Preventive Maintenance
5. M05 Incident / Breakdown
6. M06 Work Order Management
7. M07 Technician Workspace
8. M08 Inspection & Checklist Engine
9. M09 Spare Parts & Inventory
10. M10 Warranty / AMC / Contract
11. M11 SLA & Escalation
12. M12 QR / Barcode Identification
13. M13 Client / Requester Portal
14. M14 Operational Dashboards
15. M15 Audit & Compliance

## HPE scopes

M01: organizations, sites, buildings/zones, service areas, operating calendars, contact hierarchy.

M02: asset ID, category, model, serial, purchase/commission dates, location, owner, warranty, status, documents.

M03: parent-child assemblies, components, replaceable parts, relationship tree.

M04: time/meter schedules, recurring generation, checklists, maintenance windows, reminders.

M05: failure reporting, severity, photos/files, asset linkage, downtime start/end, service impact.

M06: create, plan, prioritize, assign, dispatch, pause, complete, close WOs with labor/material/time.

M07: assigned jobs, route/site details, checklist, notes, attachments, parts, time, completion evidence.

M08: template-based safety/quality/maintenance checklists with mandatory fields and exception findings.

M09: warehouse/site stock, issue/return, reservations, min-max, transfer, WO consumption.

M10: coverage, service provider, SLA, exclusions, expiry, renewal alerts, eligible claim validation.

M11: response/resolution targets by priority, escalation, breach tracking, supervisor alerts.

M12: generate/scan asset labels to open asset profile or create service event.

M13: raise request, status, attachments, scheduled visit, closure details.

M14: MTTR, MTBF, downtime, open WOs, technician utilization, SLA breaches, PM compliance, parts consumption.

M15: audit logs, closure approvals, change history, evidence exports, role-controlled reports.

## Mandatory state machines

Service Request:
`NEW -> TRIAGED -> APPROVED / REJECTED -> WORK ORDER CREATED -> IN SERVICE -> RESOLVED -> CONFIRMED -> CLOSED`

Work Order:
`DRAFT -> PLANNED -> ASSIGNED -> DISPATCHED -> IN PROGRESS -> ON HOLD -> COMPLETED -> SUPERVISOR REVIEW -> CLOSED`

PM:
`SCHEDULED -> DUE -> GENERATED -> ASSIGNED -> COMPLETED -> VERIFIED -> NEXT CYCLE`

Part Request:
`REQUESTED -> RESERVED -> ISSUED -> CONSUMED / RETURNED -> RECONCILED`

Asset:
`ACTIVE -> UNDER MAINTENANCE -> OUT OF SERVICE -> ACTIVE / RETIRED / DISPOSED`

## Core entities

Organization, Site, Zone, User, Role, TechnicianProfile, Shift; Asset, AssetCategory, AssetComponent, AssetDocument, AssetMeter, AssetStatusHistory; MaintenancePlan, MaintenanceSchedule, ChecklistTemplate, ChecklistItem; ServiceRequest, Incident, WorkOrder, WorkOrderAssignment, LaborEntry, DowntimeRecord; Inspection, InspectionResponse, Finding, Attachment, ClosureApproval; Warehouse, Part, StockBalance, StockMovement, PartReservation, WorkOrderPart; Warranty, ServiceContract, SLAProfile, EscalationRule; Notification, AuditLog, ReportSnapshot, IntegrationEvent.

## Mandatory API groups

Assets: `/api/v1/assets/`, `/assets/{id}/history/`, `/meters/`

Maintenance: `/api/v1/maintenance-plans/`, `/schedules/`, `/generate-work-orders/`

Work Orders: `/api/v1/work-orders/`, `/assign/`, `/start/`, `/hold/`, `/complete/`

Inspections: `/api/v1/checklists/`, `/inspections/`, `/findings/`

Inventory: `/api/v1/parts/`, `/stock/`, `/reserve/`, `/issue/`, `/return/`

SLA: `/api/v1/slas/`, `/breaches/`, `/escalations/`

Portal: `/api/v1/client/requests/`, `/status/`

## Complex engineering requirements

- PM scheduler generates future WOs without duplicates and handles missed/overdue cycles.
- Assignment prevents invalid technician allocation.
- SLA distinguishes response vs resolution and pauses only in configured states.
- Inventory issue/return creates stock movement and maintains transactional consistency.
- Asset status/downtime uses controlled workflow transitions.
- WO closure requires checklist, resolution notes and required evidence according to work type.
- QR/barcode uses opaque non-secret identifiers.
- Celery handles reminders, SLA escalation, contract/warranty expiry alerts and report snapshots.

## Review gates

Day 30: Auth/RBAC, site hierarchy, asset registry/hierarchy, service request, WO core, checklist templates, DB schema, CI/CD.

Day 60: PM scheduler, assignment/dispatch, technician, inspections, inventory, SLA, notifications, beta dashboards.

Day 90: Warranty/AMC, client portal, QR, analytics, audit/export, security hardening, performance, tests, deployment, KT docs.
