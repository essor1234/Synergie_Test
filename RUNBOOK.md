# Bright Path Operations Runbook

This runbook explains how to set up, run, verify, recover, and hand off the Bright Path Scheduling MVP on Windows. It is adapted from the reusable PowerShell harness guidance in `D:\[Important]_InitRepo` and describes this repository's actual behavior.

## Scope and prerequisites

- Windows PowerShell 7 or newer.
- [`uv`](https://docs.astral.sh/uv/) installed and available on `PATH`.
- The project checked out at `D:\[Test]_SynergieGlobal\SynergieProject`.
- No production credentials are required for the demo application.

The API runs on port `8000`; the Streamlit interface runs on port `8501`.

## Safe navigation

The project path contains square brackets. PowerShell treats square brackets as wildcard characters, so always use `-LiteralPath` with a quoted full path.

```powershell
Set-Location -LiteralPath 'D:\[Test]_SynergieGlobal\SynergieProject'
```

To run the harness without changing the current folder:

```powershell
& 'D:\[Test]_SynergieGlobal\SynergieProject\init.ps1' -Action Status
```

Use `-LiteralPath` for file checks and reads too:

```powershell
Get-Content -LiteralPath 'D:\[Test]_SynergieGlobal\SynergieProject\session-handoff.md'
Test-Path -LiteralPath 'D:\[Test]_SynergieGlobal\SynergieProject\.env.local'
```

## Standard lifecycle

From the project root, use these commands in order:

```powershell
.\init.ps1 -Action Setup
.\init.ps1 -Action Verify
.\init.ps1 -Action Start
```

Open `http://127.0.0.1:8501` for the application. The FastAPI health endpoint is `http://127.0.0.1:8000/health`, and interactive API documentation is available at `http://127.0.0.1:8000/docs`.

Use these commands while or after the application is running:

```powershell
.\init.ps1 -Action Status
.\init.ps1 -Action Stop
```

| Action | What it does |
| --- | --- |
| `Setup` | Synchronizes the locked Python environment with `uv sync --all-extras`. It safely renames a lone `.env` file to `.env.local`. |
| `Verify` | Runs Ruff and the full pytest suite. |
| `Start` | Ensures ports are free, applies the idempotent source seed, starts API and UI processes, and waits for both health checks. |
| `Status` | Reports each configured port and whether the harness owns any recorded processes. |
| `Stop` | Stops only processes whose process ID and start time match the harness state record. |

## Data and reset procedure

`Start` applies the source seed automatically. It preserves the source CSV files and stores generated SQLite data at:

```text
data\runtime\bright_path.db
```

The runtime database is ignored by Git and can always be recreated from `data\source`. To validate a source import without changing SQLite:

```powershell
.\.venv\Scripts\python.exe scripts\seed_database.py --mode preview
```

To apply the import manually:

```powershell
.\.venv\Scripts\python.exe scripts\seed_database.py --mode apply
```

For a clean demo state:

1. Stop services with `init.ps1 -Action Stop`.
2. Confirm the target is exactly `data\runtime\bright_path.db` under this project.
3. Delete only that generated database file.
4. Run `init.ps1 -Action Start` to recreate it from the unchanged source evidence.

Do not alter or delete files in `data\source`; they are immutable input evidence for the assessment.

## Demo access and normal operation

The Streamlit sidebar has a demo role selector:

- **Owner**: view the center schedule, lesson history, and reference data.
- **Receptionist**: the owner view plus create, edit, and soft-delete lesson actions.
- **Tutor**: view only lessons assigned to the selected tutor profile.

Receptionist updates require a reason and current lesson version. The service rejects unsafe changes such as overlapping tutor, room, or student bookings, Monday lessons, invalid durations, excessive tutor capacity, or stale versions. A deletion hides the lesson from current schedules but retains its history.

The role selector is for demonstration only. It is not production authentication, and a changed tutor schedule does not mean the tutor has acknowledged the change.

## Expected smoke test

After `Start`:

1. Visit the Streamlit URL and confirm that the owner schedule loads.
2. Change the role to Receptionist and confirm that **Manage lessons** appears.
3. Open the Tutor role and confirm that the schedule contains only that tutor's lessons.
4. Optionally update `L034` from 09:00 to 10:00 on 10 March 2026. The change should create version 2 and an entry in lesson history.
5. Run `init.ps1 -Action Verify` before handing work over.

## Port and process recovery

If `Start` says port `8000` or `8501` is already in use:

1. Run `init.ps1 -Action Status`.
2. If the harness owns the process, run `init.ps1 -Action Stop` and try `Start` again.
3. If another application owns the port, stop that application or change Bright Path's configured port environment variable.
4. Do not terminate an unknown process based only on its port number.

The harness validates both process ID and start time before it stops anything. A stale process-state file is not enough authority to terminate a process.

## Environment and secret handling

- Keep `.env` and `.env.local` out of version control.
- The harness renames `.env` to `.env.local` only if `.env.local` does not already exist.
- If both files exist, the harness stops without changing either file.
- Never place tokens, passwords, or personal information in command arguments, URLs, logs, screenshots, or Git commits.
- Use environment files or an operating-system secret store if a future feature needs a secret.

## Failure guide

| Symptom | First action | Escalation |
| --- | --- | --- |
| `uv` is not recognized | Install `uv`, reopen PowerShell, then run `Setup`. | Confirm `uv --version` is available. |
| Setup fails | Rerun `Setup` and read the non-secret error. | Check Python compatibility and network/package availability. |
| Verification fails | Read the failing test or Ruff output. | Do not mark a feature passing until it is fixed and rerun. |
| API or UI is unhealthy | Run `Status`, then inspect `data\harness` logs. | Stop harness-owned processes and retry `Start`. |
| Database import fails | Run seed `--mode preview`. | Correct the source/resolution data deliberately; do not silently repair evidence. |
| A lesson save is rejected | Read the visible validation or stale-version message. | Refresh the schedule, choose a safe slot, and retry with a reason. |

## Session handoff

Before ending a work session:

1. Run `init.ps1 -Action Verify`.
2. Update `feature_list.json` with concrete passing evidence.
3. Update `agent-progress.md` and `session-handoff.md` with current truth and the next action.
4. Complete `clean-state-checklist.md`.
5. Stop local services unless someone needs the running demo.
6. Confirm `git status --short --branch` has no generated runtime files, credentials, or unrelated changes.

## Boundaries

This MVP uses local SQLite, demo role switching, refresh-based current data, and no delivery/read acknowledgement. Production authentication, notifications, billing, payroll, two-way spreadsheet synchronization, and broad analytics remain intentionally out of scope.
