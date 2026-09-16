from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from bright_path.api.lessons import router as lessons_router
from bright_path.api.schedules import router as schedules_router
from bright_path.services.lesson_service import (
    LessonNotFoundError,
    LessonValidationError,
    PermissionDeniedError,
    StaleLessonError,
)

app = FastAPI(
    title="Bright Path Scheduling API",
    version="0.1.0",
    description="Internal scheduling API for Bright Path Learning Centre.",
)
app.include_router(lessons_router)
app.include_router(schedules_router)


@app.exception_handler(LessonNotFoundError)
def lesson_not_found(_: Request, error: LessonNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error), "code": "not_found"})


@app.exception_handler(PermissionDeniedError)
def permission_denied(_: Request, error: PermissionDeniedError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(error), "code": "forbidden"})


@app.exception_handler(StaleLessonError)
def stale_lesson(_: Request, error: StaleLessonError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(error), "code": "stale_version"})


@app.exception_handler(LessonValidationError)
def invalid_lesson(_: Request, error: LessonValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": str(error),
            "code": "lesson_validation",
            "issues": list(error.issues),
        },
    )


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bright-path-api"}
