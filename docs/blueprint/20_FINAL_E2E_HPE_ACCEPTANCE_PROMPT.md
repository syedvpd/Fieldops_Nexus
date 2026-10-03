# Final HPE Acceptance Audit

Do not assume completion. Read the blueprint, HPE source, repo, tests, migrations and deployment configuration.

Verify:
1. Site + asset hierarchy + history.
2. PM -> scheduler -> WO without duplicates.
3. Technician -> checklist -> parts -> labor -> completion.
4. High-priority request -> SLA response/resolution -> escalation.
5. Inventory issue/return -> movement -> WO linkage.
6. QR -> asset -> service event.
7. Client request -> technician completion -> confirmation -> audit/dashboard.

Also verify tenant isolation, RBAC, IDOR, all state machines, fresh migrations, transaction safety, Celery, notifications, API docs, UI actions, no fake functionality, audit, uploads, security, pagination, query/N+1, CI/CD, Docker/deployment and documentation.

Produce a requirement traceability matrix with PASS/PARTIAL/FAIL, exact evidence and defects. Do not claim UAT-ready with Critical/High defects.
