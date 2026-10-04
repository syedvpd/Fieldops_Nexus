# W5: Asset Status workflow (modules M02 and M03)

**HPE state machine:** ACTIVE → UNDER MAINTENANCE → OUT OF SERVICE → ACTIVE / RETIRED / DISPOSED

**Plain meaning:** an asset is working (Active). It can go into maintenance, be marked out of service, and come back into service. At the end of its life it is Retired and then Disposed. Retired/Disposed assets are read-only.

## Who does what
Asset Manager, Operations Manager or Owner change status: `assets@alpha.test`, `ops@alpha.test`, `owner@alpha.test`. Everyone else can view.

## Allowed moves (anything else is refused)
| From | To | Button |
|---|---|---|
| Active | Under Maintenance | **Start maintenance** |
| Under Maintenance | Active | **Complete maintenance** |
| Under Maintenance | Out of Service | **Mark out of service** |
| Out of Service | Active | **Return to service** |
| Out of Service | Retired | **Retire** (confirm dialog) |
| Retired | Disposed | **Dispose** |
Active → Out of Service directly is intentionally **not** allowed (decision D-027: go through maintenance first).

## Walkthrough
1. Sign in as `assets@alpha.test`. **Assets & Locations → Assets** → open `GEN-001` (or a spare asset you registered for the test).
2. In the blue **Next:** bar type a reason (`Quarterly service`) → **Start maintenance**. Expect badge **Under Maintenance**; bar now offers *Complete maintenance* and *Mark out of service*.
3. Click **Mark out of service** with the reason box **empty**. Expect the browser/server to require a reason; nothing changes.
4. Enter a reason → **Mark out of service** → **Out Of Service**. Then **Return to service** → **Active**.
5. On a spare asset: Start maintenance → Mark out of service → **Retire** → confirm. Expect **Retired**, text "this asset is retired: read-only", no **Edit**, no new meter readings, no components.
6. Optionally **Dispose** a retired asset (`DSP-001` in the test data is Disposed).
7. Open the **History** tab: *Status history* lists every change newest first (from → to, who, when, reason); *Change log* shows `asset.status_changed`.

## Automatic changes from other modules
- Starting a **work order** on an asset can move it Under Maintenance; completing/closing returns it to Active (M06 rule).
- A **Retired/Disposed** asset cannot be chosen for a new incident, plan or contract (it is missing from the dropdowns). `PMP-001` (Retired) is the test example.

## Negative checks
| Try | Expected |
|---|---|
| Status on the Edit form | No status field exists; status only changes through the bar |
| Active → Retire | Not offered |
| Edit or add meter on Retired asset | Refused |
| Technician tries the status URL | Access denied (403) |
| Beta user opens the asset | Not found |

## Connected modules
M01 site/location · M03 hierarchy (parent/child; moving sites needs detaching first) · M04 PM and M05 incidents choose active assets only · M06 work orders drive status · M14 downtime/availability metrics use status history · M15 audit.

## Pass when
Every allowed move works with a recorded reason, every disallowed move is refused, terminal states are read-only, and History/Audit list each change.
