# M15: Audit & Compliance

**What it answers:** Who did what, when, to which record, and what changed?
**Accounts:** `owner@alpha.test`, `reader@alpha.test` (Auditor).

## How it works
Every important action (sign in/out, create/edit, status change, user/role change, scan, export, stock movement, SLA breach) writes an **append-only** audit entry: time, actor, action, record, site, before/after, IP. Entries cannot be edited or deleted, not even from the admin.

## Screens (Compliance menu)
**Audit Trail** (`/app/audit/`): filter by date, actor, action, category, site; open an entry for details. **Compliance reports**: role-controlled reports. **Export results**: **CSV / Excel (XLSX) / PDF** of the filtered rows (the export itself is audited).

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | Perform an action (e.g. edit an asset name) then open **Audit Trail** | New entry `asset.updated` with before → after |
| 2 | Filter by actor and action | Only matching rows |
| 3 | Open an entry | Details: before/after, metadata, IP |
| 4 | **Export results → CSV**, then XLSX, then PDF | File downloads; CSV starts with "When (UTC), Actor, Action, Entity type, ..."; XLSX opens in Excel; PDF readable |
| 5 | Asset **History** tab and work order **History** tab | Per-record change history |
| 6 | **Compliance reports** | Report list for permitted roles |
| 7 | Work-order **evidence package** | Per-WO evidence export (history, labor, evidence) |
| 8 | Try to change an entry (admin or database) | Not possible: protected |
| 9 | Auditor `reader@alpha.test` | Can view and export; cannot change anything |
| 10 | Site-limited user | Sees only entries for allowed sites |
| 11 | Beta user | Sees only Beta entries |
| 12 | Technician opens `/app/audit/` | Access denied (403) |

## Connected modules
Every module writes here. Exports are themselves audited.

## Pass when
Each earlier test left a visible entry, exports match the screen, and entries cannot be altered or seen across companies.
