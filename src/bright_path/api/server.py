from __future__ import annotations

import uvicorn

from bright_path.api.main import app
from bright_path.settings import API_HOST, API_PORT


def run() -> None:
    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")
