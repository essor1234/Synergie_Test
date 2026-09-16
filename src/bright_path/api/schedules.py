"""Schedule and role-filtered lookup routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from bright_path.api.dependencies import get_actor, get_lesson_service
from bright_path.api.lessons import lesson_response
from bright_path.api.schemas import (
    LessonResponse,
    LookupResponse,
    RoomResponse,
    StudentResponse,
    TutorLookup,
)
from bright_path.domain.models import LessonStatus, User
from bright_path.services.lesson_service import LessonService

router = APIRouter(prefix="/api/v1", tags=["schedules"])

Actor = Annotated[User, Depends(get_actor)]
Service = Annotated[LessonService, Depends(get_lesson_service)]


def schedule(
    actor: Actor,
    service: Service,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    tutor_id: str | None = None,
    room_id: str | None = None,
    lesson_status: Annotated[LessonStatus | None, Query(alias="status")] = None,
) -> list[LessonResponse]:
    lessons = service.list_lessons(
        actor,
        date_from=date_from,
        date_to=date_to,
        tutor_id=tutor_id,
        room_id=room_id,
        status=lesson_status,
    )
    return [lesson_response(lesson) for lesson in lessons]


@router.get("/schedule", response_model=list[LessonResponse])
def get_schedule(
    actor: Actor,
    service: Service,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    tutor_id: str | None = None,
    room_id: str | None = None,
    lesson_status: Annotated[LessonStatus | None, Query(alias="status")] = None,
) -> list[LessonResponse]:
    return schedule(
        actor,
        service,
        date_from,
        date_to,
        tutor_id,
        room_id,
        lesson_status,
    )


@router.get("/tutors/{tutor_id}/schedule", response_model=list[LessonResponse])
def get_tutor_schedule(
    tutor_id: str,
    actor: Actor,
    service: Service,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> list[LessonResponse]:
    return schedule(actor, service, date_from, date_to, tutor_id)


@router.get("/lookups", response_model=LookupResponse)
def get_lookups(actor: Actor, service: Service) -> LookupResponse:
    values = service.get_lookups(actor)
    return LookupResponse(
        tutors=[TutorLookup(**item) for item in values["tutors"]],
        students=[StudentResponse(**item) for item in values["students"]],
        rooms=[RoomResponse(**item) for item in values["rooms"]],
    )
