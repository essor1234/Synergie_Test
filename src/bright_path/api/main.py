from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Bright Path Scheduling API",
    version="0.1.0",
    description="Internal scheduling API for Bright Path Learning Centre.",
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bright-path-api"}
