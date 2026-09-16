"""FastAPI dependencies for demo actors and application services."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from bright_path.domain.models import User, UserRole
from bright_path.services.lesson_service import LessonService
from bright_path.settings import DATABASE_PATH


def get_lesson_service() -> LessonService:
    return LessonService(DATABASE_PATH)


def get_actor(
    role: Annotated[UserRole, Header(alias="X-Demo-Role")],
    demo_tutor_id: Annotated[str | None, Header(alias="X-Demo-Tutor-Id")] = None,
) -> User:
    if role is UserRole.TUTOR:
        if demo_tutor_id is None:
            raise HTTPException(status_code=400, detail="Tutor role requires X-Demo-Tutor-Id")
        return User(
            id=f"demo-tutor-{demo_tutor_id}",
            name=f"Tutor {demo_tutor_id}",
            role=role,
            tutor_id=demo_tutor_id,
        )
    return User(
        id=f"demo-{role.value}",
        name=f"Demo {role.value.title()}",
        role=role,
    )
