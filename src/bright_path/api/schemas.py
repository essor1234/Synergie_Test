"""Public API request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from bright_path.domain.models import LessonStatus


class TutorSummary(BaseModel):
    id: str
    name: str
    subject: str


class TutorLookup(TutorSummary):
    phone: str


class StudentResponse(BaseModel):
    id: str
    name: str


class RoomResponse(BaseModel):
    id: str


class LessonResponse(BaseModel):
    id: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    tutor: TutorSummary
    room: RoomResponse
    students: list[StudentResponse]
    status: LessonStatus
    cancelled_at: datetime | None
    deleted_at: datetime | None
    note: str | None
    version: int


class LessonFields(BaseModel):
    starts_at: datetime
    duration_minutes: int
    tutor_id: str
    room_id: str
    student_ids: list[str] = Field(min_length=1, max_length=2)
    status: LessonStatus = LessonStatus.BOOKED
    cancelled_at: datetime | None = None
    note: str | None = None


class LessonCreateRequest(LessonFields):
    reason: str = Field(min_length=1)


class LessonUpdateRequest(LessonFields):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1)


class RevisionResponse(BaseModel):
    lesson_id: str
    before: dict[str, object] | None
    after: dict[str, object]
    changed_at: datetime
    changed_by: str
    reason: str


class LookupResponse(BaseModel):
    tutors: list[TutorLookup]
    students: list[StudentResponse]
    rooms: list[RoomResponse]
