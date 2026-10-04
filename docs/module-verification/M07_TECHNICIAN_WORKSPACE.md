# M07: Technician Workspace

**What it answers:** What do I (the technician) have to do today, and how do I finish it?
It is **not** a second work-order system: every button calls the M06 rules.
**Account:** `tech@alpha.test` (Tom Technician).

## Screens
- **Operations → My Jobs** (`/app/workspace/`): only jobs assigned to the signed-in technician, with site and planned time.
- **Insights → My work summary**: personal counts (open, done, hours).
- The job page: start/hold/resume/complete, labor, material, evidence, checklist/inspection (M08), site and route details.
- Works on a phone-width screen: narrow the browser window to ~400 px and use the hamburger menu (☰) at the top left.

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | Sign in as Tom → **My Jobs** | Only Tom's jobs. A job assigned to someone else is not listed |
| 2 | Open an assigned (Dispatched) job → **Start** | In Progress |
| 3 | **Put on hold** with reason → **Resume** | On Hold, then In Progress |
| 4 | **Labor & material**: record labor and material | Totals update |
| 5 | **Evidence** tab: attach a photo | Listed |
| 6 | Open the linked checklist and answer items (M08) | Progress shown |
| 7 | Enter resolution notes → **Complete** | Completed; supervisor can now review |
| 8 | Notification bell | "WO assigned to you", "ready to start", "returned for rework" arrive here |
| 9 | Open another technician's job address | Not found |
| 10 | Try Edit/Assign/Close buttons | Not shown; addresses give 403 |

## Connected modules
M06 (authoritative work order) · M08 checklists · M09 parts used · M01/M02 site and asset details · M12 scan label to jump to the asset.

## Pass when
A technician can run a job from start to completion using only their own screens and cannot see or change anything beyond their rights.
