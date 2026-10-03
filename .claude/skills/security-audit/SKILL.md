---
name: security-audit
description: Checklist for security review of a module or the final OWASP-oriented pass. Use via a read-only reviewer subagent to keep the main context small.
---
Check: authZ on every view/action; IDOR; CSRF on POSTs; mass assignment (serializers list fields explicitly); injection (ORM only, no raw SQL with user input); XSS (no `|safe`); open redirects; upload validation via `files.services.attach`; secrets (gitleaks, `.env*` ignored); rate limits (login, API); audit for create/update/transition/approval/export/permission; error messages not leaking tenant data; headers (`manage.py check --deploy`); dependency audit (`pip-audit`); Supabase: Django tables must live in a non-exposed schema or have RLS (see docs/DEPLOYMENT.md). Report findings by severity with file:line; do not edit.
