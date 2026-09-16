"""Preview-first import of the supplied CSV evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bright_path.domain.models import Lesson, LessonStatus, Room, Student, Tutor
from bright_path.storage.database import connect_database, initialize_database

BANGKOK_TIMEZONE = ZoneInfo("Asia/Bangkok")

TUTOR_CSV_FIELDS = ("tutor_id", "tutor_name", "subject", "phone")
LESSON_CSV_FIELDS = (
    "lesson_id",
    "date",
    "start_time",
    "duration_min",
    "student",
    "tutor_id",
    "room",
    "status",
    "cancelled_at",
    "note",
)

TUTOR_FIELD_DESTINATIONS = {
    "tutor_id": "Tutor.id",
    "tutor_name": "Tutor.name",
    "subject": "Tutor.subject",
    "phone": "Tutor.phone",
}

LESSON_FIELD_DESTINATIONS = {
    "lesson_id": "Lesson.id",
    "date": "Lesson.starts_at.date",
    "start_time": "Lesson.starts_at.time",
    "duration_min": "Lesson.duration_minutes",
    "student": "Student.name and lesson participant",
    "tutor_id": "Lesson.tutor",
    "room": "Room.id and Lesson.room",
    "status": "Lesson.status",
    "cancelled_at": "Lesson.cancelled_at",
    "note": "Lesson.note",
}


class ImportValidationError(ValueError):
    def __init__(self, issues: list[str] | tuple[str, ...]) -> None:
        self.issues = tuple(issues)
        super().__init__("Import preview failed:\n- " + "\n- ".join(self.issues))


class ImportStateError(RuntimeError):
    """Raised when a different source is applied to an already seeded database."""


@dataclass(frozen=True, slots=True)
class SourceRow:
    row_number: int
    values: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, str]:
        return dict(self.values)


@dataclass(frozen=True, slots=True)
class SeedPreview:
    tutors: tuple[Tutor, ...]
    students: tuple[Student, ...]
    rooms: tuple[Room, ...]
    lessons: tuple[Lesson, ...]
    raw_tutor_rows: tuple[SourceRow, ...]
    raw_lesson_rows: tuple[SourceRow, ...]
    lesson_mappings: tuple[tuple[str, str], ...]
    tutors_sha256: str
    lessons_sha256: str
    resolutions_sha256: str
    import_signature: str

    @property
    def participant_count(self) -> int:
        return sum(len(lesson.students) for lesson in self.lessons)

    def summary(self) -> dict[str, int | str]:
        return {
            "tutors": len(self.tutors),
            "students": len(self.students),
            "rooms": len(self.rooms),
            "raw_lesson_rows": len(self.raw_lesson_rows),
            "lessons": len(self.lessons),
            "lesson_participants": self.participant_count,
            "import_signature": self.import_signature,
        }


@dataclass(frozen=True, slots=True)
class SeedResult:
    applied: bool
    import_id: int
    preview: SeedPreview

    def summary(self) -> dict[str, bool | int | str]:
        return {
            "applied": self.applied,
            "import_id": self.import_id,
            **self.preview.summary(),
        }


@dataclass(frozen=True, slots=True)
class _ParsedLessonRow:
    id: str
    starts_at: datetime
    duration_minutes: int
    student: Student
    tutor: Tutor
    room: Room
    status: LessonStatus
    cancelled_at: datetime | None
    note: str | None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(
    path: Path,
    expected_fields: tuple[str, ...],
    destinations: dict[str, str],
) -> tuple[SourceRow, ...]:
    if not path.is_file():
        raise ImportValidationError([f"Missing source file: {path.name}"])

    with path.open("r", encoding="utf-8", newline="") as source_file:
        reader = csv.DictReader(source_file)
        actual_fields = tuple(reader.fieldnames or ())
        issues: list[str] = []
        if actual_fields != expected_fields:
            issues.append(
                f"{path.name} columns must be {list(expected_fields)}, got {list(actual_fields)}"
            )
        unmapped = [field for field in actual_fields if field not in destinations]
        if unmapped:
            issues.append(f"{path.name} has columns without destinations: {unmapped}")
        if issues:
            raise ImportValidationError(issues)

        rows: list[SourceRow] = []
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(row[field] is None for field in expected_fields):
                raise ImportValidationError([f"{path.name} row {row_number} is malformed"])
            rows.append(
                SourceRow(
                    row_number=row_number,
                    values=tuple((field, row[field]) for field in expected_fields),
                )
            )
    return tuple(rows)


def _parse_tutors(rows: tuple[SourceRow, ...]) -> tuple[Tutor, ...]:
    tutors: list[Tutor] = []
    seen_ids: set[str] = set()
    issues: list[str] = []
    for row in rows:
        values = row.as_dict()
        tutor_id = values["tutor_id"]
        if tutor_id in seen_ids:
            issues.append(f"tutors.csv row {row.row_number} has duplicate tutor_id {tutor_id}")
            continue
        seen_ids.add(tutor_id)
        try:
            tutors.append(
                Tutor(
                    id=tutor_id,
                    name=values["tutor_name"],
                    subject=values["subject"],
                    phone=values["phone"],
                )
            )
        except ValueError as error:
            issues.append(f"tutors.csv row {row.row_number}: {error}")
    if issues:
        raise ImportValidationError(issues)
    return tuple(tutors)


def _student_id(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12].upper()
    return f"ST-{digest}"


def _parse_local_start(date_value: str, time_value: str) -> datetime:
    parsed = datetime.strptime(f"{date_value} {time_value}", "%Y-%m-%d %H:%M")
    if parsed.strftime("%Y-%m-%d") != date_value or parsed.strftime("%H:%M") != time_value:
        raise ValueError("date or time is not in canonical source format")
    return parsed.replace(tzinfo=BANGKOK_TIMEZONE)


def _parse_cancelled_at(value: str) -> datetime | None:
    if value == "":
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("cancelled_at must include a timezone offset")
    return parsed


def _parse_lessons(
    rows: tuple[SourceRow, ...],
    tutors: tuple[Tutor, ...],
) -> tuple[tuple[_ParsedLessonRow, ...], tuple[Student, ...], tuple[Room, ...]]:
    tutors_by_id = {tutor.id: tutor for tutor in tutors}
    students_by_name: dict[str, Student] = {}
    rooms_by_id: dict[str, Room] = {}
    lessons: list[_ParsedLessonRow] = []
    lesson_ids: set[str] = set()
    issues: list[str] = []

    for row in rows:
        values = row.as_dict()
        row_issues: list[str] = []
        lesson_id = values["lesson_id"]
        if not lesson_id:
            row_issues.append("lesson_id must not be blank")
        elif lesson_id in lesson_ids:
            row_issues.append(f"duplicate lesson_id {lesson_id}")
        else:
            lesson_ids.add(lesson_id)

        try:
            starts_at = _parse_local_start(values["date"], values["start_time"])
        except ValueError:
            starts_at = None
            row_issues.append("date/start_time must use YYYY-MM-DD and HH:MM")

        try:
            duration_minutes = int(values["duration_min"])
            if duration_minutes <= 0:
                raise ValueError
        except ValueError:
            duration_minutes = 0
            row_issues.append("duration_min must be a positive whole number")

        tutor = tutors_by_id.get(values["tutor_id"])
        if tutor is None:
            row_issues.append(f"unknown tutor_id {values['tutor_id']}")

        student_name = values["student"]
        if not student_name.strip():
            row_issues.append("student must not be blank")

        room_id = values["room"]
        if not room_id.strip():
            row_issues.append("room must not be blank")

        try:
            status = LessonStatus(values["status"])
        except ValueError:
            status = None
            row_issues.append(f"unsupported status {values['status']!r}")

        try:
            cancelled_at = _parse_cancelled_at(values["cancelled_at"])
        except ValueError as error:
            cancelled_at = None
            row_issues.append(str(error))

        if status is LessonStatus.CANCELLED and cancelled_at is None:
            row_issues.append("cancelled lessons require cancelled_at")
        if status is not None and status is not LessonStatus.CANCELLED and cancelled_at is not None:
            row_issues.append("only cancelled lessons may have cancelled_at")

        if row_issues:
            issues.extend(
                f"lessons_export.csv row {row.row_number}: {issue}" for issue in row_issues
            )
            continue

        student = students_by_name.setdefault(
            student_name,
            Student(id=_student_id(student_name), name=student_name),
        )
        room = rooms_by_id.setdefault(room_id, Room(id=room_id))
        lessons.append(
            _ParsedLessonRow(
                id=lesson_id,
                starts_at=starts_at,
                duration_minutes=duration_minutes,
                student=student,
                tutor=tutor,
                room=room,
                status=status,
                cancelled_at=cancelled_at,
                note=values["note"] or None,
            )
        )

    if issues:
        raise ImportValidationError(issues)
    return tuple(lessons), tuple(students_by_name.values()), tuple(rooms_by_id.values())


def _load_group_mappings(
    path: Path,
    source_lesson_ids: set[str],
) -> dict[str, str]:
    if not path.is_file():
        raise ImportValidationError([f"Missing resolution file: {path.name}"])
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise ImportValidationError([f"Invalid {path.name}: {error}"]) from error

    groups = document.get("groups") if isinstance(document, dict) else None
    if not isinstance(groups, list):
        raise ImportValidationError([f"{path.name} must contain a groups list"])

    mappings = {lesson_id: lesson_id for lesson_id in source_lesson_ids}
    resolved_members: set[str] = set()
    issues: list[str] = []
    for index, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            issues.append(f"group {index} must be an object")
            continue
        canonical_id = group.get("canonical_lesson_id")
        member_ids = group.get("source_lesson_ids")
        if not isinstance(canonical_id, str) or not isinstance(member_ids, list):
            issues.append(f"group {index} has invalid identifiers")
            continue
        if len(member_ids) < 2 or any(not isinstance(item, str) for item in member_ids):
            issues.append(f"group {index} must contain at least two source lesson IDs")
            continue
        if canonical_id not in member_ids:
            issues.append(f"group {index} canonical lesson must be one of its source lessons")
        for member_id in member_ids:
            if member_id not in source_lesson_ids:
                issues.append(f"group {index} references unknown lesson {member_id}")
            if member_id in resolved_members:
                issues.append(f"lesson {member_id} appears in more than one group")
            resolved_members.add(member_id)
            mappings[member_id] = canonical_id
    if issues:
        raise ImportValidationError(issues)
    return mappings


def _same_lesson_assignment(left: _ParsedLessonRow, right: _ParsedLessonRow) -> bool:
    return (
        left.starts_at,
        left.duration_minutes,
        left.tutor.id,
        left.room.id,
        left.status,
        left.cancelled_at,
        left.note,
    ) == (
        right.starts_at,
        right.duration_minutes,
        right.tutor.id,
        right.room.id,
        right.status,
        right.cancelled_at,
        right.note,
    )


def _build_operational_lessons(
    parsed_rows: tuple[_ParsedLessonRow, ...],
    mappings: dict[str, str],
) -> tuple[Lesson, ...]:
    rows_by_id = {row.id: row for row in parsed_rows}
    students_by_lesson: dict[str, list[Student]] = {}
    canonical_order: list[str] = []
    issues: list[str] = []

    for row in parsed_rows:
        canonical_id = mappings[row.id]
        if canonical_id not in rows_by_id:
            issues.append(f"canonical lesson {canonical_id} does not exist")
            continue
        canonical_row = rows_by_id[canonical_id]
        if not _same_lesson_assignment(canonical_row, row):
            issues.append(
                f"grouped lesson {row.id} does not match canonical lesson {canonical_id}"
            )
        if canonical_id not in students_by_lesson:
            students_by_lesson[canonical_id] = []
            canonical_order.append(canonical_id)
        students_by_lesson[canonical_id].append(row.student)

    if issues:
        raise ImportValidationError(issues)

    lessons: list[Lesson] = []
    for canonical_id in canonical_order:
        source = rows_by_id[canonical_id]
        try:
            lessons.append(
                Lesson(
                    id=canonical_id,
                    starts_at=source.starts_at,
                    duration_minutes=source.duration_minutes,
                    tutor=source.tutor,
                    room=source.room,
                    students=tuple(students_by_lesson[canonical_id]),
                    status=source.status,
                    cancelled_at=source.cancelled_at,
                    note=source.note,
                )
            )
        except ValueError as error:
            issues.append(f"lesson {canonical_id}: {error}")
    if issues:
        raise ImportValidationError(issues)
    return tuple(lessons)


def preview_source(source_directory: Path) -> SeedPreview:
    tutors_path = source_directory / "tutors.csv"
    lessons_path = source_directory / "lessons_export.csv"
    resolutions_path = source_directory / "group_resolutions.json"

    raw_tutors = _read_csv(tutors_path, TUTOR_CSV_FIELDS, TUTOR_FIELD_DESTINATIONS)
    raw_lessons = _read_csv(lessons_path, LESSON_CSV_FIELDS, LESSON_FIELD_DESTINATIONS)
    tutors = _parse_tutors(raw_tutors)
    parsed_lessons, students, rooms = _parse_lessons(raw_lessons, tutors)
    mappings = _load_group_mappings(
        resolutions_path,
        {lesson.id for lesson in parsed_lessons},
    )
    lessons = _build_operational_lessons(parsed_lessons, mappings)

    tutors_sha256 = _sha256(tutors_path)
    lessons_sha256 = _sha256(lessons_path)
    resolutions_sha256 = _sha256(resolutions_path)
    signature_material = ":".join(
        (tutors_sha256, lessons_sha256, resolutions_sha256)
    ).encode("ascii")
    import_signature = hashlib.sha256(signature_material).hexdigest()

    return SeedPreview(
        tutors=tutors,
        students=students,
        rooms=rooms,
        lessons=lessons,
        raw_tutor_rows=raw_tutors,
        raw_lesson_rows=raw_lessons,
        lesson_mappings=tuple((row.id, mappings[row.id]) for row in parsed_lessons),
        tutors_sha256=tutors_sha256,
        lessons_sha256=lessons_sha256,
        resolutions_sha256=resolutions_sha256,
        import_signature=import_signature,
    )


def _insert_preview(connection: sqlite3.Connection, preview: SeedPreview) -> int:
    imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cursor = connection.execute(
        """
        INSERT INTO source_imports (
            import_signature, tutors_sha256, lessons_sha256, resolutions_sha256, imported_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            preview.import_signature,
            preview.tutors_sha256,
            preview.lessons_sha256,
            preview.resolutions_sha256,
            imported_at,
        ),
    )
    import_id = int(cursor.lastrowid)

    connection.executemany(
        "INSERT INTO tutors (id, name, subject, phone) VALUES (?, ?, ?, ?)",
        ((tutor.id, tutor.name, tutor.subject, tutor.phone) for tutor in preview.tutors),
    )
    connection.executemany(
        "INSERT INTO students (id, name) VALUES (?, ?)",
        ((student.id, student.name) for student in preview.students),
    )
    connection.executemany(
        "INSERT INTO rooms (id) VALUES (?)",
        ((room.id,) for room in preview.rooms),
    )
    connection.executemany(
        """
        INSERT INTO lessons (
            id, starts_at, duration_minutes, tutor_id, room_id,
            status, cancelled_at, note, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                lesson.id,
                lesson.starts_at.isoformat(timespec="seconds"),
                lesson.duration_minutes,
                lesson.tutor.id,
                lesson.room.id,
                lesson.status.value,
                (
                    lesson.cancelled_at.isoformat(timespec="seconds")
                    if lesson.cancelled_at is not None
                    else None
                ),
                lesson.note,
                lesson.version,
            )
            for lesson in preview.lessons
        ),
    )
    connection.executemany(
        """
        INSERT INTO lesson_participants (lesson_id, student_id, position)
        VALUES (?, ?, ?)
        """,
        (
            (lesson.id, student.id, position)
            for lesson in preview.lessons
            for position, student in enumerate(lesson.students, start=1)
        ),
    )
    connection.executemany(
        """
        INSERT INTO raw_tutor_rows (
            import_id, row_number, tutor_id, tutor_name, subject, phone
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                import_id,
                row.row_number,
                row.as_dict()["tutor_id"],
                row.as_dict()["tutor_name"],
                row.as_dict()["subject"],
                row.as_dict()["phone"],
            )
            for row in preview.raw_tutor_rows
        ),
    )
    connection.executemany(
        """
        INSERT INTO raw_lesson_rows (
            import_id, row_number, lesson_id, date, start_time, duration_min,
            student, tutor_id, room, status, cancelled_at, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                import_id,
                row.row_number,
                *(row.as_dict()[field] for field in LESSON_CSV_FIELDS),
            )
            for row in preview.raw_lesson_rows
        ),
    )
    connection.executemany(
        """
        INSERT INTO raw_lesson_mappings (
            import_id, raw_lesson_id, operational_lesson_id
        ) VALUES (?, ?, ?)
        """,
        ((import_id, raw_id, operational_id) for raw_id, operational_id in preview.lesson_mappings),
    )
    return import_id


def apply_preview(database_path: Path, preview: SeedPreview) -> SeedResult:
    connection = connect_database(database_path)
    try:
        initialize_database(connection)
        existing = connection.execute(
            "SELECT id FROM source_imports WHERE import_signature = ?",
            (preview.import_signature,),
        ).fetchone()
        if existing is not None:
            return SeedResult(applied=False, import_id=int(existing["id"]), preview=preview)

        other_import = connection.execute("SELECT id FROM source_imports LIMIT 1").fetchone()
        if other_import is not None:
            raise ImportStateError("database already contains a different source import")

        connection.execute("BEGIN IMMEDIATE")
        try:
            import_id = _insert_preview(connection, preview)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return SeedResult(applied=True, import_id=import_id, preview=preview)
    finally:
        connection.close()


def import_source(database_path: Path, source_directory: Path) -> SeedResult:
    preview = preview_source(source_directory)
    return apply_preview(database_path, preview)
