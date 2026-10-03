# Phase 2 — M05 Incident + M06 Work Orders

Keep separate state machines.

M05:
NEW -> TRIAGED -> APPROVED/REJECTED -> WORK ORDER CREATED -> IN SERVICE -> RESOLVED -> CONFIRMED -> CLOSED

M06:
DRAFT -> PLANNED -> ASSIGNED -> DISPATCHED -> IN PROGRESS -> ON HOLD -> COMPLETED -> SUPERVISOR REVIEW -> CLOSED

M05 owns failure, severity, evidence, asset, downtime, impact, triage/approval and request lifecycle.
M06 owns planning, priority, assignment, dispatch, execution, hold, labor/time/material, completion, review and closure.

M05 may create/link a real M06 WO. Do not execute the M06 lifecycle inside M05.

Test the complete reactive breakdown journey with real DB persistence, RBAC, tenant isolation, audit and negative tests.
