# Celery / Redis / email audit

**Verdict: Celery/Redis CONDITIONAL.** The scheduled work is real, idempotent and tenant-safe, and it recovers on its own after a broker outage. The weaknesses are availability behaviour when Redis is down (F-M11), restart-sensitive interval schedules (F-M12) and a few delivery details (L39-L41). SMTP delivery through Brevo is UNVERIFIED (no external network).

## 1. What exists

| Task | Schedule | Idempotent | Tenant-safe | Observed |
|---|---|---|---|---|
| `sla.fan_out_sla_monitor` -> `monitor_sla_for_org` | 60 s | yes: unique dedupe keys, tracking row lock, one breach per (tracking,target) | one task per active org inside `tenant_context`; suspended orgs skipped | **RUNTIME**: breach/warning/escalation events and notifications at the configured offsets (INC-000001: response breach 10:51:25 for a 10:50:56 due; 50 % warning 10:52:25; resolution breach 10:53:25; escalation level 2 at 10:54:25, +1 min rule); detection lag <= one beat tick |
| `maintenance.fan_out_maintenance` -> `generate_due_maintenance_for_org` | 15 min | yes: `UNIQUE(schedule,sequence)`, `UNIQUE(source_id)` for PM, schedule row lock | per org | **RUNTIME**: a DAILY schedule starting today produced WO-000025 (trigger=scheduler) at the next tick; two extra runs created no second cycle |
| `contracts.fan_out_renewal_alerts` -> `send_renewal_alerts_for_org` | 6 h | yes (`renewal_alerted_at` under lock) but see F-M13 | per org | **RUNTIME**: triggered through the worker: warranty WAR expiring in 20 days notified Service Manager, Owner and Asset Manager; `renewal_alerted_at` stamped; second run silent |
| `dashboards.fan_out_report_snapshots` -> `snapshot_organization` | 24 h | yes (unique org/kind/day) | per org (owner membership) | static + test suite (not waited for) |
| `core.clear_expired_sessions` | 24 h | yes | global | static |
| `notifications.send_notification_email` | on commit | no: a retry re-sends to all recipients (L39) | reads by id, then tenant context | **RUNTIME**: SLA breach/escalation emails produced for the configured roles |
| `accounts.send_invitation_email` | on commit | mostly | identity | **RUNTIME**: invitation emails rendered with the activation link (console backend) |

Settings: `acks_late=True`, no result backend, retries only on `OperationalError`/`OSError`, broker connection retry on startup, 10-minute time limit (not enforced by the `solo` pool used on Render, L40). The legacy per-org-less tasks (`monitor_sla`, `generate_due_maintenance`, ...) are not scheduled.

## 2. Failure experiments (real processes)

| Experiment | Result |
|---|---|
| **Worker stopped**, invite a user | API 201; task waits in Redis (queue length 1); starting the worker delivered the invitation email: **no loss**. Beat keeps enqueuing 60 s SLA ticks without `expires` (they pile up, harmlessly idempotent) |
| **Redis stopped** (hard `shutdown nosave`) | `/health/ready/` 503 `{"cache":"error"}` (correct); `/health/live/` 200; HTML pages keep working (sessions in DB); **every `/api/v1/*` request -> 500** (DRF throttle uses the cache); **QR scan -> 500** (failed-scan counter in cache); HTML invite -> user row committed, request errors, **email never queued**; worker logged 9 connection errors |
| **Redis restored** | API and readiness recovered with no app restart; worker and beat reconnected and resumed the 60 s/15 min jobs by themselves; queued state is lost with `nosave` (expected) |
| Duplicate execution | extra `fan_out_maintenance` runs: no duplicates; the SLA monitor is protected by dedupe keys; renewal alert by the stamp |
| Task failure | `run_for_organization` records `last_error` and continues with other schedules (static); there is no notification after repeated failures (L11) |

## 3. Email

- Backends: console in dev; SMTP (`smtp-relay.brevo.com:2525`, TLS) configured in `render.yaml`; credentials are `sync: false`. `prod.py` has no guard against the console backend or a localhost `SITE_BASE_URL` (L41): an unset `SITE_BASE_URL` silently yields `localhost` activation links.
- Content: invitation (activation link valid 3 days), SLA warning/breach/escalation, renewal alerts, in-app bell notifications. Notification email retry can duplicate sends (L39) and nothing records delivery status.
- UNVERIFIED: actual SMTP delivery, SPF/DKIM, bounce handling (U06).

## 4. Production implications

1. A Redis blip must not equal a REST outage: make the throttle and scan limiter fail-open and queue publishing non-fatal after commit (F-M11).
2. Move the 24 h / 6 h jobs to `crontab` entries (F-M12): on Render restarts reset interval timers and the Free instance sleeps (keepalive via GitHub cron is best-effort, L45).
3. Render runs web + worker + beat in one 512 MB container with `--pool=solo`: a hung SMTP/DB call blocks every task (L40); two overlapping instances during a deploy would run two beats (harmless only because every job is idempotent).
4. Tests run with locmem cache and eager Celery (`config/settings/test.py`), so none of the above is covered by the suite or CI (L44).
5. Monitoring/alerting for failed schedules does not exist (L11).

## 5. Findings

F-M11, F-M12, F-M13, L11, L39, L40, L41, L44, L45; UNVERIFIED M11-005 (breach recorded but email lost if the broker is down at commit), U06.
