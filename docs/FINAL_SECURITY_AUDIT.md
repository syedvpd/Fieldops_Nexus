# Final security audit (2026-10-03)

Method: code review of the new modules against the existing architecture rules, automated negative tests, a two-tenant fuzz, a persona
matrix, browser negative probes (see the browser report) and header inspection. Statuses: PASS / PASS WITH NOTE / OPEN.

| Area | Result | Evidence |
|---|---|---|
| Authentication / sessions / cookies | PASS | unchanged Phase 0 (lockout, HttpOnly, SameSite=Lax, 12 h; prod: secure cookies, SSL redirect, HSTS 1 y via `settings/prod.py`) |
| RBAC (backend) | PASS | every new endpoint is `permission_map` (unmapped = denied) + object/site check; persona matrix `test_persona_matrix_over_the_api`; per-module RBAC tests (M10 26, M12 21, M13 19, M14, M15) |
| Tenant isolation | PASS | `test_every_alpha_object_is_invisible_to_beta_and_vice_versa` (10 API + 9 UI detail routes, lists, scans, audit rows, writes with foreign ids, both directions); generic FK sweep |
| Site scope | PASS | scoped users tested for agreements, labels, dashboards (intersection of scopes), audit viewer + export |
| IDOR / UUID guessing | PASS | foreign or invisible ids answer 404 (not 403) everywhere new; invalid ids 404 |
| QR / barcode tokens | PASS | opaque random (128-bit URL-safe / 60-bit Code 128), no org/asset data, looked up only in the caller's own organizations, authorization after lookup, revoked/unknown/foreign indistinguishable, failures audited with a fingerprint (raw token never stored), `Cache-Control: private, no-store` on label images |
| Client portal | PASS | client-only role, ownership rule, explicit asset grants, client-safe projection (field-set test), privileged APIs 403 (16 URLs), attachment download limited to own uploads, closing stays with staff |
| Dashboards / aggregates | PASS | tenant + intersected site scope; foreign site id 404; no cross-tenant totals (test) |
| Audit integrity | PASS | model/queryset guards, DB row trigger (raw SQL UPDATE/DELETE/mass UPDATE rejected in tests), no write route in UI or API for anyone |
| Exports | PASS | same pipeline as the viewer; `audit.export` separate right; row cap; formula injection neutralised (`'=...`); exports are audited; `nosniff`, no-store |
| File upload / download | PASS | unchanged validated `files` pipeline; client uploads atomic with the request (bad file rolls everything back) |
| CSRF / XSS | PASS | all state changes are POST with CSRF (HTMX sends the header); templates autoescape; `|safe` used only for server-generated SVG (QR/Code 128 from a token / URL) |
| Security headers | PASS WITH NOTE | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`, COOP, HSTS in prod. **No Content-Security-Policy** |
| Secrets | PASS | no secrets committed; QA password is a local test value used only against the local QA database |
| Input validation | PASS | dates, ranges, enums, lengths validated server-side; 400/404/409 envelope |

## Open findings
| ID | Severity | Finding | Recommendation |
|---|---|---|---|
| S-1 | Medium | No Content-Security-Policy header | add a CSP (self + HTMX/Bootstrap from `static/lib`) in a hardening pass; inline `onclick`/`style` attributes need nonces or removal first |
| S-2 | Medium | A table-owner `TRUNCATE` bypasses the audit row trigger | production application role must not hold TRUNCATE; add to the deployment checklist (statement trigger not added because the test harness flushes tables) |
| S-3 | Low | No rate limit on failed label scans | tokens are 60-128 bit and every miss is audited; add a per-user throttle if scan abuse appears |
| S-4 | Low | Each view of the resolve page records a scan event (GET and POST) | acceptable noise; could be de-duplicated per minute |
| S-5 | Low | Dev-only: `DEBUG=True` shows Django's debug 404 | production sets `DEBUG=False` |

No open Critical or High findings.
