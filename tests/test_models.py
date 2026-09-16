from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from bright_path.domain.models import Lesson, LessonStatus, Room, Student, Tutor

BANGKOK = ZoneInfo("Asia/Bangkok")


def make_lesson(**overrides: object) -> Lesson:
    values: dict[str, object] = {
        "id": "L100",
        "starts_at": datetime(2026, 3, 10, 9, 0, tzinfo=BANGKOK),
        "duration_minutes": 60,
        "tutor": Tutor("T1", "Ngoc Anh", "Maths", "090xxx1122"),
        "room": Room("R1"),
        "students": (Student("S1", "Le Minh Chau"),),
        "status": LessonStatus.BOOKED,
    }
    values.update(overrides)
    return Lesson(**values)  # type: ignore[arg-type]


def test_lesson_reports_end_and_increments_version_when_rescheduled() -> None:
    lesson = make_lesson()
    new_start = datetime(2026, 3, 10, 10, 30, tzinfo=BANGKOK)

    assert lesson.ends_at() == datetime(2026, 3, 10, 10, 0, tzinfo=BANGKOK)

    lesson.reschedule(starts_at=new_start, room=Room("R2"))

    assert lesson.starts_at == new_start
    assert lesson.room.id == "R2"
    assert lesson.version == 2


def test_lesson_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_lesson(starts_at=datetime(2026, 3, 10, 9, 0))


@pytest.mark.parametrize(
    ("status", "cancelled_at", "message"),
    [
        (LessonStatus.CANCELLED, None, "require cancelled_at"),
        (
            LessonStatus.BOOKED,
            datetime(2026, 3, 10, 8, 0, tzinfo=BANGKOK),
            "only cancelled lessons",
        ),
    ],
)
def test_lesson_enforces_cancellation_consistency(
    status: LessonStatus,
    cancelled_at: datetime | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        make_lesson(status=status, cancelled_at=cancelled_at)


def test_lesson_accepts_one_or_two_distinct_students() -> None:
    paired = make_lesson(
        students=(Student("S1", "First"), Student("S2", "Second"))
    )

    assert len(paired.students) == 2

    with pytest.raises(ValueError, match="one or two"):
        make_lesson(students=())
