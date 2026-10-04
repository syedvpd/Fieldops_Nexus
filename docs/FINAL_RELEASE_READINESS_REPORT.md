# Final release readiness (2026-10-03)

Branch `claude/final-modules` (worktree `.claude/worktrees/final-modules`), commits on top of `main` a4e8186: M10, M12, M13+M14+M15,
final integration tests, HPE-named API aliases, docs. **Not merged, not deployed, not applied to Supabase.**

| Item | State |
|---|---|
| Migrations | 4 new, additive: `contracts.0001`, `identification.0001`, `portal.0001`, `audit.0003`. `makemigrations --check` clean. Apply to Supabase only on the Team Lead's go-ahead: `migrate --plan` first (see `docs/DEPLOYMENT.md`), then re-sync role templates (new permissions: `contract.*`, `qr.*`, `portal.*`, `report.view`, `audit.export`; `audit.view` became site-scoped) |
| New dependencies | `segno`, `python-barcode`, `openpyxl`, `reportlab` (+ `et-xmlfile`, `charset-normalizer`), pinned in `requirements.lock`; rebuild the Docker image |
| Environment variables | none new |
| Celery beat | new `contract-renewal-alerts` (6-hourly); existing SLA and PM schedules unchanged |
| Static files | new `js/qr_scan.js` (run `collectstatic` in the image build as before) |
| OpenAPI | generates with 0 warnings (`spectacular --validate --fail-on-warn`) |
| Lint / checks | `ruff check src tests` clean; `manage.py check` clean |
| Tests | see MODULE_STATUS (full run on local PostgreSQL 16, test database created by pytest, never Supabase) |
| Health / logging / error handling | unchanged (health endpoints, JSON logs with request id, project 403/404/500 pages) |
| Security | `docs/FINAL_SECURITY_AUDIT.md`: no Critical / High; S-1 CSP and S-2 TRUNCATE privilege are Medium and must be on the deployment checklist |
| Backups / rollback | rollback of the 4 migrations is safe (new tables / nullable column); audit trigger untouched; take a Supabase backup before applying |
| Open decisions for the Team Lead | (1) run the M01-M08 visible browser audit now or later (conflicting instructions this run); (2) approve applying the migrations to Supabase and merging; (3) entity naming G-1 (TechnicianProfile / Shift / ClosureApproval); (4) KPI formulas D-052 (8 h/day capacity, MTBF definition) are our decisions, confirm or change |
