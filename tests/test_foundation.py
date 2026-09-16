from fastapi.testclient import TestClient

from bright_path.api.main import app


def test_health_endpoint_reports_ready_api() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "bright-path-api"}
