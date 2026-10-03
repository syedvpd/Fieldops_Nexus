---
name: e2e-acceptance
description: HPE Day-90 seven-journey acceptance procedure and PASS/PARTIAL/FAIL traceability matrix format. Load for the final audit or when writing tests/e2e.
---
Journeys are listed in `docs/TRACEABILITY.md`. Each gets `tests/e2e/test_journey_N.py` driving real services/API with real DB (no mocks of our own code) and asserting audit entries, state history and dashboard numbers. Final report: matrix of requirement -> PASS/PARTIAL/FAIL -> exact evidence (test name/file:line) -> defects. Never claim UAT-ready with open Critical/High defects.
