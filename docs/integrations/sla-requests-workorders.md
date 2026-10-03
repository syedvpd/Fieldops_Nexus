# Integration contract: M11 SLA & Escalation <-> M05 requests / M06 work orders (+ notifications)

Status: IMPLEMENTED in Phase 6 (OUR IMPLEMENTATION DECISIONS unless marked HPE CONFIRMED; see D-044).

## Ownership
- M11 owns profiles, targets, escalation rules, trackings, events, breaches and acknowledgement.
- M05 / M06 stay the only owners of request / work-order state. M11 never changes them and never copies their state machines: the services of M05 / M06 call small hooks after their own transition.

## Hooks (called inside the authoritative service transaction)
| Caller | Hook | Effect in M11 |
|---|---|---|
| `incidents.services.create_request` | `sla.on_request_created` | starts a tracking from `request.created_at` when an active profile has a target for the severity |
| `incidents.services.update_request` | `sla.on_request_updated` | severity change re-targets a tracking whose targets are still open (due times recomputed from `started_at`, plus paused time) |
| `incidents.services._apply` (every request transition) | `sla.on_request_status_changed` | response met on the first transition out of NEW; resolution met on RESOLVED / CONFIRMED / CLOSED; REJECTED cancels; reopen resumes the resolution timer; pause sync |
| `workorders.services.create_work_order` | `sla.on_work_order_created` | work orders WITHOUT a source request get their own tracking; a work order raised from a request is covered by the request's clock (no second timer) |
| `workorders.services.transition` | `sla.on_work_order_changed` | first assignment = response; COMPLETED / SUPERVISOR_REVIEW / CLOSED = resolution; CANCELLED cancels; reopen; pause sync (also for the request's live work order) |

## Time rules (D-044)
- Timers start at the persisted `created_at`; due times are absolute and stored on the tracking, so editing a profile never rewrites running trackings.
- Response and resolution are separate targets with separate states (PENDING / MET / MET_LATE / BREACHED / NOT_APPLICABLE).
- A timer pauses ONLY while the subject is in a state listed in `SLAProfile.pause_states` (tokens such as `WORK_ORDER:ON_HOLD`); with no list it never pauses. HPE does not define pause states.
- Wall-clock minutes. Business hours / calendars are NOT implemented (HPE silent).
- Every elapsed-time function takes `now` as a parameter; tests pass a controllable clock, production passes `timezone.now()`.

## Idempotency
- `SLABreach` unique per (tracking, target); `SLAEvent` unique per (tracking, dedupe_key); each escalation rule fires once; a monitor run, a Celery retry or a concurrent worker finds existing rows and does nothing (no duplicate breach, event or notification). All work for one tracking happens under its row lock in one transaction.
- `monitor_sla` (Celery beat, every 60 s): one organization at a time inside `tenant_context`, suspended organizations skipped, one transaction per tracking, a failing tracking is logged and does not stop the others, `OperationalError` retried with backoff.

## Notifications
- `EscalationRule` (max 6 per profile): trigger WARNING / BREACH / ESCALATION (after N minutes still unmet), level 1-3, recipients = a role (users holding it at the tracked site, ACTIVE memberships only) and / or the assignee of the live work order. No rule = the breach is recorded but nobody is notified.
- Sent through `notifications.services.notify` (source `sla`), only after the event row was persisted.

## Read side / API
- Site scope: trackings and breaches are restricted to sites where the caller holds `sla.view`. Profiles are organization configuration (`sla.manage`). `sla.process` runs the monitor on demand. `sla.acknowledge` is site-scoped.
- `/api/v1/sla-profiles|sla-trackings|sla-breaches/`, `/api/v1/sla-metrics/` (real aggregates; the data contract M14 will build dashboards on - no dashboard here).
- UI: `/app/sla/trackings|breaches|profiles/`, SLA panel on the request and work-order pages.

## Not implemented
Business-hours calendars, per-customer / contract SLAs (M10), customer-facing SLA views (M13), dashboards (M14), email / SMS channels.
