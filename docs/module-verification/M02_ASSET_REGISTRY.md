# M02: Asset Registry

**What it answers:** What equipment do we own, where is it, what is its condition and history?
**Accounts:** `assets@alpha.test` (Asset Manager) does the work; `tech@alpha.test` to prove read-only rights.

## Walkthrough
| # | Do | Expect |
|---|---|---|
| 1 | Sign in as `assets@alpha.test` → **Assets & Locations → Assets** | List with filters (site, category, status, search) |
| 2 | **Categories** button → new category `Generator` (optional custom fields e.g. "Rated power kVA | number | required") and `Pump` | Listed; duplicate name refused; untick *Active* to hide it |
| 3 | **Register asset**: Tag `GEN-001`, Name `Diesel Generator 500 kVA`, Category Generator, Site, Location, Manufacturer `Cummins`, Model, Serial `CU-1`, fill required category fields → **Register asset** | "Asset GEN-001 registered". **Tip:** choosing a category reloads the form to show its fields: re-check the other fields after |
| 4 | Register `GEN-001` again; then another asset with the same manufacturer + serial | Both refused (duplicate tag / duplicate serial). Purchase date after commissioning date refused |
| 5 | Open the asset → **Edit** → change name → Save | History → **Change log** shows `name: old → new` |
| 6 | Edit → change **Site** with a reason, move back | History → **Location history** lists both moves with reasons |
| 7 | **Documents** tab → choose a small `.pdf`/`.txt`, title `Manual`, type → **Upload** | Row with name, size, uploader; **Download** works. A renamed `.exe` is refused |
| 8 | **Meters** tab → add meter `Run hours`/`h`; record `100`, then `120.5` | "Last reading 120.5 h". `110` refused (lower than previous); negative or future time refused |
| 9 | **Coverage** tab | Shows warranty/AMC/contract coverage now (from M10) |
| 10 | **Labels** tab | QR / barcode (M12) |
| 11 | Status buttons in the blue **Next:** bar | See workflow **W5** |

## Negative / security
| Try | Expected |
|---|---|
| Technician opens an asset | Can view and record meter readings; no Edit/Register/status/upload (403 on those addresses) |
| Retired/Disposed asset | Read-only; absent from incident/plan dropdowns |
| Beta user opens an Alpha asset address | Not found |
| Site-limited user opens an asset at another site | Not found |

## Connected modules
M01 site/location · M03 parent/child · M04 plans and meter schedules · M05 incidents are raised on assets · M06 work orders · M09 parts used on assets · M10 coverage · M12 labels · M14 MTTR/MTBF/downtime by asset · M15 history.

## Pass when
Assets register with validation, edits and moves leave a change/location history, documents and meters follow their rules, and access respects role, site and company.
