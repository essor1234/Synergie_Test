from __future__ import annotations

import csv
import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from bright_path.settings import SOURCE_DATA_DIR
from bright_path.storage.seed import (
    LESSON_CSV_FIELDS,
    LESSON_FIELD_DESTINATIONS,
    TUTOR_CSV_FIELDS,
    TUTOR_FIELD_DESTINATIONS,
    ImportValidationError,
    import_source,
    preview_source,
)

EXPECTED_SOURCE_HASHES = {
    "README.txt": "3c9873422219938899d3000b48b8704e528dfa9635ec3f720db2bfd725d76fea",
    "tutors.csv": "09f88090c313c0499242d694922c2240eaa2cb5889deec1e9d5eddcc2cecf352",
    "lessons_export.csv": "04d480a6f1e39f0d3deb87f3bc2f1f44079f20c6ed2697cf0c57dbadeaaa64f4",
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source_file:
        return list(csv.DictReader(source_file))


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    assert content.count(old) == 1
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def copy_source(tmp_path: Path) -> Path:
    target = tmp_path / "source"
    shutil.copytree(SOURCE_DATA_DIR, target)
    return target


def test_every_csv_column_has_an_explicit_destination() -> None:
    tutor_rows = read_csv_rows(SOURCE_DATA_DIR / "tutors.csv")
    lesson_rows = read_csv_rows(SOURCE_DATA_DIR / "lessons_export.csv")

    assert tuple(tutor_rows[0]) == TUTOR_CSV_FIELDS
    assert set(tutor_rows[0]) == set(TUTOR_FIELD_DESTINATIONS)
    assert tuple(lesson_rows[0]) == LESSON_CSV_FIELDS
    assert set(lesson_rows[0]) == set(LESSON_FIELD_DESTINATIONS)


def test_preview_preserves_every_field_and_builds_expected_operational_data() -> None:
    preview = preview_source(SOURCE_DATA_DIR)
    source_tutors = read_csv_rows(SOURCE_DATA_DIR / "tutors.csv")
    source_lessons = read_csv_rows(SOURCE_DATA_DIR / "lessons_export.csv")

    summary = preview.summary()
    summary.pop("import_signature")
    assert summary == {
        "tutors": 3,
        "students": 6,
        "rooms": 3,
        "raw_lesson_rows": 34,
        "lessons": 33,
        "lesson_participants": 34,
    }
    assert {room.id for room in preview.rooms} == {"R1", "R2", "R3"}

    tutors_by_id = {tutor.id: tutor for tutor in preview.tutors}
    for source in source_tutors:
        tutor = tutors_by_id[source["tutor_id"]]
        assert (tutor.id, tutor.name, tutor.subject, tutor.phone) == (
            source["tutor_id"],
            source["tutor_name"],
            source["subject"],
            source["phone"],
        )

    raw_by_id = {
        row.as_dict()["lesson_id"]: row.as_dict() for row in preview.raw_lesson_rows
    }
    assert raw_by_id == {row["lesson_id"]: row for row in source_lessons}
    assert sum(row["cancelled_at"] != "" for row in source_lessons) == 2
    assert sum(row["note"] != "" for row in source_lessons) == 6

    lessons_by_id = {lesson.id: lesson for lesson in preview.lessons}
    mappings = dict(preview.lesson_mappings)
    assert mappings["L009"] == "L009"
    assert mappings["L010"] == "L009"
    assert "L010" not in lessons_by_id
    assert {student.name for student in lessons_by_id["L009"].students} == {
        "Tran Bao Long",
        "Nguyen Thi Ha",
    }

    for source in source_lessons:
        lesson = lessons_by_id[mappings[source["lesson_id"]]]
        assert lesson.starts_at.strftime("%Y-%m-%d") == source["date"]
        assert lesson.starts_at.strftime("%H:%M") == source["start_time"]
        assert lesson.starts_at.utcoffset() is not None
        assert lesson.duration_minutes == int(source["duration_min"])
        assert lesson.tutor.id == source["tutor_id"]
        assert lesson.room.id == source["room"]
        assert lesson.status.value == source["status"]
        assert source["student"] in {student.name for student in lesson.students}
        assert (
            lesson.cancelled_at.isoformat(timespec="seconds")
            if lesson.cancelled_at is not None
            else ""
        ) == source["cancelled_at"]
        assert (lesson.note or "") == source["note"]


def test_apply_stores_source_evidence_and_operational_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "bright_path.db"

    result = import_source(database_path, SOURCE_DATA_DIR)

    assert result.applied is True
    with sqlite3.connect(database_path) as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "tutors",
                "students",
                "rooms",
                "lessons",
                "lesson_participants",
                "raw_tutor_rows",
                "raw_lesson_rows",
                "raw_lesson_mappings",
            )
        }
        assert counts == {
            "tutors": 3,
            "students": 6,
            "rooms": 3,
            "lessons": 33,
            "lesson_participants": 34,
            "raw_tutor_rows": 3,
            "raw_lesson_rows": 34,
            "raw_lesson_mappings": 34,
        }

        stored_tutors = connection.execute(
            "SELECT id, name, subject, phone FROM tutors ORDER BY id"
        ).fetchall()
        assert stored_tutors == [
            (row["tutor_id"], row["tutor_name"], row["subject"], row["phone"])
            for row in read_csv_rows(SOURCE_DATA_DIR / "tutors.csv")
        ]

        raw_rows = connection.execute(
            """
            SELECT lesson_id, date, start_time, duration_min, student,
                   tutor_id, room, status, cancelled_at, note
            FROM raw_lesson_rows ORDER BY row_number
            """
        ).fetchall()
        assert raw_rows == [
            tuple(row[field] for field in LESSON_CSV_FIELDS)
            for row in read_csv_rows(SOURCE_DATA_DIR / "lessons_export.csv")
        ]

        mapping = dict(
            connection.execute(
                "SELECT raw_lesson_id, operational_lesson_id FROM raw_lesson_mappings"
            ).fetchall()
        )
        assert mapping["L009"] == mapping["L010"] == "L009"

        stored_timestamps = connection.execute(
            "SELECT starts_at, cancelled_at FROM lessons"
        ).fetchall()
        assert all(
            datetime.fromisoformat(starts_at).utcoffset() is not None
            for starts_at, _ in stored_timestamps
        )
        assert all(
            cancelled_at is None
            or datetime.fromisoformat(cancelled_at).utcoffset() is not None
            for _, cancelled_at in stored_timestamps
        )

        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE raw_lesson_rows SET note = 'changed' WHERE lesson_id = 'L001'"
            )


def test_identical_repeated_import_is_a_database_no_op(tmp_path: Path) -> None:
    database_path = tmp_path / "bright_path.db"
    first = import_source(database_path, SOURCE_DATA_DIR)
    before = hashlib.sha256(database_path.read_bytes()).hexdigest()

    second = import_source(database_path, SOURCE_DATA_DIR)
    after = hashlib.sha256(database_path.read_bytes()).hexdigest()

    assert first.applied is True
    assert second.applied is False
    assert second.import_id == first.import_id
    assert after == before


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            "L001,2026-03-03,09:00,60,Le Minh Chau,T1,R1,booked,,",
            "L001,bad-date,09:00,60,Le Minh Chau,T1,R1,booked,,",
            "date/start_time",
        ),
        (
            "L001,2026-03-03,09:00,60,Le Minh Chau,T1,R1,booked,,",
            "L001,2026-03-03,09:00,60,Le Minh Chau,TX,R1,booked,,",
            "unknown tutor_id",
        ),
        ("L002,2026-03-03", "L001,2026-03-03", "duplicate lesson_id"),
        (
            "L001,2026-03-03,09:00,60,Le Minh Chau,T1,R1,booked,,",
            "L001,2026-03-03,09:00,60,Le Minh Chau,T1,R1,pending,,",
            "unsupported status",
        ),
        (
            "cancelled,2026-03-03T08:15:00+07:00",
            "cancelled,",
            "require cancelled_at",
        ),
        (
            "cancelled,2026-03-03T08:15:00+07:00",
            "cancelled,2026-03-03T08:15:00",
            "timezone offset",
        ),
        (
            "L001,2026-03-03,09:00,60,Le Minh Chau,T1,R1,booked,,",
            "L001,2026-03-03,09:00,60,Le Minh Chau,T1,R1,booked,"
            "2026-03-03T08:00:00+07:00,",
            "only cancelled lessons",
        ),
    ],
)
def test_invalid_lesson_source_is_rejected_before_database_creation(
    tmp_path: Path,
    old: str,
    new: str,
    message: str,
) -> None:
    source_directory = copy_source(tmp_path)
    replace_once(source_directory / "lessons_export.csv", old, new)
    database_path = tmp_path / "should-not-exist.db"

    with pytest.raises(ImportValidationError, match=message):
        import_source(database_path, source_directory)

    assert not database_path.exists()


def test_duplicate_tutor_id_is_rejected_during_preview(tmp_path: Path) -> None:
    source_directory = copy_source(tmp_path)
    replace_once(source_directory / "tutors.csv", "T2,Pham Duc", "T1,Pham Duc")

    with pytest.raises(ImportValidationError, match="duplicate tutor_id"):
        preview_source(source_directory)


def test_source_evidence_hashes_remain_unchanged() -> None:
    actual = {
        name: hashlib.sha256((SOURCE_DATA_DIR / name).read_bytes()).hexdigest()
        for name in EXPECTED_SOURCE_HASHES
    }

    assert actual == EXPECTED_SOURCE_HASHES
