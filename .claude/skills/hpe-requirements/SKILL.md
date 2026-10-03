---
name: hpe-requirements
description: HPE FieldOps Nexus requirements digest (modules, state machines, entities, API groups, complex rules, Day 30/60/90 gates, acceptance journeys). Load when mapping a requirement or checking acceptance.
---
Read `docs/blueprint/01_HPE_TRACEABILITY.md` (full digest) and `docs/TRACEABILITY.md` (our mapping + gates + journeys).
Rules: HPE explicit text is mandatory; anything else is a FieldOps decision and must be labelled so in `docs/DECISIONS.md`.
Rejection triggers: static/mock pages, fake success, dead buttons, frontend-only auth, committed secrets, unreviewable history, open Critical/High defects, schema without integrity/migrations.
