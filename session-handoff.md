# Session Handoff

## What is working

- `init.ps1` supports Setup, Verify, Start, Status, and Stop.
- FastAPI exposes `GET /health` on port 8000.
- Streamlit provides responsive schedule, detail, history, directory, and lesson-management views on port 8501.
- Local clean-code and clean-architecture skills pass package validation.
- Source evidence in `data/source` matches the supplied files byte-for-byte.
- Domain models cover users, tutors, students, rooms, lessons, statuses, and revisions.
- Seed preview validates every CSV field, relationship, timestamp, status, and cancellation rule before SQLite is opened.
- Seed apply stores immutable raw rows and the resolved operational schedule; identical re-imports are no-ops.
- FastAPI exposes role-filtered schedules, reference data, lesson details, revision history, and receptionist-only create/update/soft-delete operations.
- Lesson mutations use optimistic versions, atomic revisions, and inline business-rule validation.
- Starting the harness applies the idempotent seed before launching the API and UI.

## Current work

- Phases 0–4 are complete. `MVP-001` is passing and the assessment release is ready locally.

## Next action

No action is required. If requested, push the local commits or begin one explicitly selected deferred production feature.

## Final verification

- Clean `uv` setup completed from an empty generated database.
- Ruff and all 44 tests passed.
- API and Streamlit health checks returned HTTP 200.
- Moving `L034` from 09:00 to 10:00 produced version 2 and one revision.
- Owner visibility, tutor T1-only visibility, and the changed marker were confirmed.
- Desktop and narrow-width rendered reviews completed without browser console errors.

## Blockers

- None currently recorded.

## Safety reminders

- Never include secret values or personal identifiers.
- Preserve unrelated user work and the supplied source evidence.
