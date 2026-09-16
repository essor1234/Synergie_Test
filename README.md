# Bright Path Scheduling

Bright Path Scheduling is an assessment-sized internal tool for safe tutoring-center schedule changes. The project uses FastAPI for its API, Streamlit for its interface, and SQLite for local persistence.

## Foundation commands

```powershell
Set-Location -LiteralPath 'D:\[Test]_SynergieGlobal\SynergieProject'
.\init.ps1 -Action Setup
.\init.ps1 -Action Verify
.\init.ps1 -Action Start
.\init.ps1 -Action Status
.\init.ps1 -Action Stop
```

The API listens on `http://127.0.0.1:8000` and the Streamlit application on `http://127.0.0.1:8501`.

## Seed data

Preview validates every source field without opening or changing SQLite:

```powershell
.\.venv\Scripts\python.exe scripts\seed_database.py --mode preview
```

Apply the validated seed to the ignored runtime database:

```powershell
.\.venv\Scripts\python.exe scripts\seed_database.py --mode apply
```

The import preserves 34 immutable raw lesson rows and creates 33 operational lessons with 34 participant relationships. `L009` and `L010` remain separate evidence rows but map to the paired operational lesson `L009` through `data/source/group_resolutions.json`. Reapplying identical input is a no-op.

Scheduling behavior and demonstration instructions will be added in later gated phases.
