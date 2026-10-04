# Audit execution log

Date of run: 2026-10-04 (UTC). Branch `ccr-a9c54b8b-icbtpz`, HEAD `95dfc50` ("Uploads: optional S3-compatible storage ..."). Repository state before and after the audit: **no tracked file modified** (`git status` clean apart from the new `docs/audits/final/` deliverables). Phase 1 was a forensic, read-only pass over code, schema, configuration, migrations and tests.

## 1. Runtime set-up (documented before doing it; none touches the repository's code)

| Step | What | Where |
|---|---|---|
| 1 | Python 3.11.15 virtualenv, `pip install -r requirements.lock pytest pytest-django pytest-cov ruff playwright` | `/tmp/claude-0/audit/venv` (outside the repo) |
| 2 | Started the sandbox's local PostgreSQL 16 cluster (`service postgresql start`); created role `fieldops` (test password) and databases `fieldops` (pytest creates `test_fieldops`) and `fieldops_browser_qa` (audit app DB). Never Supabase, never the unknown :5432 from CLAUDE.md (that is a different machine) | local sandbox |
| 3 | Local Redis on **:6390** (`redis-server`), later reconfigured to write its dump under `/tmp` | local sandbox |
| 4 | Audit settings module `audit_settings.py` (extends the repo's own `config.settings.browser_qa`, moves `MEDIA_ROOT` to `/tmp/claude-0/audit/media`, plain static storage). Kept outside the repo; copy in `tools/` | scratchpad |
| 5 | `manage.py migrate` on the empty audit DB (fresh-database migration), then the repo's own `scripts/seed_browser_qa.py` (service layer; copy with the settings name patched in `tools/seed_audit.py`): platform admin, orgs **Alpha Field Services** and **Beta Industries**, 15 accounts (owner, admin, ops, supervisor, asset manager, planner, 2 technicians, stores, service manager, auditor, client; Beta owner + technician), sites, assets, hierarchy, PM plans, checklists, inventory, SLA profiles, AMC, portal client. Passwords random, written to a scratchpad file, never printed or committed | audit DB |
| 6 | `manage.py runserver 127.0.0.1:8098 --insecure --noreload` (DEBUG False, CSP on), Celery worker (`--pool=solo`) and Celery beat against Redis :6390 | local |
| 7 | Playwright 1.63 driving the pre-installed Chromium 1194 (`/opt/pw-browsers`), viewports 1920x1080, 1440x900, 1024x768, 390x844 | local |

Subagents: four read-only static auditors (security/tenancy/RBAC; M01-M03 + database; M04-M08; M09-M15 + Celery + deployment). They had SELECT-only access to the audit DB and no write tools usage; their reports are merged into the findings register with the evidence tag STATIC unless I reproduced the issue (RUNTIME).

## 2. Chronology (condensed)

1. Read `docs/PROJECT_MAP.md`, `MODULE_STATUS.md`, the earlier final reports, `TRACEABILITY.md`, the HPE digest (`docs/blueprint/01_HPE_TRACEABILITY.md`).
2. Launched the full test suite in the background; built the runtime environment; launched the four static auditors in parallel.
3. Playwright acceptance per module in dependency order: M01 -> M02 -> M03 -> M04 (PM) -> M06/M07/M08/M09 (PM-generated work order end to end: planner assign/dispatch, technician start/hold/resume/part request/checklist/labor/note/evidence/complete, stores reserve/issue/return, supervisor review/close) -> M05/M13 (client request to closed request) -> M11 (real elapsed-time SLA with Celery beat) -> M12 -> M10 -> M14 -> M15.
4. Re-verification at runtime of every HIGH/MEDIUM static claim that could be reproduced (M04-01, M05-01/02/03, M03-1, SEC-001/002, M13-001, M14-001, Redis/worker outages).
5. API sweep (70 list endpoints x 14 principals), cross-tenant ID substitution (52 detail + 104 action endpoints, both directions), RBAC write matrix (11 roles x 18 actions), HTML sweep (78 pages x 12 roles), owner crawl of 78 pages for CSP violations/JS errors/failed requests.
6. Adversarial probes: stored XSS/template injection in 6 entity types over 15 pages, CSRF, open redirect, login lockout/enumeration, logout invalidation, attachment IDOR (8 principals x 4 files), upload abuse (>10 MB, executable, fake PDF), mass assignment, JWT + foreign `X-Organization`.
7. Celery/Redis: worker stopped (queue + recovery), Redis stopped (API, HTML, invite, QR, readiness) and restored (auto-recovery of API, worker and beat), real beat executions (SLA monitor every 60 s, PM fan-out every 15 min, renewal alerts via worker).
8. Static/deployment: `ruff`, `manage.py check`, `check --deploy` (prod settings), `makemigrations --check`, `migrate --plan`, `spectacular --validate --fail-on-warn`, real gunicorn run under `config.settings.prod` (HTTPS redirect, HSTS, headers, Host validation, whitenoise, health).
9. Full pytest twice (plain and with coverage).
10. Reports written under `docs/audits/final/`.

## 3. Commands and results

| Check | Result |
|---|---|
| `pytest -q --create-db` (all tests, PostgreSQL 16) | **746 passed, 0 failed, 356 s** |
| `pytest --cov=src/apps` | 746 passed in 531 s; **93 % line coverage** (15 584 statements, 1 080 missed; lowest: `accounts/views.py` 70 %, `incidents/views.py` 77 %, `platform_admin/api_views.py` 78 %) |
| `ruff check src tests scripts` | All checks passed |
| `manage.py check` | no issues (1 silenced: `auth.W004`, documented) |
| `manage.py check --deploy` under `config.settings.prod` | no issues |
| `manage.py makemigrations --check --dry-run` | No changes detected |
| `manage.py migrate` on an empty DB / `migrate --plan` afterwards | all migrations apply; no planned operations |
| `manage.py spectacular --validate --fail-on-warn` | 0 warnings, 196 paths, 258 operations, 206 schemas |
| Production-settings gunicorn run | HTTP -> 301 to HTTPS; HSTS 1 y + preload; CSP nonce; COOP; Permissions-Policy; `Secure` CSRF cookie; bad Host -> 400; `/admin/` 404; whitenoise static 200; schema anonymous 401; `/health/ready/` ok; `/health/live/` over plain HTTP -> 301 (finding L42) |

## 4. Data written to the audit database (sandbox only)

Everything I created or changed exists only in `fieldops_browser_qa`: audit sites/assets/zones/calendars/contacts (`AUD-*`, `AST-*`, `H3*`, `XSS*`), categories, PM plans/schedules/cycles and about 20 work orders, requests (INC-000001..000010), checklist templates, parts/warehouses/stock movements, warranties/AMC, QR labels, scan events, SLA target/rule edits (HIGH target set to 1/3 minutes for the elapsed-time test), probe roles/members (all reverted: the Admin's temporary all-permission role was removed and the Admin returned to the "Organization Admin" role; a temporary Beta membership of an Alpha technician was deactivated; a portal account was disabled and re-enabled), and many audit rows. The backdated "BUGPROBE" PM plan (`tools/m04_edit_bug.py`) created WOs/SLA breaches with historical timestamps, visible as overdue/breached items in the dashboards; they are an artefact of that reproduction, not an application fault.

## 5. Harness corrections (results I discarded or re-classified)

The raw record of every scenario is `evidence/browser_results.jsonl` (410 lines). Lines the report treats as superseded are listed in `M01_M15_BROWSER_ACCEPTANCE.md` with the reason (my own script timing/ordering/expectation errors, all re-run correctly). Examples: the app's confirm dialog was not awaited (inspection completion, site deactivation), number inputs refuse text in the browser, labor/evidence were already present from an aborted earlier run, and "labor" gates **closure**, not completion. None of the superseded lines was counted as a pass or a defect.

## 6. Clean-up

Removed from the repository directory after use: `.coverage`, `.pytest_media/`, `.ruff_cache/`, `dump.rdb` (Redis), `staticfiles/` (collectstatic output). All were git-ignored or untracked; the working tree is identical to HEAD except `docs/audits/final/`.

## 7. Limits of this audit

- Docker/compose cannot run in the sandbox (no daemon): image build, compose stack, nginx and the HEALTHCHECK were reviewed statically and partly reproduced with gunicorn.
- Only Chromium; no Firefox/Safari/Edge; no physical camera (a Chromium synthetic capture device streamed a real label QR).
- No access to Supabase, Render, Brevo or GitHub Actions runs: production database role state, SMTP delivery and CI history are UNVERIFIED.
- No load/performance testing. Race conditions (zone moves, technician allocation, `_wind_down`) were identified statically, not reproduced.
- Python 3.11.15 here vs 3.12 in the Dockerfile.

---

## H. Browser acceptance Batch 1 (M01-M04), 2026-10-04

Read-only continuation of the browser acceptance with testing depth raised to every control of every page. Environment as in section 2 (DEBUG off, CSP on, `fieldops_browser_qa`, Redis, Celery worker + beat). Harness `docs/audits/browser/tools/playwright/bx.py`; scripts `m01a..e, m02a/b, m03, m04a..c, xcheck`; discovery crawl of 36 pages; control coverage computed against the crawl (`evidence/coverage.json`). Several scripts were re-run after fixing HARNESS mistakes of the auditor (maxlength truncation, type=number/date inputs, minlength reasons, wrong download URL prefix, SQL boolean formatting, test-data name collisions); only the final run of each script is published, and every run that was superseded this way was a harness error, not a product result. Overdue/missed-occurrence behaviour was simulated by rewinding schedule counters in the QA database (labelled SIMULATED). No production code was modified; no secrets were committed.
