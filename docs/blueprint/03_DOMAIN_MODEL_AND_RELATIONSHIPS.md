# Domain Model & Relationships

## Core model

Organization = tenant boundary.

User = identity.

Role/Permission = authorization.

Site/Zone/Service Area = physical/operational location.

Asset = central managed physical object.

AssetComponent = child assembly/component.

AssetDocument = asset evidence.

AssetMeter = usage reading.

AssetStatusHistory = lifecycle history.

MaintenancePlan/Schedule = preventive maintenance.

ServiceRequest/Incident = reported service/failure event.

WorkOrder = operational execution.

WorkOrderAssignment = technician assignment.

LaborEntry = labor/time.

DowntimeRecord = asset downtime.

ChecklistTemplate/Item = reusable inspection definition.

Inspection/Response/Finding = execution evidence.

Warehouse/Part = inventory master.

StockBalance/Movement = inventory state/history.

PartReservation/WorkOrderPart = WO-linked inventory.

Warranty/ServiceContract = coverage.

SLAProfile/EscalationRule = timing/escalation.

Notification = communication.

AuditLog = immutable/append-only critical evidence.

ReportSnapshot = persisted report data if required.

IntegrationEvent = integration/domain event tracking.

## Relationships

Organization has Users, Roles, Sites, Assets, Maintenance Plans, Service Requests, Work Orders, Warehouses, Contracts, SLA Profiles and Audit Logs.

Site belongs to Organization and contains Zones/Service Areas and Assets.

Asset belongs to Organization and location, has category, components, documents, meters, status history and may be referenced by maintenance, incidents, WOs, warranty and QR.

ServiceRequest/Incident belongs to Organization, references Asset, contains evidence/downtime and links to WorkOrder.

WorkOrder belongs to Organization, may originate from Incident/ServiceRequest or PM, references Asset, assignments, inspections, labor, parts, evidence and closure approval.

MaintenancePlan targets assets and schedules; scheduler creates WOs.

Inventory is Organization-scoped: Warehouse -> Part -> StockBalance; StockMovement records every stock-changing transaction; reservations and WO parts link inventory to work.

Warranty/Contract covers assets/services and influences eligibility/alerts.

SLAProfile maps service/priority to timing and escalation rules.

## Transaction rules

Use DB transactions for:
- assignment/state transitions;
- inventory reservation/issue/return;
- PM generation;
- closure approval;
- critical asset status/downtime changes.

Use foreign keys, indexes, unique constraints and safe delete behavior.

## Audit

Critical actions must preserve actor, action, time and relevant before/after state.
