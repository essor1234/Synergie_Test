# Bright Path Scheduling

Bright Path Scheduling is a small internal web application for a tutoring center. Owners can inspect the current center schedule, receptionists can create and maintain lessons, and tutors can view only their own lessons. FastAPI provides the HTTP API, Streamlit provides the responsive interface, and Python's built-in SQLite support stores local data.

## Quick start

Windows PowerShell and [`uv`](https://docs.astral.sh/uv/) are required.

```powershell
Set-Location -LiteralPath 'D:\[Test]_SynergieGlobal\SynergieProject'
.\init.ps1 -Action Setup
.\init.ps1 -Action Verify
.\init.ps1 -Action Start
```

Open the application at `http://127.0.0.1:8501`. The API is available at `http://127.0.0.1:8000`; its generated documentation is at `http://127.0.0.1:8000/docs`.

The start action validates and applies the seed idempotently before starting both services. Inspect or stop them with:

```powershell
.\init.ps1 -Action Status
.\init.ps1 -Action Stop
```

For setup, recovery, reset, process-safety, and handoff guidance, see [RUNBOOK.md](RUNBOOK.md).

## Demo workflow

1. Open the Streamlit application and select **Owner** to inspect all current lessons, details, and revision history.
2. Select **Receptionist**, open **Manage lessons**, and use the Create, Edit, or Remove tab. Each mutation requires a reason.
3. Edit `L034`, moving it from 09:00 to 10:00 on 10 March 2026. The application accepts the back-to-back slot, increments the lesson version, and records the before/after revision.
4. Select **Tutor**, choose **Ngoc Anh**, and inspect **My schedule**. Only that tutor's lessons are visible; revised lessons are marked as changed.

The demo role selector is not production authentication. A visible change does not mean that a tutor read or acknowledged it.

## Role permissions

| Capability | Owner | Receptionist | Tutor |
| --- | --- | --- | --- |
| View center schedule | Yes | Yes | No |
| View own schedule | N/A | N/A | Yes |
| View allowed lesson detail and history | Yes | Yes | Yes |
| View allowed people and rooms | Yes | Yes | Yes |
| Create, edit, or remove a lesson | No | Yes | No |

Lesson removal is soft deletion: it disappears from current schedules, but the lesson and its revision remain auditable.

## Scheduling safeguards

Receptionist writes are rejected when they:

- overlap an active tutor, room, or student booking;
- give a tutor more than six active lessons in one day;
- schedule a lesson on Monday;
- use a duration other than 60 or 90 minutes;
- use fewer than one or more than two students;
- use unknown references or inconsistent cancellation data; or
- submit an out-of-date `expected_version`.

Cancelled lessons free their time and room. No-shows continue to occupy them. Back-to-back lessons are allowed. The supplied historical rows remain unchanged even where they violate present-day safeguards; validation applies when a receptionist creates or changes operational data.

## Seed data

Preview validates every source field without opening or changing SQLite:

```powershell
.\.venv\Scripts\python.exe scripts\seed_database.py --mode preview
```

Apply the validated seed to the ignored runtime database:

```powershell
.\.venv\Scripts\python.exe scripts\seed_database.py --mode apply
```

The import preserves 34 immutable raw lesson rows and creates 33 operational lessons with 34 participant relationships. `L009` and `L010` remain separate evidence rows but map to the paired operational lesson `L009` through `data/source/group_resolutions.json`. Reapplying identical input is a no-op. Only the observed room identifiers `R1`–`R3` are imported.

The fixed demonstration timestamp is configured by `BRIGHT_PATH_DEMO_NOW` and defaults to `2026-03-10T08:00:00+07:00`, inside the source dataset period.

## API

Demo requests require `X-Demo-Role: owner`, `receptionist`, or `tutor`. Tutor requests also require `X-Demo-Tutor-Id`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health |
| `GET` | `/api/v1/schedule` | Role-filtered current schedule |
| `GET` | `/api/v1/tutors/{tutor_id}/schedule` | Allowed tutor schedule |
| `GET` | `/api/v1/lookups` | Role-filtered tutors, students, and rooms |
| `GET` | `/api/v1/lessons/{lesson_id}` | Lesson detail |
| `POST` | `/api/v1/lessons` | Receptionist creates a lesson |
| `PATCH` | `/api/v1/lessons/{lesson_id}` | Receptionist replaces editable lesson fields |
| `DELETE` | `/api/v1/lessons/{lesson_id}` | Receptionist soft-deletes a lesson |
| `GET` | `/api/v1/lessons/{lesson_id}/history` | Revision history |

Unsafe or stale writes return `409` with a specific explanation. The API intentionally has no bulk schedule-replacement endpoint because replacing the full schedule would make version checks, permissions, and revision evidence ambiguous.

## Project structure

```text
src/bright_path/
├── domain/models.py          # plain domain objects
├── services/lesson_service.py # use cases and write safeguards
├── storage/                  # SQLite schema and source import
├── api/                      # FastAPI routes and schemas
├── ui/                       # Streamlit pages and HTTP client
└── settings.py
```

This is intentionally light OOP: domain records, `LessonService`, and `ApiClient` have focused responsibilities. The project does not add an ORM, repository interfaces, or a dependency-injection framework for an assessment-sized workflow.

## Verification

Run the complete formatting/static check and test suite:

```powershell
.\init.ps1 -Action Verify
```

The suite covers source preservation, schema coverage, repeat imports, role privacy, business rules, transaction rollback, API responses, stale writes, response formatting, and role-specific Streamlit navigation.

## Reflection and deferred work

The implementation demonstrates a complete spreadsheet-to-application path without silently repairing the supplied history. Optimistic versions and transactional revisions make receptionist edits safer while keeping the architecture small. Native Streamlit controls gave the MVP a usable responsive interface quickly, though they are less customizable than a dedicated front end.

Deferred work includes production authentication, push delivery and read acknowledgement, lesson deletion recovery UI, participant-level cancellation, billing and tutor payment, messaging integrations, two-way spreadsheet synchronization, PostgreSQL migrations, and broader analytics. Live updates currently mean that a refresh reads the latest committed data; they do not mean WebSocket delivery or tutor acknowledgement.
