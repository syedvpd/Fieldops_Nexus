# FieldOps Nexus — Master Blueprint & Claude Code Usage

This package is the working source of truth for building FieldOps Nexus, Project 2 of the HPE draft allocation document.

## How to use it

Do **not** give Claude one giant implementation instruction. Give it:
1. the HPE source;
2. the relevant blueprint files;
3. one phase prompt;
4. the repository.

Claude must first audit/read, then plan, then implement only the approved phase.

## Source-of-truth hierarchy

1. HPE requirements — mandatory where explicitly stated.
2. This blueprint — approved FieldOps Nexus implementation decisions where HPE is silent.
3. Existing repository — evidence of current implementation.
4. Agent suggestions — proposals only.

Never silently turn an implementation decision into an HPE requirement.

## Core architecture

FieldOps Nexus is ONE multi-tenant SaaS ERP.

Platform:
- Super Admin
- Organizations
- Platform settings/monitoring

Organization:
- Owner/Admin
- Users
- Roles
- Permissions
- Sites/Zones
- Assets
- Maintenance
- Incidents
- Work Orders
- Technicians
- Inspections
- Inventory
- Contracts
- SLA
- QR
- Client Portal
- Dashboards
- Audit

Operational data is isolated by organization.

## Important correction

Do NOT create separate credentials/accounts for every module.

Correct:
`Organization -> Users -> Roles -> Permissions -> permitted actions/data`

## Recommended development process

Phase 0: read-only forensic architecture audit, then shared foundation.

Phase 1: M01 -> M02 -> M03.

Phase 2: M05 + M06.

Phase 3: M08 + M07.

Phase 4: M09.

Phase 5: M04.

Phase 6: M11.

Phase 7: M10.

Phase 8: M12 + M13.

Phase 9: M14 + M15.

Final: HPE end-to-end acceptance audit.

For every phase:
plan -> implement -> unit/API/security/RBAC/tenant tests -> integration tests -> full regression -> Claude self-audit -> human manual test -> fixes -> approval.

## Never allow agents to

- DROP DATABASE
- DROP SCHEMA
- TRUNCATE application tables
- flush/reset/recreate DB
- delete unrelated data
- force-push
- rewrite Git history
- bypass tenant isolation
- bypass backend RBAC
- fake successful APIs
- hardcode dashboard metrics
- create dead buttons
- rewrite applied migrations destructively
- commit secrets

If uncertain about destructive or architecture-changing actions: STOP and ask the Team Lead.

## Final HPE journeys

1. Site + asset hierarchy + history.
2. PM plan -> automatic WO generation.
3. Technician -> checklist -> parts -> labor -> WO completion.
4. High-priority request -> SLA timers/escalation.
5. Inventory issue/return -> stock movement -> WO linkage.
6. QR/barcode -> asset -> service event.
7. Client request -> technician completion -> confirmation -> audit/dashboard.
