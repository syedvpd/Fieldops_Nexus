# Deployment readiness audit

**Verdict: Deployment CONDITIONAL.** The application boots correctly under the production settings, enforces HTTPS/HSTS/secure cookies/Host validation, serves static files, exposes health endpoints, shuts down gracefully and fails fast. Blocking/conditional items: the DB-hardening vs migrate-on-start conflict (F-M18), the unapplied production role split and audit TRUNCATE gap (F-H02), and everything that could not be exercised in this sandbox (Docker daemon, Supabase, Render, SMTP, Python 3.12). Nothing in this report was applied to any remote system.

Evidence key: **RUN** = executed here (gunicorn / `scripts/render_start.py` with `config.settings.prod`, local PostgreSQL + Redis); **STATIC** = read only; **UNVERIFIED** = could not be established.

| Area | Status | Evidence |
|---|---|---|
| `manage.py check --deploy` (prod settings) | RUN: no issues | |
| Production boot under gunicorn | RUN | `config.settings.prod` + 53 migrations on an empty DB (supervisor `RUN_MIGRATIONS_ON_START=true`), health `live`/`ready` 200 |
| HTTPS redirect, HSTS | RUN | plain HTTP -> 301 to https; `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` behind `X-Forwarded-Proto: https` |
| Cookies | RUN | CSRF cookie `Secure; SameSite=Lax`; session cookie HttpOnly, SameSite Lax (12 h) |
| Security headers | RUN | CSP (nonce), X-Frame-Options DENY, nosniff, Referrer-Policy same-origin, Permissions-Policy, COOP same-origin |
| ALLOWED_HOSTS / Host header | RUN | `Host: evil.example` -> 400 |
| DEBUG / error pages | RUN + STATIC | DEBUG False; project 404/500 pages; DRF 500 envelope generic with request id; `/admin/` 404 |
| Static files | RUN | `collectstatic` (35 files, 85 post-processed, hashed names) and whitenoise serving `/static/css/app.css` 200 |
| Media / uploads | STATIC | local disk by default; S3-compatible private bucket via `AWS_STORAGE_BUCKET_NAME` (`querystring_auth`, no ACL); downloads only through the permission-checked view |
| Health endpoints | RUN | `/health/live/` (process), `/health/ready/` (DB + cache; 503 when Redis is down). **`/health/live/` over plain HTTP answers 301** under prod settings, so the Docker HEALTHCHECK (which follows the redirect over http) cannot pass (L42); Render's own probe behaviour on a 301 is UNVERIFIED |
| Logging | RUN | structured JSON with request id on every line; access log; no secrets observed |
| Graceful shutdown | RUN | `SIGTERM` to `scripts/render_start.py`: gunicorn "Shutting down: Master", beat "Shutting down", both children exit 0 in **2.2 s** |
| Fail-fast supervision | RUN | `SIGKILL` on the Celery child: supervisor stopped the web child and exited **non-zero (247)**, so the platform restarts the container instead of leaving it half-dead |
| Restart / startup behaviour | RUN + STATIC | migrate-on-start works with an owner role; interval beat schedules restart from zero (F-M12); free-tier sleep stops beat/worker (L45) |
| Celery/Redis | RUN | see `CELERY_REDIS_EMAIL_AUDIT.md`; Redis outage -> API 500 (F-M11) |
| Secrets handling | STATIC | no secrets tracked; `render.yaml` uses `sync: false`; `DJANGO_SECRET_KEY` required, no default; build-time key not persisted |
| Dockerfile | STATIC | non-root uid 10001, `collectstatic` at build, healthcheck, gunicorn 3 workers; base Python 3.12 (audit ran 3.11.15, U03); no `.dockerignore`, no hash-pinned requirements (C03); `--forwarded-allow-ips "*"` (L43) |
| docker-compose | STATIC | db/redis healthchecks, one-shot `migrate` service, worker ping healthcheck, beat; local stack runs plain HTTP with SSL redirect disabled by env, as documented. **Not executed (no Docker daemon, U02)** |
| Render blueprint | STATIC | single free web service running web + worker + beat (`render_start.py`), Supabase via session pooler, Brevo SMTP on 2525, `TRUSTED_PROXY_COUNT=1` (hop count on Render UNVERIFIED, L43) |
| Nginx | STATIC | rate limits for login/API, `server_tokens off`, 12 MB body cap (the cap does not exist on Render, L50), no TLS (documented: terminate upstream) |
| CORS | STATIC | allow-list from env, empty by default, credentials off |
| CSRF trusted origins | STATIC | env-driven; verified that cross-site POST without token is rejected |
| CI (`.github/workflows/ci.yml`) | STATIC | ruff, `makemigrations --check`, fresh migrate, `check --deploy`, pytest + coverage, `pip-audit`, gitleaks on a throwaway PostgreSQL; locmem/eager Celery, unpinned actions, no `permissions:` block, no deploy job, no run history available (no remote) (L44) |
| PostgreSQL/Supabase | UNVERIFIED | role split `scripts/harden_db_roles.py` not applied to Supabase per `docs/DEPLOYMENT.md`; admin password described as weak and DB internet-reachable there (F-H02, U01) |
| SMTP / Brevo | UNVERIFIED | no external network (U06) |
| Backups / rollback | STATIC | documented: take a Supabase backup before migrating; rollback of new migrations is additive (reports); not exercised |

## Gate list before a production go-live

1. Fix F-M18 (migrations as a pre-deploy step with a migrator role) and apply the role split; add TRUNCATE triggers; rotate the Supabase admin password; verify with the SQL in `docs/DEPLOYMENT.md` (F-H02).
2. Make Redis failures non-fatal (F-M11); switch 24 h/6 h jobs to crontab (F-M12); do not rely on Render Free for SLA monitoring (L45).
3. Exempt `/health/` from the HTTPS redirect (L42); confirm `TRUSTED_PROXY_COUNT` and restrict `--forwarded-allow-ips` (L43).
4. Add a prod guard for email backend and `SITE_BASE_URL` (L41); add a request-size cap that does not depend on nginx (L50).
5. Build and run the image and the compose stack in CI; add a Redis-backed smoke job; pin actions (L44, U02).
6. Execute the browser matrix on Chrome/Edge/Firefox (U04), load/performance tests (U07), and a real SMTP delivery test (U06).
