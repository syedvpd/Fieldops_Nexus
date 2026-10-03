# Final database integrity report (2026-10-03)

Read-only SELECTs against the QA database `fieldops_qa_final` after the browser journeys (real rows written through the UI/services) plus a
generic invariant sweep in the test suite (`tests/test_final_integration.py::integrity_sweep`).

| Check | Result |
|---|---|
| Work order -> asset in another organization | 0 |
| Service request -> asset in another organization | 0 |
| Work order site differs from its asset's site | 0 |
| Covered asset in another site / organization than its agreement | 0 |
| More than one ACTIVE identifier per asset and kind | 0 (also DB partial unique index) |
| Duplicate identifier tokens | 0 (DB unique index) |
| Negative stock, or reserved > on hand | 0 (also DB checks) |
| Stock balance differs from the sum of its movements | 0 |
| More than one PM work order per cycle source | 0 (DB unique index) |
| More than one SLA breach per tracking and target | 0 |
| Portal grants pointing at another organization's asset | 0 |
| Audit rows without organization (tenant events) | 0 |
| Audit immutability trigger present | yes (`audit_auditlog_immutable`) |

Generic sweep: for EVERY tenant-owned model and EVERY foreign key to another tenant-owned model, `fk.organization = row.organization`
(no cross-tenant relation exists after the continuous journey, the two-tenant fuzz and the persona matrix).

Migrations added in this run (all additive, nullable or new tables): `contracts.0001`, `identification.0001`, `portal.0001`, `audit.0003`
(adds nullable `site_id` + two indexes; the row trigger is unaffected). **Not applied to Supabase** (needs the Team Lead's go-ahead; review
`migrate --plan` first). Known limit: a table-owner `TRUNCATE` bypasses the row trigger: the production application role must not hold
TRUNCATE (release checklist).
