# M01: Site & Location (plus company, users and access: the foundation)

**What it answers:** Where does the company operate, and who may see which site?
**Why it matters:** every asset, work order, stock item and report belongs to a site. Site-scoped roles (a user limited to some sites) are what keep data private inside a company.

## 1. Accounts you need
| Step | Account |
|---|---|
| Create the company + first owner | Platform Super Admin (see `00_START_HERE.md`, "Super admin") |
| Everything else in this guide | Company Owner: `owner@alpha.test` (password in `.env.qa-users`) |

## 2. Create a company and invite its owner (Super Admin)
| # | Do | Expect |
|---|---|---|
| 2.1 | Sign in as Super Admin → **Platform → Organizations → New organization** | Form opens |
| 2.2 | Name `Gamma Works`, slug `gamma-works`, Owner name `Gina Owner`, Owner email (a real inbox you control), Time zone `Asia/Kolkata`, Country `IN` → Save | Company listed as **Active**; owner shows **Invited** |
| 2.3 | Open the owner's email → click the activation link → choose a password (rules: length, not common) | Owner lands in the company dashboard. The link works **once**; reusing it shows an error |
| 2.4 | Super Admin list now shows owner **Active** | |
| 2.5 | Negative: Super Admin → Suspend company; owner tries to sign in | Blocked. Activate again → works |

## 3. Invite users and assign roles (Owner)
| # | Do | Expect |
|---|---|---|
| 3.1 | Sign in as `owner@alpha.test` → **Administration → Users → Invite user** | Form |
| 3.2 | Email `new.tech@alpha.test`, Full name `New Tech`, tick role **Technician** → Invite | "Invitation sent"; user listed as **Invited**. (Email goes out through Brevo; for `.test` addresses nothing arrives: use a real address to test the link.) |
| 3.3 | Same form, role **Asset Manager**, and under *Limit to sites* tick only **BLR-OPS** | User detail shows the role with the site |
| 3.4 | **Users → open a user → Roles** change roles; deactivate a user | Deactivated user is blocked at sign-in; reactivate restores |
| 3.5 | Negative: owner tries to deactivate themselves | Refused |
| 3.6 | **Roles & Permissions** | 11 built-in roles listed (Owner, Admin, Operations Manager, Asset Manager, Planner, Supervisor, Technician, Stores Manager, Service Manager, Client/Requester, Auditor). Open one to see its permission list |

## 4. Sites (M01 proper)
| # | Do | Expect |
|---|---|---|
| 4.1 | **Assets & Locations → Sites & Locations → New site**: Code `PUNE-1`, Name `Pune Plant`, City `Pune`, Country `IN`, Time zone `Asia/Kolkata`, Address → **Create site** | "Site PUNE-1 created"; code shown in capitals, status Active |
| 4.2 | Create the same code again | Red "A site with this code already exists" |
| 4.3 | Time zone `Mars/Base` | Red "Unknown timezone" |
| 4.4 | Site page → **Locations** tab → **Add location**: Name `Block A`, Type *Building*, parent *(top level)* | Row appears |
| 4.5 | **Add child** on Block A: `Ground floor` (Zone / area); then child of that: `Generator hall` (Service area) | Tree indented 3 levels |
| 4.6 | Try a *Building* under Block A | Red "A building must be a top-level location" |
| 4.7 | Edit Block A, set its parent to its own descendant | Not offered (no loops) |
| 4.8 | **Calendars** tab → **New calendar**: `Day shift`, Mon-Sat, 08:00-18:00, *Default* → add holiday `2026-12-25` Christmas; add same date again | First ok; second refused "already has a holiday" |
| 4.9 | **Contacts** tab → add `Site Manager` (level blank) and `Regional Head` (escalation level 2) | Levels listed in order; reusing level 1 refused |
| 4.10 | Create a second site `PUNE-2` | Both in the list with counts of locations and active assets |

## 5. Site-scoped access (the key security test)
| # | Do | Expect |
|---|---|---|
| 5.1 | As owner invite `sam.scoped@alpha.test` with role Asset Manager limited to **PUNE-1** only, activate via the email link | |
| 5.2 | Sign in as that user | Sites and Assets lists show **only PUNE-1** |
| 5.3 | Paste a PUNE-2 site or asset address | **Not found** (same as a record that does not exist) |
| 5.4 | Try `/app/sites/new/` or `/app/users/` | **Access denied (403)** |
| 5.5 | Owner changes the user's scope to PUNE-2 | After refresh the user sees only PUNE-2; Audit Trail shows `membership.roles_changed` |

## 6. Company isolation
Sign in as `owner@beta.test`: Beta sees only Beta's sites. An Alpha site address pasted into Beta's session → **Not found**.

## Connected modules
M02/M03 assets sit at a site/location · M04 schedules use the site calendar and time zone · M06/M09 are scoped by site · M11 uses site-level SLA profiles · M14 filters by site · M15 audits every user/site change.

## Pass when
A company and owner can be created and activated, users can be invited with roles and site limits, the site → location tree and calendar/contact rules hold, and a site-limited user cannot see or open any other site's data.
