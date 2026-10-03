# Phase 3 manual test guide: Checklists (M08) and Technician Workspace (M07)

Goal: prove by hand the technician job from assignment to review, with a required checklist gating completion.
Time: about 60 minutes. **Not yet run in a browser** (Team Lead deferred browser, responsive and Supabase acceptance to the end of the project). Phase 3 is not applied to Supabase: merge, migrate (`checklists.0001`, `workspace.0001`), collectstatic and restart before using it there. Never paste passwords; they live in the git-ignored `.env.qa-users`.

**Accounts** (Phase 2 users; roles sync additively when you run `migrate`/role sync): Alice `owner@alpha.test` (Owner), Tom `tech@alpha.test` (Technician), Pat `planner@alpha.test` (Planner), Sue `supervisor@alpha.test` (Supervisor), Olly `ops@alpha.test` (Operations Manager), Rita `reader@alpha.test` (Auditor), Bob `owner@beta.test` (Org B). Test data: site `BLR-OPS`, asset `GEN-BLR-001`.

## 1. Menus and permissions
| # | Do | Expect |
|---|---|---|
| 1.1 | Sign in as Sue | Operations menu shows **Checklists** and **Inspections**. |
| 1.2 | Sign in as Tom | Menu shows **My Jobs**; **no** Checklists / Inspections entries; `/app/checklists/` answers 403. |
| 1.3 | Sign in as Rita | Checklists + Inspections visible and read-only (no New / Activate buttons). |

## 2. Build and activate a required checklist (M08, as Sue)
| # | Do | Expect |
|---|---|---|
| 2.1 | Checklists > New checklist: name `Generator weekly round`, applies to *Preventive*, tick **Required**, Create | Draft opens; **Activate** is disabled (no questions). |
| 2.2 | Add: `Casing free of leaks` (Pass / fail, required) | Row appears. |
| 2.3 | Add: `Discharge pressure` (Number, min 2, max 6, unit bar, required) | Row shows min/max. |
| 2.4 | Add: `Seal condition` (Selection; options `Good`, `Worn`, `Failed`; exception `Failed`; required; evidence required) | Row shows options + exception. |
| 2.5 | Add: `Remarks` (Text, not required) | Row appears. |
| 2.6 | Try Add with 1 option only, or a minimum above the maximum | Message / error, nothing saved. |
| 2.7 | Move `Remarks` up with the arrows; Edit a question | Order and text change; persists after refresh. |
| 2.8 | Activate | Status Active; the page says the version is frozen; Add-a-question form disappears. |
| 2.9 | Click **New version** | Draft v2 with the same questions; Activate v2: v1 becomes Inactive. (Skip if you want to keep v1 for the next steps.) |

## 3. Technician workspace (M07, as Tom)
Prepare as Pat: create a **Preventive** work order on `GEN-BLR-001`, plan, assign to Tom, dispatch.
| # | Do | Expect |
|---|---|---|
| 3.1 | My Jobs | The job is listed under *To do* with a "1 checklist pending" badge; other technicians' jobs are not. |
| 3.2 | Open the job | Overview, checklist list ("Not started"), notes, time, material, evidence, activity. **Start work** button. |
| 3.3 | Press **Start work** | Status In progress; checklist **Start checklist** button appears. |
| 3.4 | Add a note; refresh | Note persists with author and time. |
| 3.5 | Put on hold without a reason | Refused. With a reason: On hold; notes / time forms disappear. **Resume**. |

## 4. Checklist execution and the completion gate
| # | Do | Expect |
|---|---|---|
| 4.1 | In the job type resolution notes `All checks done properly` and press **Complete** | Refused: "Complete the required checklist(s) ..." (also visible in the yellow box before pressing). Status stays In progress. |
| 4.2 | **Start checklist** | Checklist page with Pass / Fail buttons, number box, selection, text. |
| 4.3 | Enter `abc` as the pressure, **Save answers** | Inline error "must be a number"; nothing saved. |
| 4.4 | Answer Fail, pressure 7.5, seal Failed; Save | Saved without reload; items show **Exception**; yellow box lists the missing findings / evidence. |
| 4.5 | **Complete inspection** | Refused: record a finding; evidence needed for the seal question. Answers stay saved (refresh keeps them). |
| 4.6 | Record a finding for question 1 and one for the seal (severity High); upload a file for the seal answer | Findings listed with status Open. |
| 4.7 | **Complete inspection** | Returns to the job; checklist shows Completed; yellow box gone. Re-opening the checklist is read-only. |
| 4.8 | Record time (e.g. 2 h, today), note material `Grease cartridge` qty 1, upload a photo | Rows appear; material shows "no stock is moved". |
| 4.9 | Press **Complete** with notes | Work order Completed. |
| 4.10 | Try hours `0`, `25`, a future date, a `.exe` upload | Each refused with a message; no row is created. |

## 5. Review and closure (as Sue)
| # | Do | Expect |
|---|---|---|
| 5.1 | Work Orders > the job > Start supervisor review | Supervisor review. |
| 5.2 | Inspections > open the inspection | Answers with Exception badges, findings, evidence links. Resolve a finding with notes | Finding becomes Resolved. |
| 5.3 | Close the work order | Closed. (Before 4.7 this would have been blocked with the checklist reason.) |

## 6. Negative / security checks
| # | Do | Expect |
|---|---|---|
| 6.1 | As another technician open Tom's job URL, inspection URL and evidence download URL | 404 for all (not 403). |
| 6.2 | As Rita (auditor) open Tom's job | Visible but no action buttons; direct POST of a note answers 403. |
| 6.3 | As Bob (Org B) open Alpha's checklist, inspection, job and file URLs | 404 / 403, nothing leaks. |
| 6.4 | As Tom POST `/app/workspace/<job>/transition/close/` (browser dev tools / curl with session) | Refused ("not available in the technician workspace"), status unchanged. |
| 6.5 | Open the checklist page in two tabs, complete in tab A, press Save in tab B | Tab B shows "completed ... can no longer be changed"; stored answers unchanged. |
| 6.6 | API: `POST /api/v1/work-orders/<id>/transition/ {"action":"complete"}` as Tom while the checklist is incomplete | 409 `checklist_incomplete`. |
| 6.7 | A site-scoped supervisor (other site) opens the inspection URL | 404. |

## 7. Responsive (DEFERRED, do at project end)
1920x1080, 1366x768, 768x1024 and 390x844 for My Jobs, Job, Checklist; no horizontal overflow, clipped buttons or unusable forms; browser console and network clean.

## 8. Database spot checks (read-only SQL, Supabase schema `fieldops` after apply)
`checklists_inspection` (status COMPLETED, completed_at set), `checklists_inspectionresponse` (is_exception flags), `checklists_finding`, `workspace_worknote`, `audit_auditlog` actions `inspection.*`, `checklist.*`, `work_order.note_added`.

## Result sheet
| Section | Pass / Fail | Tester | Date | Notes |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |
| 8 | | | | |
