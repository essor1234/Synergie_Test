# Session Handoff

## What is working

- `init.ps1` supports Setup, Verify, Start, Status, and Stop.
- FastAPI exposes `GET /health` on port 8000.
- Streamlit renders the Bright Path foundation page and health endpoint on port 8501.
- Local clean-code and clean-architecture skills pass package validation.
- Source evidence in `data/source` matches the supplied files byte-for-byte.
- Domain models cover users, tutors, students, rooms, lessons, statuses, and revisions.
- Seed preview validates every CSV field, relationship, timestamp, status, and cancellation rule before SQLite is opened.
- Seed apply stores immutable raw rows and the resolved operational schedule; identical re-imports are no-ops.

## Current work

- Phase 0 and corrected Phase 1 are complete. `MVP-001` remains in progress.

## Next action

After explicit approval, begin Phase 2: conflict rules, transactional rescheduling, version checks, and revision history.

## Blockers

- None currently recorded.

## Safety reminders

- Never include secret values or personal identifiers.
- Preserve unrelated user work and the supplied source evidence.
