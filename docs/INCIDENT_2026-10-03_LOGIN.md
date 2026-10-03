# Incident 2026-10-03: Super Admin browser login rejected ("Invalid email or password.")

Status: **fixed and verified**; supersedes the "PASS" given to checks 4, 10 and 11 in `CHECKPOINT_PHASE_0.md` for login behaviour.

## Symptom
`superadmin@fieldops.test` (active, `is_platform_admin=True`, password "valid" from a Django shell) was rejected at http://localhost:8080/accounts/login/ with the generic error. Three browser POSTs (04:45, 04:47, 04:54 UTC) all returned HTTP 200 (form error), none 429/403.

## Login path (traced, not guessed)
`POST /accounts/login/` -> `accounts.views.LoginView` (Django `LoginView`) -> `EmailAuthenticationForm` (field **`username`**, an `EmailField`; `clean_username` lower-cases) -> `AuthenticationForm.clean()` -> `django.contrib.auth.authenticate(request, username=..., password=...)` -> backend 1 `axes.backends.AxesStandaloneBackend` (lockout gate only; returns `None` when allowed, raises `PermissionDenied` when locked) -> backend 2 `ModelBackend` (`User.objects.get_by_natural_key` = `email__iexact`, `check_password`, `is_active`) -> on failure the form raises the single message "Invalid email or password." (`accounts/forms.py` `error_messages`) -> on success `login()` creates the session, `LOGIN_REDIRECT_URL=/app/` -> `ui.views.home` sends a platform admin with no membership to `/platform/organizations/`.
The credential key passed to `authenticate()` is `username` even though `USERNAME_FIELD` is `email`.

## What was proven (evidence)
| # | Finding | Evidence |
|---|---|---|
| F1 | **Axes recorded `username = NULL`**. `AXES_USERNAME_FORM_FIELD` was `"email"`, but Django hands Axes the key `"username"` (signal credentials), so Axes never saw the identity. | `axes_accessattempt` rows had empty username; Axes source `get_client_username` reads `credentials[AXES_USERNAME_FORM_FIELD]` |
| F2 | **Behind Nginx every client had the proxy's IP.** Axes' proxy options need `django-ipware` (not installed), so it fell back to `REMOTE_ADDR` = Nginx container (`172.21.0.7`). | Same rows: `ip_address = 172.21.0.7` |
| F3 | **`AXES_LOCKOUT_PARAMETERS = ["username","ip_address"]` means lock on EITHER**, so (F1+F2) five failures by *anyone* locked *everyone* (HTTP 429), including users with the right password. | Reproduced in the container with Django's test client: 5 failures by a non-existent user -> a valid user with the correct password got 429 |
| F4 | Nginx `login` rate limit (10 req/min) counted page GETs as well as POSTs and answered 503. | probe got `503 Service Temporarily Unavailable` on its 4th attempt |
| F5 | The Phase 0 guide told the tester to set the password with `$env:X = "..."` in **double quotes**. Windows PowerShell 5.1 silently expands `$word` and drops `"` characters, so the stored password can differ from what is later typed in the browser. | Demonstrated: `"Ab$cd-Passw0rd!"` -> length 12 not 15; a value containing `"` reached Python with the quote removed |

## Root cause of the reported rejections
- The three recorded POSTs returned 200, i.e. **not** lockouts (a lockout is 429 / lockout page), so Axes F1-F3 was a real defect but did not itself produce those responses.
- The `superadmin` row is structurally identical to a working account (PBKDF2 hash, active, same flags); a freshly created account with a password supplied through the same command logs in over the same real HTTP path (302 -> `/app/`), proven before any fix.
- Therefore the credentials presented in the browser did not match the stored password. The proven mechanism that makes that happen is **F5** (the guide's PowerShell quoting). It cannot be proven for the exact session because the password is unknown; the new `diagnose_login` command lets the owner of the account settle it in seconds, and the guide now avoids the hazard.
- Independently, **F1-F4 are real security/availability defects** (one bad actor, or one typo-prone user, could lock the whole site) and are fixed.

## Why the Phase 0 tests missed it
1. The Django test client does not enforce CSRF and always uses IP 127.0.0.1 behind no proxy.
2. Tests used the fast MD5 hasher, never PBKDF2.
3. Login was only tested for tenant owners built by fixtures, never for a Super Admin created through the real management command.
4. The lockout test asserted only `status in (403, 429)`; it never checked that *other* users stay unlocked or what Axes stored.
5. The smoke script probed only the *wrong*-password path.
6. No test ran through the proxy configuration.

## Fix
- `config/settings/base.py`: `AXES_USERNAME_FORM_FIELD="username"`, `AXES_LOCKOUT_PARAMETERS=[["username","ip_address"]]` (one combined key), `AXES_USERNAME_CALLABLE` (strip + lower-case so case variants cannot dodge the counter), `AXES_CLIENT_IP_CALLABLE`, `AXES_LOCKOUT_TEMPLATE`, `TRUSTED_PROXY_COUNT`.
- `apps/core/net.py` (new): `client_ip` trusts `X-Forwarded-For` only for the configured number of proxy hops counted from the right (a forged left-most value is ignored; `0` ignores the header); `axes_username`. `audit.services.client_ip` now uses the same function.
- `templates/accounts/locked.html` (new): friendly 429 page.
- `deploy/nginx/default.conf`: rate-limit only POSTs (30/min, burst 10), return 429, `X-Forwarded-For $proxy_add_x_forwarded_for`, comment on trust model. `docker-compose.yml`: `TRUSTED_PROXY_COUNT=1`, `NGINX_PORT` parameter.
- `accounts/management/commands/diagnose_login.py` (new): prompts for the password with hidden input and runs the real `authenticate()` pipeline, printing each stage.
- Not changed (by design): `is_staff`/`is_superuser` stay `False`; Axes stays enabled; CSRF stays enforced; no special-cased users.

## Regression tests (`tests/test_login_integration.py`, 18 tests)
CSRF-enforced browser flow with PBKDF2; Super Admin created via `create_platform_admin` then logged in; session + persistence + redirect to the platform console; wrong password; email case/whitespace; Axes stores the real username and IP; lockout returns 429 even for the correct password; **a bystander on the same IP is not locked**; lock is per username+IP; case variants cannot dodge the counter; proxy IP handling and spoofing; header ignored when no trusted proxy; tenant owner lands in `/app/` and gets 403 on `/platform/*`; platform admin has no tenant access; `diagnose_login` output and no password echo.
**Proof the tests detect the defect:** run against the old Axes settings, 5 of them fail (blank username, proxy IP, cross-user lockout, lockout page, settings contract); with the fix all 18 pass.

## Verification evidence
- Full suite: **128 passed** on PostgreSQL 16; `ruff` clean; `manage.py check` clean; no migration drift.
- Docker: main stack rebuilt (db, redis, migrate, web, worker, beat, nginx); `scripts/smoke_stack.py` passes on it and on a separate QA stack.
- Real browser (Chrome engine in the app pane) against a throwaway QA stack (`fieldops-qa`, port 8081, since torn down), Super Admin whose password contains `$` and `!`:
  1. Sign-in succeeded and landed on **Organizations (Platform console)**; sidebar showed only Platform items.
  2. Navigating to Platform Audit kept the session; opening `/app/users/` redirected back to the platform console (no tenant data).
  3. `auth.login` for the admin appeared in Platform Audit.
  4. Signed out, signed in as a tenant Owner: dashboard of "QA Acceptance Org"; `/platform/organizations/` and `/platform/audit/` -> **Access denied (403)**.
  5. Through Nginx: 5 wrong passwords for the Super Admin -> 5th returned 429; correct password then also 429 (locked); the Owner on the same client address logged in (302). Axes rows showed `username=superadmin@fieldops.test`, `ip=172.22.0.1` (real client) while the Nginx container was `172.22.0.7`.

## Remaining warnings
- The exact rejected session of 2026-10-03 is attributed to credential mismatch by elimination plus the demonstrated PowerShell hazard; it is not provable without the password. Run `diagnose_login` or `changepassword` to settle/fix it.
- A distributed brute-force against one username from many IPs is limited only by password policy and Nginx rate limiting (combined-key lock trades that for no collateral lockouts). Revisit with per-username soft limits before production.
- `TRUSTED_PROXY_COUNT` must match the real proxy chain in each environment (Render adds its own hop).
