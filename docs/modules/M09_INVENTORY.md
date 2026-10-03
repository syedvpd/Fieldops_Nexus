# M09 Spare Parts & Inventory

Part of the ONE integrated FieldOps Nexus ERP. Read `docs/PROJECT_SOURCE_OF_TRUTH.md` and `docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md` first.

- **Answers:** What stock exists, and what moved?
- **HPE CONFIRMED scope (section 7.2):** Warehouse/site stock, issue/return, reservations, min-max, transfer, consumption against work orders.
- **Team owner / phase:** Prasad / Sub-TL / Phase 4
- **Authoritatively owns:** Warehouses, parts, balances, reservations, issue/return/transfer/consumption, movement history; Part Request REQUESTED -> RESERVED -> ISSUED -> CONSUMED/RETURNED -> RECONCILED.
- **Consumes:** M06 work orders, M01 sites, M03 part_number bridge.
- **Provides:** Stock truth and parts consumption for M14.
- **Boundary rules:** Every issue/return creates stock-movement records; transactional; concurrency and rollback tested; never plain `quantity -= N`.
- **Status:** NOT STARTED


Related: `docs/MODULE_STATUS.md`, `docs/TRACEABILITY.md`, `docs/DOMAIN_MODEL.md`, `docs/DECISIONS.md`, `docs/blueprint/04_MODULE_RESPONSIBILITIES.md`.
Done means: requirement, feature, database, service, permission, tenant isolation, API/view, UI, browser workflow, PostgreSQL verification, audit verification, integration verification, automated + negative + regression tests (see PROJECT_SOURCE_OF_TRUTH section 5).
