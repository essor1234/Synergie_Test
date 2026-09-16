from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from bright_path.api.dependencies import get_lesson_service
from bright_path.api.main import app
from bright_path.services.lesson_service import LessonService
from bright_path.settings import SOURCE_DATA_DIR
from bright_path.storage.seed import import_source

BANGKOK = ZoneInfo("Asia/Bangkok")
OWNER_HEADERS = {"X-Demo-Role": "owner"}
RECEPTIONIST_HEADERS = {"X-Demo-Role": "receptionist"}
TUTOR_T1_HEADERS = {"X-Demo-Role": "tutor", "X-Demo-Tutor-Id": "T1"}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "bright_path.db"
    import_source(database_path, SOURCE_DATA_DIR)
    service = LessonService(
        database_path,
        now=lambda: datetime(2026, 3, 10, 15, 0, tzinfo=BANGKOK),
        make_lesson_id=lambda: "L-API",
    )
    app.dependency_overrides[get_lesson_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def lookup_id(client: TestClient, collection: str, name: str) -> str:
    response = client.get("/api/v1/lookups", headers=RECEPTIONIST_HEADERS)
    return next(item["id"] for item in response.json()[collection] if item["name"] == name)


def lesson_payload(client: TestClient) -> dict[str, object]:
    return {
        "starts_at": "2026-03-10T11:00:00+07:00",
        "duration_minutes": 60,
        "tutor_id": "T2",
        "room_id": "R3",
        "student_ids": [lookup_id(client, "students", "Bui An Nhien")],
        "status": "booked",
        "cancelled_at": None,
        "note": "Created through API",
        "reason": "New family booking",
    }


def test_owner_and_tutor_receive_role_filtered_schedules(client: TestClient) -> None:
    owner_schedule = client.get("/api/v1/schedule", headers=OWNER_HEADERS)
    tutor_schedule = client.get("/api/v1/schedule", headers=TUTOR_T1_HEADERS)

    assert owner_schedule.status_code == 200
    assert len(owner_schedule.json()) == 33
    assert tutor_schedule.status_code == 200
    assert tutor_schedule.json()
    assert {lesson["tutor"]["id"] for lesson in tutor_schedule.json()} == {"T1"}
    assert "phone" not in tutor_schedule.json()[0]["tutor"]


def test_tutor_cannot_read_another_tutors_lesson(client: TestClient) -> None:
    response = client.get("/api/v1/lessons/L002", headers=TUTOR_T1_HEADERS)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_role_appropriate_lookups_do_not_leak_other_tutor_phones(client: TestClient) -> None:
    owner = client.get("/api/v1/lookups", headers=OWNER_HEADERS).json()
    tutor = client.get("/api/v1/lookups", headers=TUTOR_T1_HEADERS).json()

    assert len(owner["tutors"]) == 3
    assert len(tutor["tutors"]) == 1
    assert tutor["tutors"][0]["id"] == "T1"
    assert tutor["tutors"][0]["phone"] == "090xxx1122"


def test_receptionist_can_complete_crud_flow(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/lessons",
        headers=RECEPTIONIST_HEADERS,
        json=lesson_payload(client),
    )
    assert create_response.status_code == 201
    created = create_response.json()

    update_body = lesson_payload(client) | {
        "note": "Updated through API",
        "reason": "Family confirmed",
        "expected_version": created["version"],
    }
    update_response = client.patch(
        f"/api/v1/lessons/{created['id']}",
        headers=RECEPTIONIST_HEADERS,
        json=update_body,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["note"] == "Updated through API"
    assert updated["version"] == 2

    stale_response = client.patch(
        f"/api/v1/lessons/{created['id']}",
        headers=RECEPTIONIST_HEADERS,
        json=update_body,
    )
    assert stale_response.status_code == 409
    assert stale_response.json()["code"] == "stale_version"

    delete_response = client.delete(
        f"/api/v1/lessons/{created['id']}",
        headers=RECEPTIONIST_HEADERS,
        params={"expected_version": 2, "reason": "Entered by mistake"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_at"] is not None

    history = client.get(
        f"/api/v1/lessons/{created['id']}/history",
        headers=OWNER_HEADERS,
    )
    assert history.status_code == 200
    assert [item["reason"] for item in history.json()] == [
        "New family booking",
        "Family confirmed",
        "Entered by mistake",
    ]


def test_owner_cannot_create_lesson(client: TestClient) -> None:
    response = client.post(
        "/api/v1/lessons",
        headers=OWNER_HEADERS,
        json=lesson_payload(client),
    )

    assert response.status_code == 403


def test_business_rule_failure_returns_specific_409(client: TestClient) -> None:
    payload = lesson_payload(client) | {
        "starts_at": "2026-03-09T11:00:00+07:00",
    }

    response = client.post(
        "/api/v1/lessons",
        headers=RECEPTIONIST_HEADERS,
        json=payload,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "lesson_validation"
    assert "closed on Monday" in response.json()["detail"]


def test_removed_conflict_endpoint_does_not_exist(client: TestClient) -> None:
    response = client.get("/api/v1/conflicts", headers=OWNER_HEADERS)

    assert response.status_code == 404
