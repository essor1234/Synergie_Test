"""SQLite connection and schema helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    tutor_id TEXT REFERENCES tutors(id)
);

CREATE TABLE IF NOT EXISTS tutors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    subject TEXT NOT NULL,
    phone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS lessons (
    id TEXT PRIMARY KEY,
    starts_at TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    tutor_id TEXT NOT NULL REFERENCES tutors(id),
    room_id TEXT NOT NULL REFERENCES rooms(id),
    status TEXT NOT NULL CHECK (status IN ('booked', 'cancelled', 'no_show')),
    cancelled_at TEXT,
    deleted_at TEXT,
    note TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    CHECK (
        (status = 'cancelled' AND cancelled_at IS NOT NULL)
        OR (status <> 'cancelled' AND cancelled_at IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS lesson_participants (
    lesson_id TEXT NOT NULL REFERENCES lessons(id),
    student_id TEXT NOT NULL REFERENCES students(id),
    position INTEGER NOT NULL CHECK (position IN (1, 2)),
    PRIMARY KEY (lesson_id, student_id),
    UNIQUE (lesson_id, position)
);

CREATE TABLE IF NOT EXISTS lesson_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL REFERENCES lessons(id),
    before_state TEXT NOT NULL,
    after_state TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_signature TEXT NOT NULL UNIQUE,
    tutors_sha256 TEXT NOT NULL,
    lessons_sha256 TEXT NOT NULL,
    resolutions_sha256 TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_tutor_rows (
    import_id INTEGER NOT NULL REFERENCES source_imports(id),
    row_number INTEGER NOT NULL,
    tutor_id TEXT NOT NULL,
    tutor_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    phone TEXT NOT NULL,
    PRIMARY KEY (import_id, row_number)
);

CREATE TABLE IF NOT EXISTS raw_lesson_rows (
    import_id INTEGER NOT NULL REFERENCES source_imports(id),
    row_number INTEGER NOT NULL,
    lesson_id TEXT NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    duration_min TEXT NOT NULL,
    student TEXT NOT NULL,
    tutor_id TEXT NOT NULL,
    room TEXT NOT NULL,
    status TEXT NOT NULL,
    cancelled_at TEXT NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (import_id, row_number)
);

CREATE TABLE IF NOT EXISTS raw_lesson_mappings (
    import_id INTEGER NOT NULL REFERENCES source_imports(id),
    raw_lesson_id TEXT NOT NULL,
    operational_lesson_id TEXT NOT NULL REFERENCES lessons(id),
    PRIMARY KEY (import_id, raw_lesson_id)
);

CREATE TRIGGER IF NOT EXISTS raw_tutor_rows_no_update
BEFORE UPDATE ON raw_tutor_rows
BEGIN
    SELECT RAISE(ABORT, 'raw tutor evidence is immutable');
END;

CREATE TRIGGER IF NOT EXISTS raw_tutor_rows_no_delete
BEFORE DELETE ON raw_tutor_rows
BEGIN
    SELECT RAISE(ABORT, 'raw tutor evidence is immutable');
END;

CREATE TRIGGER IF NOT EXISTS raw_lesson_rows_no_update
BEFORE UPDATE ON raw_lesson_rows
BEGIN
    SELECT RAISE(ABORT, 'raw lesson evidence is immutable');
END;

CREATE TRIGGER IF NOT EXISTS raw_lesson_rows_no_delete
BEFORE DELETE ON raw_lesson_rows
BEGIN
    SELECT RAISE(ABORT, 'raw lesson evidence is immutable');
END;

CREATE TRIGGER IF NOT EXISTS raw_lesson_mappings_no_update
BEFORE UPDATE ON raw_lesson_mappings
BEGIN
    SELECT RAISE(ABORT, 'raw lesson mappings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS raw_lesson_mappings_no_delete
BEFORE DELETE ON raw_lesson_mappings
BEGIN
    SELECT RAISE(ABORT, 'raw lesson mappings are immutable');
END;
"""


def connect_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    lesson_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(lessons)").fetchall()
    }
    if "deleted_at" not in lesson_columns:
        connection.execute("ALTER TABLE lessons ADD COLUMN deleted_at TEXT")
