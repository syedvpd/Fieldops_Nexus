# FieldOps Nexus: browser acceptance results (INTERIM #3, 2026-10-04)

## Addendum (after server restart + `collectstatic`)
| Area | Result | Evidence |
|---|---|---|
| M12 Scan page (manual code entry; camera unavailable in pane) | PASS | page renders after collectstatic (defect 1 resolved) |
| M12 unknown label | PASS | generic "Label not recognised", no tenant leak |
| M12 failed-scan throttle | PASS | after 15 failures: "Too many failed scans. Wait a few minutes before trying again." |
| M12 valid scan / scan -> service request / revoked label | NOT MANUALLY VERIFIABLE (token only inside the QR image; no camera) | |
| Cross-tenant Alpha -> Beta (site view + edit URLs) | PASS | "Not found" (Beta only had a site; created via UI) |
| M15 audit export (CSV) | PASS | `audit.exported` entry under Exports (file download itself not viewable in pane) |
| M15 per-WO evidence package | PASS (download only) | `audit.evidence_exported`; ZIP / checksum manifest contents NOT verified in pane |
| Role: Auditor (reader) | PASS | write pages (new asset, new incident, invite user, receive stock) = Access denied; audit + WO readable |
| Role: Planner | PASS | users, stock receive, audit denied; WO viewable; no Close action in Supervisor Review |
| Role: Technician | PASS | users, new WO, SLA profiles, stock receive denied |
| M02 meters | PASS | meter added, reading 500 h recorded, lower reading rejected ("lower than the previous reading 500.000 h") |
| M03 hierarchy | PASS (UI level) | ENG-001 attached to GEN-001 as Assembly; repeat attach refused (single parent); ancestor not offered as child (cycle prevented) |
| M02 documents upload/removal | NOT TESTED | needs native file picker |
| Responsive 1920/1366/1024/390 | PASS (overflow) | scrollWidth == viewport on dashboard, WO list/detail, assets, stock, audit; visual/keyboard review not done |
| Client portal (M13) | NOT TESTABLE | no Client account (activation needs email/Celery) |

## Indicative verdict (not final)
RELEASE CONDITIONALLY ACCEPTED: the mandatory core workflow and all five HPE state machines pass with browser evidence, tenant isolation and RBAC boundaries held,
no Critical/High defect found. Not ACCEPTED because HPE Day-90 journeys 6 (QR scan to service event) and 7 (client portal) could not be exercised in this
environment, and Journey 4 escalation notification delivery was not verified. This is browser evidence only; it does not by itself prove M01-M15 complete
(full regression and the findings #1-#18 reconciliation are separate gates).

# (earlier interim content follows)

Status: **IN PROGRESS. Not a completion claim.** M01-M15 completeness still requires the full regression and the
gap-by-gap reconciliation against audit findings #1-#18 (not done here).

## Environment
- Base URL `http://localhost:8000` (`runserver --noreload`, `config.settings.prod` via `.claude/run_prod.ps1`), Claude desktop built-in browser pane.
- Database: Supabase project `fieldops-nexus-prod-sg`, schema `fieldops` (designated QA dataset; orgs "Alpha Industries" and "Beta Utilities").
  Migrations `assets.0002`, `contracts.0002`, `sla.0002` were applied by the user before the run (before that `/app/assets/` returned 500: QA drift, not a code defect).
- Celery worker/beat NOT running; SMTP not configured. Redis `localhost:6390`. SLA and PM were driven through the UI buttons ("Run check now", "Generate now").
- Accounts used: owner@alpha.test, tech@alpha.test, owner@beta.test. Passwords are never recorded.
- QA rows created by this run (Alpha): GEN-001, PMP-001 (retired), DSP-001 (disposed); INC-000001..3; WO-000001..3; checklist "Generator preventive service";
  warehouse BLR-STORE, part BRG-6205 (+10 stock); PM plan + weekly schedule; SLA profile "Standard incident SLA"; provider + AMC-GEN-2026; pending invitation supervisor@alpha.test.

## Mandatory state machines (HPE 8.1)
| Machine | Result | Evidence |
|---|---|---|
| Service Request NEW > TRIAGED > APPROVED > WO CREATED > IN SERVICE > RESOLVED > CONFIRMED > CLOSED | PASS | INC-000001 end to end; list shows Closed. Repeat triage rejected by backend. |
| Service Request REJECTED branch | PASS | INC-000002: reason required (browser + backend), ends Rejected, no further actions |
| Work Order DRAFT > PLANNED > ASSIGNED > DISPATCHED > IN PROGRESS > ON HOLD > IN PROGRESS > COMPLETED > SUPERVISOR REVIEW > CLOSED | PASS | WO-000001, WO-000003; closed WO read-only |
| WO rework (Supervisor Review > In Progress) | PASS | WO-000003 returned for rework with reason |
| WO closure gates | PASS | corrective needs evidence; closure needs labor ("No labor / time has been recorded"); required checklist blocks completion |
| Preventive Maintenance SCHEDULED > DUE > GENERATED > (WO) COMPLETED > VERIFIED > NEXT CYCLE | PASS | plan GEN-001 weekly: Due -> WO-000003 generated (cycle 0, Generated) -> Closed -> PM state Verified, next due 11 Oct Scheduled |
| PM duplicate prevention | PASS | second "Generate now": "The previous cycle's work order is still open" |
| Part Request REQUESTED > RESERVED > ISSUED > CONSUMED/RETURNED > RECONCILED | PASS | WO-000002 BRG-6205: req 3, reserve 3 (on hand 10), issue 3 (7), consume 2, return 1 (8), reconcile. Issue 99 refused. Ledger 10-3+1=8 |
| Asset ACTIVE > UNDER MAINTENANCE > OUT OF SERVICE > ACTIVE | PASS | PMP-001 |
| Asset OUT OF SERVICE > RETIRED / DISPOSED | PASS | PMP-001 Retired; DSP-001 Disposed; both read-only |
| Asset coupling (WO start/close drives status + history) | PASS | GEN-001 history |

## Other results
| Area | Result | Notes |
|---|---|---|
| Foundation (Alpha owner: login, org, nav, users, roles, sites) | PASS | |
| Platform Super Admin login | NOT TESTABLE | no credential available (hidden-password command) |
| Supervisor / Stores / Client / Service Mgr accounts | NOT TESTABLE, QA ACCOUNT PROVISIONING BLOCKER | invite created; activation email needs Celery worker |
| CORE workflow steps 1-20 | PASS (checklist/inventory done separately on WO-000002/3) | steps 16-17 done as org owner |
| Evidence upload | PASS | `.md` rejected by allow-list; PDF accepted; native picker done by user |
| M08 checklist | PASS | blank completion refused (backend); exception requires finding; finding recorded; completion with finding; version frozen on activate |
| M07 technician screen | PASS | assigned-only list, Site & route card, hold/resume, notes, time |
| M11 SLA | PASS (pause not tested) | High target 1/2 min, SLA attached to INC-000003; Run check now -> 1 warning, 1 breach; Response Breached; breach acknowledged |
| M10 contract | PASS | AMC-GEN-2026 created, SLA profile linked; asset shows "Coverage now: AMC..." |
| M10 -> M11 effect on SLA resolution | PARTIAL | linked profile equals org-wide profile in this data, so effect not distinguishable |
| M12 QR | PARTIAL | QR label page and panel render, SVG/PNG links work; valid scan NOT MANUALLY VERIFIABLE (no camera, token only in image); Scan page returns 500 (see defects) |
| Cross-tenant Beta -> Alpha | PASS | 6 Alpha URLs (WO, asset, incident, site, evidence ZIP, user) all "Not found" |
| Cross-tenant Alpha -> Beta | NOT TESTED | |
| Responsive 390x844 | PARTIAL | no horizontal overflow on dashboard, sites, assets list/detail, incidents, work orders, stock, dashboards, audit (scrollWidth == viewport); other widths and screenshots not done |
| Client portal, role matrix beyond owner/tech, meters/documents/hierarchy UI, M14 drilldown, exports | NOT TESTED | |

## Defects / observations
1. **Environment (blocks M12 scan UI):** `/app/identification/scan/` -> 500 `Missing staticfiles manifest entry for 'js/qr_scan.js'`; `collectstatic` not re-run after the new JS (deploy step; `staticfiles/` is git-ignored).
2. Cosmetic: invalid-transition message shows raw text ("service_request: action 'triage' is not allowed from state 'TRIAGED'").
3. Cosmetic: asset history label "Undermaintenance".
4. Cosmetic: Work order Labor & material tab says stock movements "arrive with the inventory module" (stale; M09 exists).
5. Minor: retired asset PMP-001 is still offered in the AMC "Covered assets" list.
6. UX: Asset "Labels" tab and some HTMX panels take several seconds to appear over the remote DB ("Loading labels...").
7. Tooling: built-in pane cannot drive native file pickers; element-ref clicks below the fold unreliable (coordinates worked).
8. Open risk: WO-000002 left in Supervisor Review (needs labor) and INC-000003 left New; both are QA data.

## Remaining
Restart the QA server (power cycle); run `collectstatic`; start Celery worker/beat; then: QR scan page, invalid scan/throttle, Alpha -> Beta isolation,
role matrix (planner, reader), client portal (needs provisioned Client), asset meters/documents/hierarchy UI, M14 drill-down, M15 export + evidence ZIP, remaining viewports.
