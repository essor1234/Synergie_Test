# Agent Progress

## Current verified state

- Phase 0 is complete: the project can be set up, verified, started, inspected, and stopped through `init.ps1`.
- The FastAPI and Streamlit shells are healthy on ports 8000 and 8501.
- The supplied brief and two CSV files are preserved byte-for-byte in `data/source`.
- Phase 1 domain models and the preview/apply SQLite seed importer are complete.
- The seed preserves 34 raw lesson rows and creates 33 lessons with 34 participants.
- `L009` and `L010` map to one two-student lesson only through `group_resolutions.json`.
- Scheduling conflict and rescheduling behavior are not implemented yet.

## Project locations

- Project root: `D:\[Test]_SynergieGlobal\SynergieProject`
- API: `http://127.0.0.1:8000`
- Streamlit: `http://127.0.0.1:8501`
- Runtime logs: `data\harness`

## Standard commands

```powershell
Set-Location -LiteralPath 'D:\[Test]_SynergieGlobal\SynergieProject'
.\init.ps1 -Action Setup
.\init.ps1 -Action Verify
.\init.ps1 -Action Start
.\init.ps1 -Action Status
.\init.ps1 -Action Stop
```

## Next priority

Wait for explicit approval, then implement Phase 2 conflict rules and safe scheduling service behavior.

## Known blockers

- None currently recorded.

## Latest session

- Date: 2026-09-16
- Work: Completed corrected Phase 1 domain and seed-data implementation.
- Evidence: Ruff passed; pytest passed (19 tests); preview and apply totals matched; repeated apply left the database hash unchanged; supplied source hashes remained unchanged.
