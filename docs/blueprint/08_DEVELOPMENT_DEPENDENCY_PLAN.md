# Development Dependency Plan

## Order

Phase 0: shared foundation.

Phase 1: M01 -> M02 -> M03.

Phase 2: M05 + M06.

Phase 3: M08 -> M07.

Phase 4: M09.

Phase 5: M04.

Phase 6: M11.

Phase 7: M10.

Phase 8: M12 + M13.

Phase 9: M14 + M15.

Final: complete HPE E2E audit.

## Dependency graph

`M01 -> M02 -> M03`
`M02 -> M04`
`M02 -> M05`
`M05 -> M06`
`M06 -> M07`
`M06 -> M08`
`M06 -> M09`
`M04 -> M06`
`M05/M06 -> M11`
`M02/M06 -> M10`
`M02 -> M12`
`M13 -> M05/service request`
`all operational modules -> M14`
`all critical modules -> M15`

## First vertical slice

`Organization -> Site -> Asset -> Incident -> Work Order -> Technician -> Checklist -> Completion -> Audit`

Then plug in PM, Inventory, SLA, QR, Client Portal and Dashboards.

## Module approval

A module is not approved only because tests pass.

Require:
- code;
- DB/migration;
- API;
- RBAC;
- tenant isolation;
- state machine;
- UI;
- integration;
- unit/API/security tests;
- regression;
- manual business test;
- docs.
