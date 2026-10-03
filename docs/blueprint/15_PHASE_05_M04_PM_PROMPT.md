# Phase 5 — M04 Preventive Maintenance

Implement maintenance plans, time/meter schedules, maintenance windows, reminders, due detection and WO generation.

State:
SCHEDULED -> DUE -> GENERATED -> ASSIGNED -> COMPLETED -> VERIFIED -> NEXT CYCLE

Celery scheduler must avoid duplicate WO generation and handle missed/overdue cycles. Integrate with M06. Test repeated scheduler execution and missed cycles deterministically.
