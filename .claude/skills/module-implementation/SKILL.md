---
name: module-implementation
description: Step-by-step recipe for implementing one FieldOps module (M01-M15) end to end in this codebase. Load at the start of every module/phase.
---
1. Read `docs/PROJECT_MAP.md`, `docs/MODULE_STATUS.md`, the phase prompt in `docs/blueprint/1x_PHASE_*.md`, and `04_MODULE_RESPONSIBILITIES.md` for the boundary. Do not re-read the whole blueprint.
2. Backend slice: models (extend `TenantOwnedModel`) + migration, `permissions.py`, `services.py` (+ StateMachine, audit), `selectors.py`, API (`TenantAPIMixin` + `permission_map`), tests (unit/API/RBAC/tenant/IDOR/invalid state).
3. UI slice: views (`TenantPermissionMixin`), templates on `shell.html`, `navigation.py`, tests that every button persists + audits.
4. Integration contract with neighbours: write `docs/integrations/<a>-<b>.md`; call the other module's service, never its tables' state directly.
5. Run targeted tests, then full `pytest`, `ruff`, `makemigrations --check`. Update MODULE_STATUS / TRACEABILITY / PROJECT_MAP, and write `docs/manual-tests/PHASE_N_*.md` (step-by-step manual test guide). Short report.
