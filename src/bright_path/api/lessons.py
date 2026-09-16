"""Role-aware lesson CRUD routes."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from bright_path.api.dependencies import get_actor, get_lesson_service
from bright_path.api.schemas import (
    LessonCreateRequest,
    LessonResponse,
    LessonUpdateRequest,
    RevisionResponse,
    RoomResponse,
    StudentResponse,
    TutorSummary,
)
from bright_path.domain.models import Lesson, LessonRevision, User
from bright_path.services.lesson_service import LessonDraft, LessonService

router = APIRouter(prefix="/api/v1/lessons", tags=["lessons"])

Actor = Annotated[User, Depends(get_actor)]
Service = Annotated[LessonService, Depends(get_lesson_service)]


def lesson_response(lesson: Lesson) -> LessonResponse:
    return LessonResponse(
        id=lesson.id,
        starts_at=lesson.starts_at,
        ends_at=lesson.ends_at(),
        duration_minutes=lesson.duration_minutes,
        tutor=TutorSummary(
            id=lesson.tutor.id,
            name=lesson.tutor.name,
            subject=lesson.tutor.subject,
        ),
        room=RoomResponse(id=lesson.room.id),
        students=[StudentResponse(id=student.id, name=student.name) for student in lesson.students],
        status=lesson.status,
        cancelled_at=lesson.cancelled_at,
        deleted_at=lesson.deleted_at,
        note=lesson.note,
        version=lesson.version,
    )


def lesson_draft(request: LessonCreateRequest | LessonUpdateRequest) -> LessonDraft:
    note = request.note.strip() if request.note and request.note.strip() else None
    return LessonDraft(
        starts_at=request.starts_at,
        duration_minutes=request.duration_minutes,
        tutor_id=request.tutor_id,
        room_id=request.room_id,
        student_ids=tuple(request.student_ids),
        status=request.status,
        cancelled_at=request.cancelled_at,
        note=note,
    )


def revision_response(revision: LessonRevision) -> RevisionResponse:
    before = json.loads(revision.before)
    after = json.loads(revision.after)
    return RevisionResponse(
        lesson_id=revision.lesson_id,
        before=before,
        after=after,
        changed_at=revision.changed_at,
        changed_by=revision.changed_by,
        reason=revision.reason,
    )


@router.get("/{lesson_id}", response_model=LessonResponse)
def get_lesson(lesson_id: str, actor: Actor, service: Service) -> LessonResponse:
    return lesson_response(service.get_lesson(actor, lesson_id))


@router.post("", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
def create_lesson(
    request: LessonCreateRequest,
    actor: Actor,
    service: Service,
) -> LessonResponse:
    return lesson_response(service.create_lesson(actor, lesson_draft(request), request.reason))


@router.patch("/{lesson_id}", response_model=LessonResponse)
def update_lesson(
    lesson_id: str,
    request: LessonUpdateRequest,
    actor: Actor,
    service: Service,
) -> LessonResponse:
    lesson = service.update_lesson(
        actor,
        lesson_id,
        lesson_draft(request),
        expected_version=request.expected_version,
        reason=request.reason,
    )
    return lesson_response(lesson)


@router.delete("/{lesson_id}", response_model=LessonResponse)
def delete_lesson(
    lesson_id: str,
    actor: Actor,
    service: Service,
    expected_version: Annotated[int, Query(ge=1)],
    reason: Annotated[str, Query(min_length=1)],
) -> LessonResponse:
    lesson = service.delete_lesson(
        actor,
        lesson_id,
        expected_version=expected_version,
        reason=reason,
    )
    return lesson_response(lesson)


@router.get("/{lesson_id}/history", response_model=list[RevisionResponse])
def get_history(
    lesson_id: str,
    actor: Actor,
    service: Service,
) -> list[RevisionResponse]:
    return [revision_response(revision) for revision in service.get_history(actor, lesson_id)]
