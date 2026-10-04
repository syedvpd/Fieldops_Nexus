# M12: QR / Barcode identification

**What it answers:** Scan a label on the machine and land on the right asset, safely.
**Accounts:** `assets@alpha.test` issues labels; `tech@alpha.test` scans and reports; `owner@beta.test` proves isolation.

## How it works
Each asset can have one active **QR code** (and optionally a **Code 128 barcode**). The code is a random, meaningless token (22 characters): scanning only *finds* the asset; the usual login, company and site permissions still apply. Too many failed scans (15 in 10 minutes) are throttled and audited.

## Checklist
| # | Do | Expect |
|---|---|---|
| 1 | Sign in as `assets@alpha.test` → open an asset → **Labels** tab (wait a second for the panel) | "QR code: None" with **Generate qr code** |
| 2 | Click **Generate qr code** | "Label generated"; QR panel Active with **View / Download SVG / Download PNG** |
| 3 | Click **Printable label** | Sheet with asset tag, name, site and the QR, plus **Print** |
| 4 | **Scan a label** (also in the left menu: Assets → *Scan asset label*) | Camera view starts (browser asks permission); point at the printed QR → the asset page opens automatically. No camera? type/paste the label code or the scanned link in **Enter code** → **Open asset** |
| 5 | After scanning, the "Resolved" page offers **Open asset**, **Scan another**, and (if allowed) **Report a problem** | Report creates an incident with the asset prefilled |
| 6 | Labels tab → reason `Label damaged` → **Replace** | Old label listed under *Replaced / revoked*; new one active |
| 7 | Scan the **old** label | Red "This label was revoked or replaced" |
| 8 | Sign in as `tech@beta.test` and open the Alpha label address | "Label not recognised" (nothing about Alpha is revealed) |
| 9 | Labels tab → **Recent scans** | Who scanned and when |

## Negative
Garbage code → "not recognised"; user without access to that site → refused; revoked label never opens the asset via the camera path; Beta cannot use Alpha's labels.

## Connected modules
M02 (labels belong to assets) · M05 (report from scan) · M07 (technicians scan on site) · M15 (scan audit: scanned / unknown / denied / revoked / throttled).

## Pass when
Generate → print → scan opens the asset; replaced labels are dead; other companies get no information.
