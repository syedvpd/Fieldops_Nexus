# Agent Governance & Definition of Done

Before code:
1. Read applicable blueprint/HPE source.
2. Inspect repository.
3. Inspect dependencies/models/migrations/tests.
4. Identify schema impact.
5. Plan.
6. Stop for approval on architecture/high-risk migration changes.

Never:
- DROP DB/schema
- TRUNCATE
- flush/reset/recreate DB
- delete unrelated data
- force push
- rewrite Git history
- bypass tenant/RBAC
- fake APIs
- hardcode metrics
- create dead buttons
- rewrite applied migrations
- commit secrets.

Use isolated test DBs.

Migration rule: module-owned migrations; new migration for new changes; never destructively rewrite applied migrations.

## Definition of Done

Requirement mapped + backend + DB + migration + API + RBAC + tenant isolation + state machine + UI + errors + audit + tests + regression + manual business test + documentation.

## Agent final report

Report:
1. files;
2. migrations;
3. APIs;
4. UI/actions;
5. permissions;
6. tenant evidence;
7. state transitions;
8. tests;
9. integrations;
10. gaps;
11. HPE mapping;
12. manual test;
13. decisions needing human approval.

Never claim complete if a dependency is a stub or integration is pending.
