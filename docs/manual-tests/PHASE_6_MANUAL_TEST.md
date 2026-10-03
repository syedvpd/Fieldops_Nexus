# Phase 6 manual test: M11 SLA & Escalation

Use a local QA database (never Supabase). Test users are created by your seed script; use roles: service manager (`sla.*`), operations manager (`sla.view` + `sla.acknowledge`), technician (no SLA access), and a second organization's service manager.

## 1. Configure (service manager)
1. Open `/app/sla/profiles/` -> New profile: name `Incident SLA`, applies to Service requests, pause states: tick `Work Order - On Hold`. Create.
2. On the profile page add target HIGH: respond 2 min, resolve 6 min, warn at 80. Expected: row appears; saving HIGH again replaces it.
3. Add rules: Response/Warning -> role Operations Manager; Response/Breach -> Operations Manager; Resolution/Escalation after 2 min -> Service Manager (level 2).
4. Negative: target with resolve < respond -> error message, nothing saved. A second active profile for the same scope -> conflict message. 7th rule -> refused.

## 2. Journey (T0..T4)
1. T0: as a technician report an incident with severity HIGH. Open it as operations manager: the SLA panel shows Response/Resolution pending with due times 2 and 6 minutes after creation.
2. T1 (about 1.6 min): click `Run check now` on `/app/sla/trackings/` (service manager). Expected: 1 warning; operations manager has a WARNING notification.
3. T2 (after 2 min): Run check now -> response breach row on `/app/sla/breaches/` (status Open), CRITICAL notification for the operations manager.
4. Triage the request as operations manager: response shows `Met late`, the response breach closes.
5. T3 (after 6 min): Run check now -> resolution breach.
6. T4 (after 8 min): Run check now -> escalation level 2, notification for the service manager.
7. Run check now repeatedly: counters stay 0, no duplicate rows or notifications.
8. Acknowledge the open breach as operations manager (button on the breaches page): status Acknowledged. A supervisor / planner has no button; posting directly returns 403.

## 3. Pause
Create a work-order profile with pause `Work Order - On Hold` and a target; create a work order without a request, assign it (response met), put it on hold: tracking shows Paused; resume: due time moved by the paused duration.

## 4. Negative / security
- Technician opens `/app/sla/trackings/` -> 403. Operations manager opens `/app/sla/profiles/` -> 403.
- Other organization's tracking / profile URLs (copy an id) -> 404. Scoped-site user sees only their site's trackings.
- API: `GET /api/v1/sla-metrics/` returns the same counts as the pages.

## 5. Database checks (psql on the QA database)
- `select count(*) from sla_slabreach group by tracking_id, target_kind having count(*) > 1;` -> 0 rows.
- `select dedupe_key, count(*) from sla_slaevent where dedupe_key <> '' group by tracking_id, dedupe_key having count(*) > 1;` -> 0 rows.
- No tracking without exactly one of request / work order; no breach whose organization differs from its tracking's.

## Result sheet
| Step | Expected | Actual | Pass |
|---|---|---|---|
| 1-4 | configuration + validation | | |
| 2.1-2.8 | journey | | |
| 3 | pause / resume | | |
| 4 | negatives | | |
| 5 | database | | |
