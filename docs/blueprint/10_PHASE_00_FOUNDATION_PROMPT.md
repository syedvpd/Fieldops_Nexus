# Phase 0 — Foundation & Forensic Audit

READ the entire blueprint package and HPE source.

FIRST STEP IS READ-ONLY. Do not modify code, DB, migrations or Git.

Audit repository, auth, organization/user/role/permission, tenant isolation, audit, Celery/Redis, APIs, UI shell, M01-M15, M05/M06 boundary, tests, DB safety, secrets and Git state.

Report:
- current architecture;
- implemented/missing;
- HPE conflicts;
- blueprint conflicts;
- destructive risks;
- tenant/RBAC risks;
- schema risks;
- dependency gaps;
- recommended sequence.

After Team Lead approval, implement shared foundation:
- Organization/tenant;
- membership;
- User/Role/Permission;
- authentication;
- backend tenant enforcement;
- audit foundation;
- notification foundation;
- common API/error conventions;
- file foundation;
- Redis/Celery;
- CI/test setup.

Never use destructive DB commands.
