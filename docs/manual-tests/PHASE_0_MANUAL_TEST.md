# Phase 0 manual test guide: Foundation

Goal: prove, by hand, that onboarding, login, tenant isolation, roles/permissions, audit and the platform console work.
Time: about 45 minutes. Everything runs locally; nothing touches Supabase/production.

**Test data used below (all fake, change if you like):**

| Who | Email | Name | Password |
|---|---|---|---|
| Super Admin (platform) | `superadmin@fieldops.test` | Platform Admin | you choose, 12+ chars (e.g. `Local-Test-2026-Admin!`) |
| Org A owner | `owner@alpha.test` | Alice Owner | you choose at activation |
| Org A technician | `tech@alpha.test` | Tom Technician | you choose at activation |
| Org B owner | `owner@beta.test` | Bob Owner | you choose at activation |

Organizations: **Alpha Industries** (A) and **Beta Utilities** (B). Passwords must be 12+ characters, not common, not all digits, not similar to the email.

---
## 0. Start the stack
Docker Desktop must be running. In PowerShell:
```powershell
cd C:\Users\HP\Downloads\fieldops-nexus
docker compose -p fieldops up -d --build      # first time ~3 min
docker compose -p fieldops ps                  # db, redis, web, worker, beat, nginx = Up (migrate = Exited 0 is normal)
```
Open **http://localhost:8080/accounts/login/**. You should see a white "Sign in" card on a dark-blue background.
Stop later with `docker compose -p fieldops stop` (data is kept in Docker volumes).

**Pass criteria:** page loads, `http://localhost:8080/health/ready/` shows `{"status": "ok", "checks": {"database": "ok", "cache": "ok"}}`.

## 1. Create the Super Admin (one-time, from the command line)
There is deliberately no public sign-up. **Type the password at the hidden prompt** (do NOT put it in a PowerShell variable or on the command line: Windows PowerShell silently rewrites `$word` inside double quotes and drops `"` characters, so the stored password could differ from what you later type in the browser; this caused confusion during Phase 0 testing, see `docs/INCIDENT_2026-10-03_LOGIN.md`).
```powershell
cd C:\Users\HP\Downloads\fieldops-nexus
docker compose -p fieldops exec web python manage.py create_platform_admin --email superadmin@fieldops.test --full-name "Platform Admin"
```
(no `-T`, so the prompt works.) It asks `Password (input hidden):` then `Password (again):`. Choose 12+ characters, not common, not all digits (example shape only: `Sunrise-Harbor-2026-x`).
Expected: `Platform admin superadmin@fieldops.test created (password length N).` A weak password is refused with reasons. The email already exists? It tells you; to change a password later use `docker compose -p fieldops exec web python manage.py changepassword superadmin@fieldops.test`.

**If sign-in is ever rejected** (wrong password message or lock page), run this before anything else; it types nothing into your shell history and shows which stage fails:
```powershell
docker compose -p fieldops exec web python manage.py diagnose_login --email superadmin@fieldops.test
```
"password matches stored: False" = the stored password is not what you typed (reset it with `changepassword`). "authenticate() result: OK" = the backend accepts it; then the browser is sending different text (autofill / keyboard layout).

## 2. Sign-in tests (Super Admin)
| # | Do | Expect |
|---|---|---|
| 2.1 | Sign in with a wrong password | Red "Invalid email or password." No hint whether the email exists. |
| 2.2 | Sign in with `superadmin@fieldops.test` + your password | Lands on **Organizations** (platform console). Left menu shows only *Platform → Organizations, Platform Audit*. |
| 2.3 | Open http://localhost:8080/app/users/ | Does NOT show any organization's users: you are redirected / denied. A Super Admin has no tenant rights. |
| 2.4 | Top-right name menu → **Sign out** | Back at sign-in. |
| 2.5 | (Lockout) Enter a wrong password **5 times** for the same email, then the right one | The 5th failure and every later attempt (even the right password) show the **"Too many sign-in attempts"** page for 15 minutes. The lock is per **email + your address**: another user (e.g. an organization owner) can still sign in, and the same email from a different device is not locked. Unlock now: `docker compose -p fieldops exec web python manage.py axes_reset` |

## 3. Onboard Organization A (Super Admin → Organization)
1. Sign in as Super Admin → **Organizations → New organization**.
2. Fill: Name `Alpha Industries`, Slug (leave blank), Timezone `Asia/Kolkata`, Country `IN`, Owner full name `Alice Owner`, Owner email `owner@alpha.test` → **Create organization**.
3. Expected: success message "An activation email was sent…". Org detail page shows status **Active**, Owners list shows Alice with status **Invited**.
4. Try creating the same name again → red error "already exists".
5. No email server exists locally, so the email is printed in the worker log. Get the activation link:
```powershell
docker compose -p fieldops logs worker --since 10m | Select-String "activate"
```
Copy the `http://localhost:8080/accounts/activate/.../` link. (Proves Redis + Celery delivered the task. If nothing appears, wait 5 s and retry.)

## 4. Activate and use Organization A as Owner
| # | Do | Expect |
|---|---|---|
| 4.1 | Open the link in a **private/incognito window** (so you stay signed in as Super Admin in the other window) | "Activate your account" page asking for a password. |
| 4.2 | Enter a short password (`abc`) | Error list (too short/common). Nothing activated. |
| 4.3 | Enter a valid password twice | Redirect to sign-in with "Your password is set." |
| 4.4 | Re-open the same activation link | "Link expired or invalid" (links are single-use). |
| 4.5 | Sign in as `owner@alpha.test` | Dashboard titled **Alpha Industries**. Real counts: Active users 1, Pending invitations 0, Roles 11. Sidebar: Overview, Administration (Organization, Users, Roles & Permissions), Compliance (Audit Trail). **No "Platform" section.** |
| 4.6 | Open http://localhost:8080/platform/organizations/ | **403 Access denied**. An Owner is not a Super Admin. |
| 4.7 | Organization → change name/phone/address → Save | "Organization profile saved." Reload: values persist. Enter timezone `Mars/Base` → red "Unknown timezone". |
| 4.8 | Roles & Permissions | 11 roles: *Organization Owner* (Owner badge, "All"), Admin, Operations Manager, Asset Manager, Maintenance Planner, Maintenance Supervisor, Technician, Stores Manager, Service Manager, Client / Requester, Auditor. |
| 4.9 | Open *Organization Owner* | Permission boxes are all ticked and disabled (locked). |
| 4.10 | **New role**: name `Field Lead`, tick `user.view` and `audit.view` → Save | Role appears as **Custom**. Reopen: only those two ticked. Untick one → Save → persists. |
| 4.11 | Create another role named `field lead` | Error "A role with this name already exists." |
| 4.12 | Open *Technician* → untick one permission, Save | Allowed: defaults are editable. |
| 4.13 | Try to delete *Technician* | There is no Delete button for system roles. (Custom role `Field Lead` has **Delete role** → confirm dialog → removed.) |

## 5. Users, invitations and role-based access
1. **Users → Invite user**: Email `tech@alpha.test`, Full name `Tom Technician`, tick role **Technician** → Send invitation.
2. Expected: Tom's page with status **Invited**. Repeat the invite → "already a member".
3. Get the link with the worker-log command from step 3.5, open it in the private window, set a password, sign in as Tom.
4. As **Tom (Technician)** verify:
   - Dashboard works; sidebar has only *Overview → Dashboard* (no Users / Roles / Audit / Organization).
   - Type http://localhost:8080/app/users/ , /app/roles/ , /app/audit/ , /app/organization/ in the address bar → each shows **403 Access denied**. (Hiding the menu is not security; the server refuses.)
   - Bell icon works (empty: "You're all caught up").
   - Name menu → **My profile**: change full name → saved; **Change password** works.
5. Back as **Alice (Owner)**: Users → Tom → set Job title `Field Tech` and change his role to **Auditor / Report Consumer** → Save ("Member updated."). Tom reloads: his sidebar now also shows *Organization, Users, Roles & Permissions, Audit Trail* — all **read-only** (no "Invite user" button, form fields disabled; direct POSTs are refused with 403). Permissions follow the role, instantly.
6. Alice → Tom → **Deactivate** → confirm dialog → status **Suspended**. Tom reloads any page → "no active organization membership". **Reactivate** → he can work again.
7. Alice opens her own user page → there is **no Deactivate button** for herself (the server also refuses: "You cannot change your own access.").
8. Last-Owner rule: on Alice's own page, change her roles to only *Organization Admin* → Save → error "An organization must keep at least one Owner." (An org can never be left without an Owner.) Then set Tom back to **Technician** (needed for step 10.5).

## 6. Tenant isolation: two organizations
1. As Super Admin create **Beta Utilities** with owner `owner@beta.test` / `Bob Owner`; activate Bob like step 4.
2. Sign in as **Bob**. Users page lists only Bob. Roles page shows Beta's own 11 roles. Audit shows only Beta events. Dashboard counts are Beta's.
3. **IDOR test (URL guessing):** sign in as Alice, open Users → click Tom and copy the address (e.g. `/app/users/<uuid>/`). Sign in as Bob and paste that exact URL → **404 Not found** (never Tom's data). Do the same with a Role URL from Alice (`/app/roles/<uuid>/`) → 404.
4. Search box (top bar): as Alice type `bob` → no result (other tenant). Type `tom` → Tom found (Alice can see users). As Tom (no user.view) typing `tom` → no results.
5. A user that belongs to two organizations sees an organization switcher in the top bar; switching changes all data. (Create: invite `owner@alpha.test` as Admin into Beta from Bob's Users page → the existing account is activated at once and a drop-down appears for Alice.) Selecting Beta shows only Beta data; Alice's roles in Beta are only what Bob gave her.

## 7. Super Admin controls
1. Super Admin → Organizations → **Alpha Industries** → **Suspend…** → leave reason empty → Suspend → refused ("A reason is required").
2. Reason `Test suspension` → organization status **Suspended**.
3. Alice reloads → page "Organization suspended". Tom too. Bob (Beta) is unaffected.
4. Super Admin → **Re-activate** → confirm → Alice works again.
5. Platform Audit lists `organization.created`, `organization.suspended`, `organization.activated`, with who did it.

## 8. Audit trail (organization level)
As Alice → **Audit Trail**: expected entries (newest first): `auth.login`, `user.invited`, `membership.roles_changed`, `role.created/updated/deleted`, `user.deactivated/reactivated`, `organization.updated`, etc.
- Filter by Action prefix `user.` → only user events. Filter by date; by actor email.
- **Details** shows Before/After JSON, IP, request id.
- Append-only proof at database level (this must FAIL):
```powershell
docker compose -p fieldops exec db psql -U fieldops -d fieldops -c "UPDATE audit_auditlog SET action='tampered';"
docker compose -p fieldops exec db psql -U fieldops -d fieldops -c "DELETE FROM audit_auditlog;"
```
Expected for both: `ERROR: audit_auditlog is append-only (UPDATE blocked)` / `(DELETE blocked)`.

## 9. Notifications (no feature creates them yet; manual injection to see the UI)
```powershell
docker compose -p fieldops exec -T web python manage.py shell -c "from apps.tenancy.models import Organization; from django.contrib.auth import get_user_model; from apps.notifications.services import notify; o=Organization.objects.get(slug='alpha-industries'); u=get_user_model().objects.get(email='owner@alpha.test'); notify(o,[u],title='Test alert',body='Hello from the shell',level='WARNING',link='/app/users/', email=True)"
```
Alice's bell shows a red **1**. Click the item → it opens Users and the counter drops. The worker log shows the email. Bob does not see it. **Mark all read** works on the Notifications page.

## 10. API and documentation
1. Swagger UI: http://localhost:8080/api/v1/docs/ (all endpoints listed; schema at `/api/v1/schema/`).
2. Get a token (PowerShell):
```powershell
$t = Invoke-RestMethod -Method Post http://localhost:8080/api/v1/auth/token/ -ContentType application/json -Body '{"email":"owner@alpha.test","password":"<Alice password>"}'
$h = @{ Authorization = "Bearer $($t.access)" }
Invoke-RestMethod http://localhost:8080/api/v1/auth/me/ -Headers $h                    # lists her organizations
Invoke-RestMethod http://localhost:8080/api/v1/members/ -Headers $h                     # works (one org => no header needed)
```
3. Cross-tenant header attack (must fail): `Invoke-RestMethod http://localhost:8080/api/v1/members/ -Headers ($h + @{"X-Organization"="beta-utilities"})` → **403 `not_a_member`** (error JSON has `code`, `message`, `details`, `request_id`).
4. No token: `Invoke-RestMethod http://localhost:8080/api/v1/members/` → **401**.
5. With Tom's token (he must be back on the **Technician** role) `GET /api/v1/members/` → **403 permission_denied**; `GET /api/v1/notifications/` → 200.
6. As Super Admin token: `GET /api/v1/platform/organizations/` → list; as Alice → **403**.

## 11. Infrastructure checks
- `docker compose -p fieldops logs worker --tail 20` shows `ready`, the three tasks, `Connected to redis://redis:6379/1`.
- `docker compose -p fieldops logs beat --tail 5` shows `beat: Starting...`.
- `docker compose -p fieldops logs web --tail 5` shows JSON access logs with `request_id`. Every response has an `X-Request-ID` header.
- Automated browser-like smoke test (optional, no credentials needed): `python scripts/smoke_stack.py http://localhost:8080` prints PASS lines (needs any Python 3.11+; standard library only).

## Result sheet
Copy this and mark each: PASS / FAIL (note the step number and what you saw).

| Area | Steps | Result |
|---|---|---|
| Stack up, health | 0 | |
| Super Admin creation, login, lockout | 1, 2 | |
| Org onboarding + activation (Celery/Redis) | 3, 4.1-4.4 | |
| Owner dashboard, profile, roles | 4.5-4.13 | |
| Invite, technician restrictions, deactivate | 5 | |
| Tenant isolation / IDOR / switcher | 6 | |
| Suspend / re-activate | 7 | |
| Audit trail + append-only | 8 | |
| Notifications | 9 | |
| API security | 10 | |
| Infra | 11 | |

When everything passes, tell me "Phase 0 approved" and I will mark it APPROVED in `docs/MODULE_STATUS.md` and start Phase 1.
