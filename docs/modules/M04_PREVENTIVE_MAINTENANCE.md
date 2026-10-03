# M04 Preventive Maintenance

Part of the ONE integrated FieldOps Nexus ERP. Read `docs/PROJECT_SOURCE_OF_TRUTH.md` and `docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md` first.

- **Answers:** How do we maintain equipment before it fails?
- **HPE CONFIRMED scope (section 7.2):** Time/meter-based schedules, recurring job generation, checklists, maintenance windows, reminders.
- **Team owner / phase:** Prasad / Sub-TL / Phase 5
- **Authoritatively owns:** PM plans, schedules, windows, reminders; the PM lifecycle SCHEDULED -> DUE -> GENERATED -> ASSIGNED -> COMPLETED -> VERIFIED -> NEXT CYCLE.
- **Consumes:** M02 assets/meters, M03, M08 checklists, M01 calendars.
- **Provides:** Maintenance demand: generated Work Orders (owned by M06).
- **Boundary rules:** Creates demand only; M06 owns the WO. Scheduler idempotent, no duplicates, handles missed/overdue cycles, concurrency-safe.
- **Status:** NOT STARTED


Related: `docs/MODULE_STATUS.md`, `docs/TRACEABILITY.md`, `docs/DOMAIN_MODEL.md`, `docs/DECISIONS.md`, `docs/blueprint/04_MODULE_RESPONSIBILITIES.md`.
Done means: requirement, feature, database, service, permission, tenant isolation, API/view, UI, browser workflow, PostgreSQL verification, audit verification, integration verification, automated + negative + regression tests (see PROJECT_SOURCE_OF_TRUTH section 5).
