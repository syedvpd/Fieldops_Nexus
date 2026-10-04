# M11: SLA & Escalation

**What it answers:** How fast must we respond and resolve, and who is told when we are late?
**Accounts:** `owner@alpha.test` / `service@alpha.test` configure; `ops@alpha.test` sees tracking and breaches.

## How it works in one paragraph
An **SLA profile** has targets per priority (respond within X min, resolve within Y min, warn at Z %). When an incident is reported, a clock starts. A background job (Celery Beat, **every 60 seconds**) checks every clock: at the warning % it sends a **warning**, at the deadline it records a **breach**, and later it can **escalate** to a higher role. Warnings are in-app; **breaches and escalations are in-app AND emailed**. Clocks are 24/7 elapsed minutes.

## Screens (Service levels menu)
**SLA tracking** (every running/finished clock) · **SLA breaches** (with **Acknowledge**) · **SLA profiles** (targets + escalation rules).

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | **SLA profiles → New profile**: name `Standard incident SLA`, applies to *Service requests / incidents*, scope Organization | Listed, Active |
| 2 | Open it → **Targets**: Priority *High*, Respond `30`, Resolve `120`, Warn at `80` → **Save target** | Row shown. (Use 1 and 2 minutes to see a breach quickly during a demo) |
| 3 | **Escalation rules**: Target *Response*, Trigger *Target breached*, Notify role *Operations Manager* → **Add rule**; add *Warning threshold reached*; add *Still unmet after the breach* (after 60 min, level 2, role Service Manager) | Rules listed with who is notified |
| 4 | Report a **High** incident (W1) | Its **SLA** tab: Response/Resolution "Pending, due HH:MM" |
| 5 | Wait past the warning point | Notification (bell) "SLA warning" to the rule's role |
| 6 | Wait past the deadline (≤ 1 min after) | SLA breaches list shows an **Open** breach; bell shows "SLA breached"; an **email** is sent to the notified users |
| 7 | **Acknowledge** the breach | Status Acknowledged, user/time recorded |
| 8 | Respond/triage late | Response state "Met late"; breach closes |
| 9 | Run twice / retry | No duplicate breach or email (idempotent) |

## Negative
Stores/Supervisor cannot open **SLA profiles** (403); the profile pages need `sla.manage`; Beta cannot see Alpha clocks.

## Connected modules
M05/M06 (clock starts/stops with them) · M10 (coverage SLA) · M01 (site profiles override organization profiles) · Notifications + Brevo email · M14 SLA breach KPI · M15 audit.

## Pass when
A real breach is detected by the scheduler without anyone clicking, the right people are notified (in-app + email), and re-runs never duplicate.
