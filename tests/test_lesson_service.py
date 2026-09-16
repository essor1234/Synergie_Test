from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from bright_path.domain.models import Lesson, LessonStatus, User, UserRole
from bright_path.services.lesson_service import (
    LessonDraft,
    LessonService,
    LessonValidationError,
    PermissionDeniedError,
    StaleLessonError,
)
from bright_path.settings import SOURCE_DATA_DIR
from bright_path.storage.seed import import_source

BANGKOK = ZoneInfo("Asia/Bangkok")
OWNER = User("owner", "Owner", UserRole.OWNER)
RECEPTIONIST = User("reception", "Receptionist", UserRole.RECEPTIONIST)
TUTOR_T1 = User("tutor-T1", "Ngoc Anh", UserRole.TUTOR, "T1")


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "bright_path.db"
    import_source(path, SOURCE_DATA_DIR)
    return path


@pytest.fixture
def service(database_path: Path) -> LessonService:
    return LessonService(
        database_path,
        now=lambda: datetime(2026, 3, 10, 15, 0, tzinfo=BANGKOK),
        make_lesson_id=lambda: "L-NEW",
    )


def student_id(service: LessonService, name: str) -> str:
    lookups = service.get_lookups(RECEPTIONIST)
    return next(student["id"] for student in lookups["students"] if student["name"] == name)


def valid_draft(service: LessonService, **changes: object) -> LessonDraft:
    values: dict[str, object] = {
        "starts_at": datetime(2026, 3, 10, 11, 0, tzinfo=BANGKOK),
        "duration_minutes": 60,
        "tutor_id": "T2",
        "room_id": "R3",
        "student_ids": (student_id(service, "Bui An Nhien"),),
        "status": LessonStatus.BOOKED,
        "cancelled_at": None,
        "note": "Created in test",
    }
    values.update(changes)
    return LessonDraft(**values)  # type: ignore[arg-type]


def draft_from_lesson(lesson: Lesson, **changes: object) -> LessonDraft:
    values: dict[str, object] = {
        "starts_at": lesson.starts_at,
        "duration_minutes": lesson.duration_minutes,
        "tutor_id": lesson.tutor.id,
        "room_id": lesson.room.id,
        "student_ids": tuple(student.id for student in lesson.students),
        "status": lesson.status,
        "cancelled_at": lesson.cancelled_at,
        "note": lesson.note,
    }
    values.update(changes)
    return LessonDraft(**values)  # type: ignore[arg-type]


def test_receptionist_can_create_update_and_soft_delete_with_history(
    service: LessonService,
) -> None:
    created = service.create_lesson(RECEPTIONIST, valid_draft(service), "New booking")
    updated = service.update_lesson(
        RECEPTIONIST,
        created.id,
        draft_from_lesson(created, note="Family confirmed"),
        expected_version=1,
        reason="Confirm booking",
    )
    deleted = service.delete_lesson(
        RECEPTIONIST,
        created.id,
        expected_version=2,
        reason="Entered by mistake",
    )

    assert created.version == 1
    assert updated.version == 2
    assert updated.note == "Family confirmed"
    assert deleted.version == 3
    assert deleted.deleted_at == datetime(2026, 3, 10, 15, 0, tzinfo=BANGKOK)
    assert created.id not in {lesson.id for lesson in service.list_lessons(OWNER)}
    assert [revision.reason for revision in service.get_history(OWNER, created.id)] == [
        "New booking",
        "Confirm booking",
        "Entered by mistake",
    ]


def test_only_receptionist_can_mutate_lessons(service: LessonService) -> None:
    with pytest.raises(PermissionDeniedError, match="Only receptionists"):
        service.create_lesson(OWNER, valid_draft(service), "Not allowed")


def test_tutor_can_read_only_assigned_lessons(service: LessonService) -> None:
    own_lessons = service.list_lessons(TUTOR_T1)

    assert own_lessons
    assert {lesson.tutor.id for lesson in own_lessons} == {"T1"}
    assert service.get_lesson(TUTOR_T1, "L001").id == "L001"
    with pytest.raises(PermissionDeniedError, match="own lessons"):
        service.get_lesson(TUTOR_T1, "L002")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"starts_at": datetime(2026, 3, 9, 12, 0, tzinfo=BANGKOK)},
            "closed on Monday",
        ),
        ({"duration_minutes": 45}, "60 or 90"),
        (
            {
                "starts_at": datetime(2026, 3, 3, 9, 0, tzinfo=BANGKOK),
                "tutor_id": "T1",
                "room_id": "R3",
            },
            "Tutor T1 is already booked",
        ),
        (
            {
                "starts_at": datetime(2026, 3, 3, 9, 0, tzinfo=BANGKOK),
                "tutor_id": "T3",
                "room_id": "R1",
            },
            "Room R1 is already used",
        ),
        (
            {
                "starts_at": datetime(2026, 3, 3, 9, 0, tzinfo=BANGKOK),
                "tutor_id": "T3",
                "room_id": "R3",
                "student_ids": (),
            },
            "Select one or two students",
        ),
        (
            {
                "starts_at": datetime(2026, 3, 6, 22, 0, tzinfo=BANGKOK),
                "tutor_id": "T1",
            },
            "already has six lessons",
        ),
    ],
)
def test_create_rejects_invalid_schedule_changes(
    service: LessonService,
    changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(LessonValidationError, match=message):
        service.create_lesson(RECEPTIONIST, valid_draft(service, **changes), "Test validation")


def test_create_rejects_student_overlap(service: LessonService) -> None:
    le_minh_chau = student_id(service, "Le Minh Chau")
    draft = valid_draft(
        service,
        starts_at=datetime(2026, 3, 3, 9, 0, tzinfo=BANGKOK),
        tutor_id="T3",
        room_id="R3",
        student_ids=(le_minh_chau,),
    )

    with pytest.raises(LessonValidationError, match="Le Minh Chau is already booked"):
        service.create_lesson(RECEPTIONIST, draft, "Test student guardrail")


def test_back_to_back_lesson_is_allowed(service: LessonService) -> None:
    draft = valid_draft(
        service,
        starts_at=datetime(2026, 3, 3, 10, 0, tzinfo=BANGKOK),
        tutor_id="T2",
        room_id="R2",
    )

    lesson = service.create_lesson(RECEPTIONIST, draft, "Back-to-back booking")

    assert lesson.starts_at.hour == 10


def test_cancelled_lesson_frees_slot_but_no_show_does_not(service: LessonService) -> None:
    cancelled = valid_draft(
        service,
        starts_at=datetime(2026, 3, 3, 9, 0, tzinfo=BANGKOK),
        tutor_id="T1",
        room_id="R1",
        status=LessonStatus.CANCELLED,
        cancelled_at=datetime(2026, 3, 3, 8, 0, tzinfo=BANGKOK),
    )
    assert service.create_lesson(RECEPTIONIST, cancelled, "Cancelled booking").status is (
        LessonStatus.CANCELLED
    )

    no_show_overlap = valid_draft(
        service,
        starts_at=datetime(2026, 3, 5, 13, 0, tzinfo=BANGKOK),
        tutor_id="T2",
        room_id="R2",
    )
    with pytest.raises(LessonValidationError, match="already booked"):
        service.create_lesson(RECEPTIONIST, no_show_overlap, "No-show still occupies slot")


def test_stale_update_cannot_overwrite_newer_version(service: LessonService) -> None:
    lesson = service.get_lesson(OWNER, "L001")

    with pytest.raises(StaleLessonError, match="version 1"):
        service.update_lesson(
            RECEPTIONIST,
            lesson.id,
            draft_from_lesson(lesson, note="Stale edit"),
            expected_version=2,
            reason="Stale edit",
        )


def test_note_only_update_preserves_historical_schedule_evidence(
    service: LessonService,
) -> None:
    lesson = service.get_lesson(OWNER, "L033")

    updated = service.update_lesson(
        RECEPTIONIST,
        lesson.id,
        draft_from_lesson(lesson, note="Reception confirmed"),
        expected_version=lesson.version,
        reason="Add confirmation",
    )

    assert updated.note == "Reception confirmed"


def test_revision_failure_rolls_back_lesson_update(
    service: LessonService,
    database_path: Path,
) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER stop_revision BEFORE INSERT ON lesson_revisions
            BEGIN SELECT RAISE(ABORT, 'revision write failed'); END
            """
        )
    lesson = service.get_lesson(OWNER, "L001")

    with pytest.raises(sqlite3.IntegrityError, match="revision write failed"):
        service.update_lesson(
            RECEPTIONIST,
            lesson.id,
            draft_from_lesson(lesson, note="Should roll back"),
            expected_version=lesson.version,
            reason="Test rollback",
        )

    unchanged = service.get_lesson(OWNER, lesson.id)
    assert unchanged.version == lesson.version
    assert unchanged.note == lesson.note
