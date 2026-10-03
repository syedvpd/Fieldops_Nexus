# Phase 1 — M01/M02/M03

Implement/verify:
M01 Site & Location
M02 Asset Registry
M03 Asset Hierarchy

Flow:
Organization -> Site -> Zone -> Asset -> Hierarchy

Require real persistence, tenant isolation, backend RBAC, audit, asset history, documents, meters, controlled status and hierarchy integrity.

Do not put PM, Incident, WO, Inventory or SLA business logic here.

Test happy paths, invalid data, wrong organization, wrong role, IDOR, state/history, hierarchy and fresh migrations. Run regression and give manual test instructions.
