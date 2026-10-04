# Browser acceptance, Batch 1 (M01-M04)

Complete Playwright UI acceptance of every functionality exposed by M01-M04, run read-only (no production code changed).

| File | Content |
|---|---|
| `M01_BROWSER_DETAILED.md` .. `M04_BROWSER_DETAILED.md` | One report per module, 15 sections each (pages, buttons, forms, validation, RBAC, tenant, DB persistence, HTMX, errors, responsive, console/network, integration, findings, evidence, final status). Generated from the raw run files by `tools/gen_batch1_reports.py`; narrative sections (integration, findings) are written by the auditor in that file. |
| `../final/M01_M15_BROWSER_ACCEPTANCE.md` | Overall M01-M15 browser acceptance; the section between `BATCH1:START/END` is the Batch 1 summary and verdict. |
| `evidence/*.json` | Raw per-run results: every check (feature, page, role, action, expected, actual, database, audit, status), console/network captures, provoked errors, click/request coverage. `final_runs.json` lists which run files make up each module; `inventory_owner.json` is the discovery crawl (pages, links, buttons, forms, tabs, HTMX); `coverage.json` compares discovered controls with exercised ones. |
| `evidence/shots/` | Screenshots taken on failure or for key states. |
| `tools/playwright/` | The scripts. `bx.py` is the harness (role contexts, console/network/HTMX capture, in-page CSRF requests, SQL read-back, permission lookup `perm()`); `m01*.py` .. `m04*.py` are the test scripts; `xcheck.py` = anonymous/session-expiry/download probes; `coverage.py` computes control coverage. Paths and the QA database URL are specific to the audit sandbox (local throw-away PostgreSQL `fieldops_browser_qa`, app on 127.0.0.1:8098); credentials are read from a git-ignored file and are not stored here. |

Method summary: expected RBAC outcomes are derived from the role's permission set in the database; a denied action must be refused by the server (403/404) with the database unchanged, an allowed action must change the database as specified. Tenant isolation is tested in both directions with real objects of both tenants. Constraints that a browser would block (maxlength, date pickers, required) were removed in the page - or the request forged from the page with the session cookie and CSRF token - so that SERVER validation was what got tested; the client hint was asserted separately. Overdue/missed-occurrence behaviour was exercised by rewinding schedule counters in the QA database (the clock cannot be advanced); that check is labelled SIMULATED.
