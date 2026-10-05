# UI/UX reference map (reference screen -> FieldOps screen)

Reference: `docs/ui ux refernce/fieldopus-nexus-frontend-uiux-main/fieldopus-nexus-frontend-ui-main/` (Figma Make export: React 19 + Tailwind 4, hard-coded demo data, no API client, no auth/RBAC; `docs/inventory-backend-contracts.md` there confirms its data is "presentation constants").
Status of this document: PLAN. Nothing below is implemented yet. Level in the source-of-truth order (D-032): the reference is **below level 5**. It informs look and layout only; HPE PRD, module docs, RBAC, tenant isolation and state machines always win.

## Method (applied to every screen)
reference screen -> existing FieldOps screen -> existing template -> reference component -> WHAT CHANGES -> WHAT MUST NOT CHANGE -> backend gap? -> HPE required? -> IMPLEMENT / ADAPT / DEFER

## Global rules
- **Stack stays Django templates + Bootstrap 5 + HTMX.** Tailwind/React are NOT adopted (OUR IMPLEMENTATION DECISION). We port the visual language, not the code.
- **Never ported:** demo numbers, fake KPIs, client-side-only workflows, demo auth (`demoAuth.ts`, localStorage session), role switcher, any button without a real endpoint. A reference element with no backend becomes DEFER, not a stub.
- **Must not change anywhere:** URL names, view/permission mixins, `required_permission`, tenant scoping, site scope, state-machine transitions, audit calls, form field names/ids used by tests (`#site-table`, `#export-sites`, `data-kpi`, `data-drill`, ...), HTMX endpoints, CSRF.
- Reference token set to map into `src/static/css/app.css` `:root` (replace values, keep `--fx-*` names so templates are untouched): navy `#0B1F3A / #102A43 / #071426`, gold accent `#C9A227`, surface `#F8FAFC`, border `#E2E8F0`, text `#172033 / #64748B`, Inter. Semantic success/warning/danger/info `#10B981 / #F59E0B / #EF4444 / #3B82F6`. Current: nav `#14202e`, accent blue `#0b6bcb`. Contrast of gold on white must be checked (a gold text on white fails AA; use gold only for accents/active borders, navy for text).

## Shared components (do these first; every screen reuses them)
| Reference component | FieldOps equivalent (exists) | Change | Must not change | Decision |
|---|---|---|---|---|
| `Sidebar.tsx` (grouped, collapsible, role nav) | `shell.html` + `fx-sidebar`, nav from each app's `navigation.py` | Navy theme, gold active marker, section icons, optional collapse-to-icons | Nav still data-driven from `navigation.py` and permission-filtered; no hard-coded role menus | ADAPT |
| `Header.tsx` (breadcrumbs, search, bell, org, user) | `fx-topbar` in `shell.html`; `components/_page_header.html` has `crumbs` | Breadcrumb in topbar via existing `crumbs`; restyle | HTMX search/bell endpoints, org switch POST | ADAPT |
| `PageHeader.tsx` (title, subtitle, actions, tabs) | `components/_page_header.html`, `.fx-tabs` | Title/tab styling (gold underline) | Tabs stay real links, not JS state | ADAPT |
| `KpiCard.tsx` | `dashboards/_kpi.html` | Icon chip, tone (accent/alert), trend line | `n/a` for missing data, drill links, `data-kpi`; no invented trend values (trend only if M14 `metrics.py` supplies it) | ADAPT |
| `StatusBadge.tsx` | `{% status_badge %}` + `.fx-badge-*` | Dot + colour per status family | Status keys come from our state machines (reference keys like `dispatched`, `triaged` are NOT assumed to exist); unknown -> neutral | ADAPT |
| `DataTable.tsx` (skeleton, empty, pager) | `.fx-table`, `_empty_state.html`, `_pagination.html` | Header/row styling, sticky head, empty-state art | Server-side sort/filter/pagination; no client paging of fake arrays | ADAPT |
| `FilterBar.tsx` | per-list GET forms | Unified bar markup/partial | GET params and names (tests, CSV export reuse the query) | ADAPT |
| Toasts/notify in `SuperAdminDashboard` | Django messages `_messages.html` | Toast styling only | Messages only after a real persisted action | ADAPT |

## Screen matrix
Legend for backend: OK = model/service/API exist (all M01-M15 apps exist per MODULE_STATUS); GAP = data or action missing. HPE column: confirm against the PRD digest (`hpe-requirements` skill) before building; "module" = covered by an M-module, "n/a" = marketing/extra.

| # | Reference page | Existing FieldOps screen / template | Reference component(s) | What changes | Must not change | Backend gap? | HPE required? | Decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `LoginPage` | `accounts/login.html` | split brand panel, form card | Brand panel, spacing, show/hide password | Axes lockout, error messages, no demo-credential hints, no role picker | None | module (auth) | ADAPT |
| 2 | `LandingPage`, `MarketingPages` | `public.html` | hero, feature sections | Nothing now | - | Marketing site is not an ERP requirement | n/a | DEFER |
| 3 | `ClientRegistrationPage` | `portal/new.html`, `portal/accounts.html` | stepper/sections | Section layout only | Registration is admin-enabled (M13 `enable`), NOT self-signup; no account creation from the public page | Self-registration would be a new flow | M13 says accounts are enabled by staff (verify) | DEFER self-signup; ADAPT layout |
| 4 | `DashboardPage` (Operations) | `dashboards/operations.html` | KpiCard grid, charts | Card/chart styling, layout order | KPI values only from `dashboards/metrics.py`; drill links | None for KPIs the reference shows if in `KPI_DEFINITIONS`; extra reference KPIs = GAP | M14 | ADAPT |
| 5 | `AssetManagerDashboard`, `MaintenancePlannerDashboard` | `dashboards/assets.html`, `maintenance.html` | health bars, sections | Visuals | Same as #4 | Reference widgets without a metric -> DEFER | M14 | ADAPT |
| 6 | `SuperAdminDashboard` (org, RBAC, health) | `platform_admin/*`, `rbac/*`, `tenancy/*` | sidebar sub-app, tables | Visual only | Platform admin never implied by org owner; real RBAC views | "System health" tiles = GAP (needs real health source) | Platform admin is OUR design | ADAPT visuals; DEFER health tiles |
| 7 | `SiteLocationMaster` (2011 lines) | `sites/home.html`, `list.html`, `detail.html` (**uncommitted work in progress**) | tree + master/detail | Layout | Zone tree selectors, calendars, contacts, lifecycle | Check after M01 WIP lands | M01 | ADAPT, **after M01 WIP is committed** (avoid colliding with it) |
| 8 | `AssetsPage`, `AssetDetailPage` | `assets/list.html`, `detail.html`, `form.html` | FilterBar, DataTable, tabs | Styling, detail header card, tab bar | Documents/meters/status transitions, QR panel (`identification/_panel`), M10 panel | None | M02 | ADAPT |
| 9 | Asset hierarchy (`OtherPages`) | `assets/_tree*.html` | tree | Node styling | Re-parent/cycle rules (M03) | None | M03 | ADAPT |
| 10 | `ServiceRequestsPage`, incidents | `incidents/list.html`, `detail.html` | table, status badges | Styling | M05 workflow bar, downtime, history | Reference "incident vs request" split: confirm vs M05 model before copying | M05 | ADAPT |
| 11 | `WorkOrdersPage`, `WorkOrderDetailPage` | `workorders/list.html`, `detail.html`, `components/_workflow_bar.html` | stepper, tabs, cost cards | Stepper look, tabs, side panels | `closure_blockers`, labor/material/evidence services, M06 states (not reference states) | None | M06 | ADAPT |
| 12 | `DispatchPage` | no dedicated board (assignment lives on WO detail / reassign) | board columns | A board needs real assignment data | Assignment must go through M06 `reassign`/transition services | **GAP**: no dispatch board view/selector | M06 assignment is HPE; a board view is not confirmed | DEFER (needs Team Lead call: CLARIFICATION REQUIRED) |
| 13 | `TechnicianPage` | `workspace/jobs.html`, `job.html`, `inspection.html` | mobile cards | Mobile-first card styling | M07 delegates to M06/M08, offline not claimed | None | M07 | ADAPT |
| 14 | `MaintenancePage` | `maintenance/plans.html`, `due.html`, `schedule_detail.html`, `history.html` | KPI + tabs | Styling; PM calendar view only if backed by `MaintenanceCycle` dates | `generate_cycle` rules | Calendar grid view = GAP (selector) | M04 | ADAPT; DEFER calendar |
| 15 | Inspections (`OtherPages`) | `checklists/*` | list/detail | Styling | M08 gates | None | M08 | ADAPT |
| 16 | `InventoryPage` | `inventory/*` | KPIs, tables, workflow forms | Styling, stock health badges | `services.py` is the only stock mutator; reservations | Reference "attention queue" = selector GAP | M09 | ADAPT; DEFER attention queue |
| 17 | `SLAPage` | `sla/*` | KPIs, breach table | Styling | M11 evaluation engine | None | M11 | ADAPT |
| 18 | Contracts (`OtherPages`) | `contracts/*` | tabs | Styling | Overlap rule, coverage engine | None | M10 | ADAPT |
| 19 | QR/Barcode (`OtherPages`) | `identification/*`, `static/js/qr_scan.js` | scan card | Styling | Resolve-then-authorize, camera scanner CSS | None | M12 | ADAPT |
| 20 | `ClientDashboard`, client portal | `portal/dashboard.html`, `requests.html`, `detail.html` | KPI + request list | Styling | Client sees only ownership-scoped, client-safe data | None | M13 | ADAPT |
| 21 | `ReportsPage` | `dashboards/*`, report snapshots (API) | report cards | Only reports backed by `ReportSnapshot` | Real data only | Reference report list mostly GAP | M14 | DEFER non-backed reports |
| 22 | `AuditPage` (+ 5 sub-pages in nav) | `audit/list.html`, `detail.html`, `reports.html` | filters, tables | Styling; closure approvals/evidence exports only if backed | Audit is append-only, read-only UI | "Closure approvals", "evidence exports" = verify vs M15 | M15 | ADAPT; DEFER unbacked sub-pages |
| 23 | Notifications, Profile, Settings (`OtherPages`) | `notifications/*`, `accounts/profile.html`, `tenancy/organization.html` | pages | Styling | Real settings only | Reference Settings tabs likely GAP | module/shell | ADAPT; DEFER unbacked tabs |
| 24 | Forgot password | `accounts/password_reset*.html` | card | Styling | Token flow, no user enumeration | None | auth | ADAPT |

## Proposed order (each item = one bounded task, tests re-run per slice)
1. Tokens + shell (sidebar, topbar, page header, KPI, badge, table, filter bar) in `app.css` + `shell.html` + `components/`. Visible on every screen, so check the whole app at 4 widths, dark text contrast, and that all existing UI tests still pass.
2. Login/auth pages (#1, #24).
3. Dashboards (#4, #5).
4. Core lists/details: assets, incidents, work orders (#8-#11), then inventory/maintenance/SLA/contracts.
5. Technician, portal, audit, remaining.
6. M01 sites (#7) after the in-progress M01 work is committed.

## Open questions for the Team Lead
- Gold/navy: adopt the reference palette globally (changes the current blue accent), or keep blue and only adopt layout? (Recommend adopt, see token note.)
- Dispatch Board (#12): is a board view wanted, given HPE only requires assignment?
- Attention queue, PM calendar, unbacked reports (#14, #16, #21): build backend selectors, or leave out?

## Fidelity requirement (Team Lead, 2026-10-05)
The reference is the visual design authority. Per screen, reproduce its colours, typography, spacing, sizing, cards, buttons, forms, tables, filters, tabs, badges, icons, sidebar, header, page headers, dashboard and detail composition, responsive behaviour and hierarchy as closely as practical, translated into Django templates + Bootstrap 5 + HTMX. Reference decides HOW it looks; FieldOps decides WHAT it does. No React/Tailwind architecture, demo data, demo auth or invented functionality; reference features without a real backend are DEFERRED. Result must feel like one product.
