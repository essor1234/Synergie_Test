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

Feature behavior and demonstration instructions will be added in later gated phases.
