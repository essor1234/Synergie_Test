from __future__ import annotations

from typing import Any

import httpx
from streamlit.testing.v1 import AppTest

from bright_path.ui.api_client import ApiClient, ApiClientError
from bright_path.ui.pages import display_datetime, schedule_rows


def lesson() -> dict[str, Any]:
    return {
        "id": "L001",
        "starts_at": "2026-03-03T09:00:00+07:00",
        "ends_at": "2026-03-03T10:00:00+07:00",
        "duration_minutes": 60,
        "tutor": {"id": "T1", "name": "Ngoc Anh", "subject": "Maths"},
        "room": {"id": "R1"},
        "students": [{"id": "S1", "name": "Le Minh Chau"}],
        "status": "booked",
        "cancelled_at": None,
        "deleted_at": None,
        "note": "Family confirmed",
        "version": 2,
    }


class FakeClient:
    def __init__(self, role: str, tutor_id: str | None) -> None:
        self.role = role
        self.tutor_id = tutor_id

    def lookups(self) -> dict[str, list[dict[str, str]]]:
        tutors = [
            {"id": "T1", "name": "Ngoc Anh", "subject": "Maths", "phone": "090xxx1122"},
            {"id": "T2", "name": "Pham Duc", "subject": "English", "phone": "090xxx3344"},
        ]
        if self.role == "tutor":
            tutors = [item for item in tutors if item["id"] == self.tutor_id]
        return {
            "tutors": tutors,
            "students": [{"id": "S1", "name": "Le Minh Chau"}],
            "rooms": [{"id": "R1"}],
        }

    def schedule(self, **filters: str) -> list[dict[str, Any]]:
        return [lesson()]

    def history(self, lesson_id: str) -> list[dict[str, Any]]:
        return []

    def create_lesson(self, payload: dict[str, Any]) -> dict[str, Any]:
        return lesson()

    def update_lesson(self, lesson_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return lesson()

    def delete_lesson(
        self,
        lesson_id: str,
        *,
        expected_version: int,
        reason: str,
    ) -> dict[str, Any]:
        return lesson() | {"deleted_at": "2026-03-03T08:00:00+07:00"}


class FakeClientFactory:
    def __call__(self, base_url: str, role: str, tutor_id: str | None = None) -> FakeClient:
        return FakeClient(role, tutor_id)


def streamlit_script(factory) -> None:
    from bright_path.ui.app import render_app

    render_app(factory)


def test_schedule_rows_show_complete_operational_data() -> None:
    rows = schedule_rows([lesson()])

    assert rows == [
        {
            "ID": "L001",
            "Date": "Tue 03 Mar",
            "Start": "09:00",
            "End": "10:00",
            "Students": "Le Minh Chau",
            "Tutor": "Ngoc Anh",
            "Subject": "Maths",
            "Room": "R1",
            "Duration": "60 min",
            "Status": "Booked",
            "Changed": "Yes",
            "Cancelled at": "—",
            "Note": "Family confirmed",
            "Version": 2,
        }
    ]
    assert display_datetime("2026-03-03T09:00:00+07:00") == "Tue 03 Mar 2026, 09:00"


def test_api_client_sends_actor_headers_and_surfaces_validation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/schedule":
            return httpx.Response(200, json=[lesson()])
        return httpx.Response(
            409,
            json={
                "detail": "Room R1 is already used",
                "code": "lesson_validation",
                "issues": ["Room R1 is already used"],
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = ApiClient("http://test", "tutor", "T1", client=http_client)
        assert client.schedule()[0]["id"] == "L001"
        try:
            client.create_lesson({"reason": "test"})
        except ApiClientError as error:
            assert error.code == "lesson_validation"
            assert error.issues == ("Room R1 is already used",)
        else:
            raise AssertionError("Expected the API error to be raised")

    assert requests[0].headers["X-Demo-Role"] == "tutor"
    assert requests[0].headers["X-Demo-Tutor-Id"] == "T1"


def test_streamlit_navigation_is_role_specific() -> None:
    app = AppTest.from_function(
        streamlit_script,
        args=(FakeClientFactory(),),
        default_timeout=10,
    ).run()

    assert not app.exception
    assert app.header[0].value == "Center schedule"
    assert app.sidebar.radio[0].options == ["Schedule", "People and rooms"]

    app.sidebar.selectbox[0].set_value("Receptionist").run()
    assert not app.exception
    assert app.sidebar.radio[0].options == [
        "Schedule",
        "People and rooms",
        "Manage lessons",
    ]

    app.sidebar.selectbox[0].set_value("Tutor").run()
    assert not app.exception
    assert app.header[0].value == "My schedule"
    assert app.sidebar.radio[0].options == ["Schedule", "People and rooms"]
    assert len(app.sidebar.selectbox) == 2
