from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DATA_DIR = PROJECT_ROOT / "data" / "source"
DATABASE_PATH = PROJECT_ROOT / "data" / "runtime" / "bright_path.db"
API_HOST = os.getenv("BRIGHT_PATH_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("BRIGHT_PATH_API_PORT", "8000"))
UI_PORT = int(os.getenv("BRIGHT_PATH_UI_PORT", "8501"))
API_URL = os.getenv("BRIGHT_PATH_API_URL", f"http://{API_HOST}:{API_PORT}")
DEMO_NOW = os.getenv("BRIGHT_PATH_DEMO_NOW", "2026-03-10T08:00:00+07:00")
