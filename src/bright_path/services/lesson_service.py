"""Role-aware lesson queries and transactional mutations."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from bright_path.domain.models import (
    Lesson,
    LessonRevision,
    LessonStatus,
    Room,
    Student,
    Tutor,
    User,
    UserRole,
)
from bright_path.storage.database import connect_database, initialize_database

BANGKOK_TIMEZONE = ZoneInfo("Asia/Bangkok")


class LessonServiceError(RuntimeError):
    """Base class for expected lesson workflow failures."""


class LessonNotFoundError(LessonServiceError):
    pass


class PermissionDeniedError(LessonServiceError):
    pass


class StaleLessonError(LessonServiceError):
    pass


class LessonValidationError(LessonServiceError):
    def __init__(self, issues: list[str] | tuple[str, ...]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


@dataclass(frozen=True, slots=True)
class LessonDraft:
    starts_at: datetime
    duration_minutes: int
    tutor_id: str
    room_id: str
    student_ids: tuple[str, ...]
    status: LessonStatus
    cancelled_at: datetime | None = None
    note: str | None = None


def _current_time() -> datetime:
    return datetime.now(BANGKOK_TIMEZONE)


def _new_lesson_id() -> str:
    return f"L-{uuid.uuid4().hex[:12].upper()}"


class LessonService:
    def __init__(
        self,
        database_path: Path,
        *,
        now: Callable[[], datetime] = _current_time,
        make_lesson_id: Callable[[], str] = _new_lesson_id,
    ) -> None:
        self.database_path = database_path
        self._now = now
        self._make_lesson_id = make_lesson_id

    def list_lessons(
        self,
        actor: User,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        tutor_id: str | None = None,
        room_id: str | None = None,
        status: LessonStatus | None = None,
        include_deleted: bool = False,
    ) -> tuple[Lesson, ...]:
        if actor.role is UserRole.TUTOR:
            if tutor_id is not None and tutor_id != actor.tutor_id:
                raise PermissionDeniedError("Tutors can view only their own schedule")
            tutor_id = actor.tutor_id
            include_deleted = False

        connection = self._connect()
        try:
            clauses: list[str] = []
            parameters: list[str] = []
            if not include_deleted:
                clauses.append("deleted_at IS NULL")
            if date_from is not None:
                clauses.append("substr(starts_at, 1, 10) >= ?")
                parameters.append(date_from.isoformat())
            if date_to is not None:
                clauses.append("substr(starts_at, 1, 10) <= ?")
                parameters.append(date_to.isoformat())
            if tutor_id is not None:
                clauses.append("tutor_id = ?")
                parameters.append(tutor_id)
            if room_id is not None:
                clauses.append("room_id = ?")
                parameters.append(room_id)
            if status is not None:
                clauses.append("status = ?")
                parameters.append(status.value)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = connection.execute(
                f"SELECT id FROM lessons {where} ORDER BY starts_at, id",
                parameters,
            ).fetchall()
            return tuple(self._load_lesson(connection, row["id"]) for row in rows)
        finally:
            connection.close()

    def get_lesson(self, actor: User, lesson_id: str) -> Lesson:
        connection = self._connect()
        try:
            lesson = self._load_lesson(connection, lesson_id)
            self._check_read_access(actor, lesson)
            return lesson
        finally:
            connection.close()

    def create_lesson(self, actor: User, draft: LessonDraft, reason: str) -> Lesson:
        self._require_receptionist(actor)
        reason = self._require_reason(reason)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                lesson = self._build_lesson(connection, self._make_lesson_id(), draft)
                self._validate_schedule_change(connection, lesson)
                self._insert_lesson(connection, lesson)
                self._insert_revision(
                    connection,
                    lesson_id=lesson.id,
                    before_state="null",
                    after_state=self._state_json(lesson),
                    actor=actor,
                    reason=reason,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            return lesson
        finally:
            connection.close()

    def update_lesson(
        self,
        actor: User,
        lesson_id: str,
        draft: LessonDraft,
        *,
        expected_version: int,
        reason: str,
    ) -> Lesson:
        self._require_receptionist(actor)
        reason = self._require_reason(reason)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = self._load_lesson(connection, lesson_id)
                if current.deleted_at is not None:
                    raise LessonNotFoundError(f"Lesson {lesson_id} is deleted")
                if current.version != expected_version:
                    raise StaleLessonError(
                        f"Lesson {lesson_id} is version {current.version}, not {expected_version}"
                    )
                updated = self._build_lesson(
                    connection,
                    lesson_id,
                    draft,
                    version=current.version + 1,
                )
                if self._schedule_signature(current) != self._schedule_signature(updated):
                    self._validate_schedule_change(
                        connection,
                        updated,
                        exclude_lesson_id=lesson_id,
                    )
                before_state = self._state_json(current)
                cursor = connection.execute(
                    """
                    UPDATE lessons
                    SET starts_at = ?, duration_minutes = ?, tutor_id = ?, room_id = ?,
                        status = ?, cancelled_at = ?, note = ?, version = ?
                    WHERE id = ? AND version = ? AND deleted_at IS NULL
                    """,
                    (
                        updated.starts_at.isoformat(timespec="seconds"),
                        updated.duration_minutes,
                        updated.tutor.id,
                        updated.room.id,
                        updated.status.value,
                        self._datetime_text(updated.cancelled_at),
                        updated.note,
                        updated.version,
                        lesson_id,
                        expected_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise StaleLessonError(f"Lesson {lesson_id} changed while it was being saved")
                connection.execute(
                    "DELETE FROM lesson_participants WHERE lesson_id = ?",
                    (lesson_id,),
                )
                self._insert_participants(connection, updated)
                self._insert_revision(
                    connection,
                    lesson_id=lesson_id,
                    before_state=before_state,
                    after_state=self._state_json(updated),
                    actor=actor,
                    reason=reason,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            return updated
        finally:
            connection.close()

    def delete_lesson(
        self,
        actor: User,
        lesson_id: str,
        *,
        expected_version: int,
        reason: str,
    ) -> Lesson:
        self._require_receptionist(actor)
        reason = self._require_reason(reason)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = self._load_lesson(connection, lesson_id)
                if current.deleted_at is not None:
                    raise LessonNotFoundError(f"Lesson {lesson_id} is already deleted")
                if current.version != expected_version:
                    raise StaleLessonError(
                        f"Lesson {lesson_id} is version {current.version}, not {expected_version}"
                    )
                deleted_at = self._aware_now()
                cursor = connection.execute(
                    """
                    UPDATE lessons
                    SET deleted_at = ?, version = version + 1
                    WHERE id = ? AND version = ? AND deleted_at IS NULL
                    """,
                    (deleted_at.isoformat(timespec="seconds"), lesson_id, expected_version),
                )
                if cursor.rowcount != 1:
                    raise StaleLessonError(f"Lesson {lesson_id} changed while it was being deleted")
                deleted = self._load_lesson(connection, lesson_id)
                self._insert_revision(
                    connection,
                    lesson_id=lesson_id,
                    before_state=self._state_json(current),
                    after_state=self._state_json(deleted),
                    actor=actor,
                    reason=reason,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            return deleted
        finally:
            connection.close()

    def get_history(self, actor: User, lesson_id: str) -> tuple[LessonRevision, ...]:
        connection = self._connect()
        try:
            lesson = self._load_lesson(connection, lesson_id)
            self._check_read_access(actor, lesson)
            rows = connection.execute(
                """
                SELECT before_state, after_state, changed_at, changed_by, reason
                FROM lesson_revisions WHERE lesson_id = ? ORDER BY id
                """,
                (lesson_id,),
            ).fetchall()
            return tuple(
                LessonRevision(
                    lesson_id=lesson_id,
                    before=row["before_state"],
                    after=row["after_state"],
                    changed_at=datetime.fromisoformat(row["changed_at"]),
                    changed_by=row["changed_by"],
                    reason=row["reason"],
                )
                for row in rows
            )
        finally:
            connection.close()

    def get_lookups(self, actor: User) -> dict[str, list[dict[str, str]]]:
        connection = self._connect()
        try:
            if actor.role in {UserRole.OWNER, UserRole.RECEPTIONIST}:
                tutor_rows = connection.execute(
                    "SELECT id, name, subject, phone FROM tutors ORDER BY name"
                ).fetchall()
                student_rows = connection.execute(
                    "SELECT id, name FROM students ORDER BY name"
                ).fetchall()
                room_rows = connection.execute("SELECT id FROM rooms ORDER BY id").fetchall()
            else:
                tutor_rows = connection.execute(
                    "SELECT id, name, subject, phone FROM tutors WHERE id = ?",
                    (actor.tutor_id,),
                ).fetchall()
                student_rows = connection.execute(
                    """
                    SELECT DISTINCT s.id, s.name
                    FROM students s
                    JOIN lesson_participants lp ON lp.student_id = s.id
                    JOIN lessons l ON l.id = lp.lesson_id
                    WHERE l.tutor_id = ? AND l.deleted_at IS NULL
                    ORDER BY s.name
                    """,
                    (actor.tutor_id,),
                ).fetchall()
                room_rows = connection.execute(
                    """
                    SELECT DISTINCT r.id
                    FROM rooms r JOIN lessons l ON l.room_id = r.id
                    WHERE l.tutor_id = ? AND l.deleted_at IS NULL
                    ORDER BY r.id
                    """,
                    (actor.tutor_id,),
                ).fetchall()
            return {
                "tutors": [dict(row) for row in tutor_rows],
                "students": [dict(row) for row in student_rows],
                "rooms": [dict(row) for row in room_rows],
            }
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = connect_database(self.database_path)
        initialize_database(connection)
        return connection

    def _load_lesson(self, connection: sqlite3.Connection, lesson_id: str) -> Lesson:
        row = connection.execute(
            """
            SELECT l.*, t.name AS tutor_name, t.subject, t.phone
            FROM lessons l JOIN tutors t ON t.id = l.tutor_id
            WHERE l.id = ?
            """,
            (lesson_id,),
        ).fetchone()
        if row is None:
            raise LessonNotFoundError(f"Lesson {lesson_id} was not found")
        student_rows = connection.execute(
            """
            SELECT s.id, s.name
            FROM students s JOIN lesson_participants lp ON lp.student_id = s.id
            WHERE lp.lesson_id = ? ORDER BY lp.position
            """,
            (lesson_id,),
        ).fetchall()
        return Lesson(
            id=row["id"],
            starts_at=datetime.fromisoformat(row["starts_at"]),
            duration_minutes=row["duration_minutes"],
            tutor=Tutor(row["tutor_id"], row["tutor_name"], row["subject"], row["phone"]),
            room=Room(row["room_id"]),
            students=tuple(Student(student["id"], student["name"]) for student in student_rows),
            status=LessonStatus(row["status"]),
            cancelled_at=self._parse_optional_datetime(row["cancelled_at"]),
            deleted_at=self._parse_optional_datetime(row["deleted_at"]),
            note=row["note"],
            version=row["version"],
        )

    def _build_lesson(
        self,
        connection: sqlite3.Connection,
        lesson_id: str,
        draft: LessonDraft,
        *,
        version: int = 1,
    ) -> Lesson:
        issues: list[str] = []
        if draft.duration_minutes not in {60, 90}:
            issues.append("Duration must be 60 or 90 minutes")
        if draft.starts_at.tzinfo is None or draft.starts_at.utcoffset() is None:
            issues.append("Start time must include a timezone")
        elif draft.starts_at.astimezone(BANGKOK_TIMEZONE).weekday() == 0:
            issues.append("The center is closed on Monday")
        if not 1 <= len(draft.student_ids) <= 2:
            issues.append("Select one or two students")
        if len(set(draft.student_ids)) != len(draft.student_ids):
            issues.append("A student can appear only once in a lesson")

        tutor_row = connection.execute(
            "SELECT id, name, subject, phone FROM tutors WHERE id = ?",
            (draft.tutor_id,),
        ).fetchone()
        if tutor_row is None:
            issues.append(f"Tutor {draft.tutor_id} does not exist")
        room_row = connection.execute(
            "SELECT id FROM rooms WHERE id = ?",
            (draft.room_id,),
        ).fetchone()
        if room_row is None:
            issues.append(f"Room {draft.room_id} does not exist")

        students: list[Student] = []
        for student_id in draft.student_ids:
            row = connection.execute(
                "SELECT id, name FROM students WHERE id = ?",
                (student_id,),
            ).fetchone()
            if row is None:
                issues.append(f"Student {student_id} does not exist")
            else:
                students.append(Student(row["id"], row["name"]))
        if issues:
            raise LessonValidationError(issues)

        try:
            return Lesson(
                id=lesson_id,
                starts_at=draft.starts_at.astimezone(BANGKOK_TIMEZONE),
                duration_minutes=draft.duration_minutes,
                tutor=Tutor(
                    tutor_row["id"],
                    tutor_row["name"],
                    tutor_row["subject"],
                    tutor_row["phone"],
                ),
                room=Room(room_row["id"]),
                students=tuple(students),
                status=draft.status,
                cancelled_at=draft.cancelled_at,
                note=draft.note,
                version=version,
            )
        except ValueError as error:
            raise LessonValidationError([str(error)]) from error

    def _validate_schedule_change(
        self,
        connection: sqlite3.Connection,
        lesson: Lesson,
        *,
        exclude_lesson_id: str | None = None,
    ) -> None:
        if lesson.status is LessonStatus.CANCELLED or lesson.deleted_at is not None:
            return
        parameters: list[str] = [
            lesson.tutor.id,
            lesson.starts_at.date().isoformat(),
        ]
        exclude_clause = ""
        if exclude_lesson_id is not None:
            exclude_clause = "AND id <> ?"
            parameters.append(exclude_lesson_id)
        same_day = connection.execute(
            f"""
            SELECT COUNT(*) AS total FROM lessons
            WHERE tutor_id = ? AND substr(starts_at, 1, 10) = ?
              AND deleted_at IS NULL AND status <> 'cancelled' {exclude_clause}
            """,
            parameters,
        ).fetchone()["total"]
        issues: list[str] = []
        if same_day >= 6:
            issues.append(f"Tutor {lesson.tutor.id} already has six lessons that day")

        rows = connection.execute(
            """
            SELECT id FROM lessons
            WHERE deleted_at IS NULL AND status <> 'cancelled'
              AND (? IS NULL OR id <> ?)
            """,
            (exclude_lesson_id, exclude_lesson_id),
        ).fetchall()
        lesson_student_ids = {student.id for student in lesson.students}
        for row in rows:
            other = self._load_lesson(connection, row["id"])
            if not (lesson.starts_at < other.ends_at() and other.starts_at < lesson.ends_at()):
                continue
            if lesson.tutor.id == other.tutor.id:
                issues.append(f"Tutor {lesson.tutor.id} is already booked for lesson {other.id}")
            if lesson.room.id == other.room.id:
                issues.append(f"Room {lesson.room.id} is already used by lesson {other.id}")
            shared_students = lesson_student_ids & {student.id for student in other.students}
            if shared_students:
                names = ", ".join(
                    student.name for student in lesson.students if student.id in shared_students
                )
                issues.append(f"{names} is already booked for lesson {other.id}")
        if issues:
            raise LessonValidationError(issues)

    def _insert_lesson(self, connection: sqlite3.Connection, lesson: Lesson) -> None:
        connection.execute(
            """
            INSERT INTO lessons (
                id, starts_at, duration_minutes, tutor_id, room_id,
                status, cancelled_at, deleted_at, note, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lesson.id,
                lesson.starts_at.isoformat(timespec="seconds"),
                lesson.duration_minutes,
                lesson.tutor.id,
                lesson.room.id,
                lesson.status.value,
                self._datetime_text(lesson.cancelled_at),
                self._datetime_text(lesson.deleted_at),
                lesson.note,
                lesson.version,
            ),
        )
        self._insert_participants(connection, lesson)

    @staticmethod
    def _insert_participants(connection: sqlite3.Connection, lesson: Lesson) -> None:
        connection.executemany(
            """
            INSERT INTO lesson_participants (lesson_id, student_id, position)
            VALUES (?, ?, ?)
            """,
            (
                (lesson.id, student.id, position)
                for position, student in enumerate(lesson.students, start=1)
            ),
        )

    def _insert_revision(
        self,
        connection: sqlite3.Connection,
        *,
        lesson_id: str,
        before_state: str,
        after_state: str,
        actor: User,
        reason: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO lesson_revisions (
                lesson_id, before_state, after_state, changed_at, changed_by, reason
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                lesson_id,
                before_state,
                after_state,
                self._aware_now().isoformat(timespec="seconds"),
                actor.id,
                reason,
            ),
        )

    @staticmethod
    def _state_json(lesson: Lesson) -> str:
        return json.dumps(
            {
                "id": lesson.id,
                "starts_at": lesson.starts_at.isoformat(timespec="seconds"),
                "duration_minutes": lesson.duration_minutes,
                "tutor_id": lesson.tutor.id,
                "room_id": lesson.room.id,
                "student_ids": [student.id for student in lesson.students],
                "status": lesson.status.value,
                "cancelled_at": LessonService._datetime_text(lesson.cancelled_at),
                "deleted_at": LessonService._datetime_text(lesson.deleted_at),
                "note": lesson.note,
                "version": lesson.version,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _schedule_signature(lesson: Lesson) -> tuple[object, ...]:
        return (
            lesson.starts_at,
            lesson.duration_minutes,
            lesson.tutor.id,
            lesson.room.id,
            tuple(student.id for student in lesson.students),
            lesson.status is not LessonStatus.CANCELLED and lesson.deleted_at is None,
        )

    @staticmethod
    def _check_read_access(actor: User, lesson: Lesson) -> None:
        if actor.role is UserRole.TUTOR and lesson.tutor.id != actor.tutor_id:
            raise PermissionDeniedError("Tutors can view only their own lessons")

    @staticmethod
    def _require_receptionist(actor: User) -> None:
        if actor.role is not UserRole.RECEPTIONIST:
            raise PermissionDeniedError("Only receptionists can change lessons")

    @staticmethod
    def _require_reason(reason: str) -> str:
        cleaned = reason.strip()
        if not cleaned:
            raise LessonValidationError(["A change reason is required"])
        return cleaned

    def _aware_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Service time must be timezone-aware")
        return value.astimezone(BANGKOK_TIMEZONE)

    @staticmethod
    def _parse_optional_datetime(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value is not None else None

    @staticmethod
    def _datetime_text(value: datetime | None) -> str | None:
        return value.isoformat(timespec="seconds") if value is not None else None
