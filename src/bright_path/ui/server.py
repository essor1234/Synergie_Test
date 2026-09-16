from __future__ import annotations

import sys

from streamlit.web import cli as streamlit_cli

from bright_path.settings import PROJECT_ROOT, UI_PORT


def run() -> None:
    app_path = PROJECT_ROOT / "src" / "bright_path" / "ui" / "app.py"
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        f"--server.port={UI_PORT}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
    ]
    raise SystemExit(streamlit_cli.main())
