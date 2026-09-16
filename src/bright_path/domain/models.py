"""Plain domain models for Bright Path scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


def _require_text(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class LessonStatus(str, Enum):
    BOOKED = "booked"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


@dataclass(frozen=True, slots=True)
class User:
    id: str
    name: str
    role: str
    tutor_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, "user id")
        _require_text(self.name, "user name")
        _require_text(self.role, "user role")
        if self.tutor_id is not None:
            _require_text(self.tutor_id, "user tutor id")


@dataclass(frozen=True, slots=True)
class Tutor:
    id: str
    name: str
    subject: str
    phone: str

    def __post_init__(self) -> None:
        _require_text(self.id, "tutor id")
        _require_text(self.name, "tutor name")
        _require_text(self.subject, "tutor subject")
        _require_text(self.phone, "tutor phone")


@dataclass(frozen=True, slots=True)
class Student:
    id: str
    name: str

    def __post_init__(self) -> None:
        _require_text(self.id, "student id")
        _require_text(self.name, "student name")


@dataclass(frozen=True, slots=True)
class Room:
    id: str

    def __post_init__(self) -> None:
        _require_text(self.id, "room id")


@dataclass(slots=True)
class Lesson:
    id: str
    starts_at: datetime
    duration_minutes: int
    tutor: Tutor
    room: Room
    students: tuple[Student, ...]
    status: LessonStatus
    cancelled_at: datetime | None = None
    note: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        _require_text(self.id, "lesson id")
        _require_aware(self.starts_at, "lesson start")
        if self.duration_minutes <= 0:
            raise ValueError("lesson duration must be positive")
        if not 1 <= len(self.students) <= 2:
            raise ValueError("a lesson must have one or two students")
        if len({student.id for student in self.students}) != len(self.students):
            raise ValueError("a lesson cannot contain the same student twice")
        if not isinstance(self.status, LessonStatus):
            raise ValueError("lesson status is unsupported")
        if self.cancelled_at is not None:
            _require_aware(self.cancelled_at, "cancellation time")
        if self.status is LessonStatus.CANCELLED and self.cancelled_at is None:
            raise ValueError("cancelled lessons require cancelled_at")
        if self.status is not LessonStatus.CANCELLED and self.cancelled_at is not None:
            raise ValueError("only cancelled lessons may have cancelled_at")
        if self.note is not None and not self.note:
            raise ValueError("blank lesson notes must be represented as None")
        if self.version < 1:
            raise ValueError("lesson version must be at least 1")

    def ends_at(self) -> datetime:
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    def reschedule(
        self,
        *,
        starts_at: datetime | None = None,
        tutor: Tutor | None = None,
        room: Room | None = None,
    ) -> None:
        next_start = starts_at if starts_at is not None else self.starts_at
        _require_aware(next_start, "lesson start")
        next_tutor = tutor if tutor is not None else self.tutor
        next_room = room if room is not None else self.room
        if (next_start, next_tutor, next_room) == (self.starts_at, self.tutor, self.room):
            return
        self.starts_at = next_start
        self.tutor = next_tutor
        self.room = next_room
        self.version += 1


@dataclass(frozen=True, slots=True)
class LessonRevision:
    lesson_id: str
    before: str
    after: str
    changed_at: datetime
    changed_by: str
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.lesson_id, "revision lesson id")
        _require_text(self.before, "revision before state")
        _require_text(self.after, "revision after state")
        _require_aware(self.changed_at, "revision change time")
        _require_text(self.changed_by, "revision actor")
        _require_text(self.reason, "revision reason")
