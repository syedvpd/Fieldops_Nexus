# Phase 4 — M09 Inventory

Implement warehouse, part, stock balance, stock movement, reservation, issue, return, transfer, min/max and WO consumption.

State:
REQUESTED -> RESERVED -> ISSUED -> CONSUMED/RETURNED -> RECONCILED

All stock changes must be transactional, auditable and organization-scoped. Test rollback, insufficient stock, duplicate issue, return, concurrency-sensitive paths, wrong tenant and unauthorized access.
