"""Small HTTP client used by the Streamlit interface."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx


class ApiClientError(RuntimeError):
    def __init__(
        self,
        detail: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        issues: list[str] | None = None,
    ) -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
        self.issues = tuple(issues or ())
        super().__init__(detail)


class ApiClient:
    def __init__(
        self,
        base_url: str,
        role: str,
        tutor_id: str | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.role = role
        self.tutor_id = tutor_id
        self._client = client

    @property
    def headers(self) -> dict[str, str]:
        values = {"X-Demo-Role": self.role}
        if self.tutor_id is not None:
            values["X-Demo-Tutor-Id"] = self.tutor_id
        return values

    def schedule(self, **filters: str) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/schedule", params=filters)

    def lookups(self) -> dict[str, list[dict[str, str]]]:
        return self._request("GET", "/api/v1/lookups")

    def lesson(self, lesson_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/lessons/{lesson_id}")

    def history(self, lesson_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/v1/lessons/{lesson_id}/history")

    def create_lesson(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/lessons", json=dict(payload))

    def update_lesson(self, lesson_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/api/v1/lessons/{lesson_id}", json=dict(payload))

    def delete_lesson(
        self,
        lesson_id: str,
        *,
        expected_version: int,
        reason: str,
    ) -> dict[str, Any]:
        return self._request(
            "DELETE",
            f"/api/v1/lessons/{lesson_id}",
            params={"expected_version": expected_version, "reason": reason},
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            if self._client is None:
                response = httpx.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    timeout=6,
                    **kwargs,
                )
            else:
                response = self._client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    **kwargs,
                )
        except httpx.RequestError as error:
            raise ApiClientError(
                "The scheduling service is unavailable. Start the project and try again."
            ) from error

        if response.is_success:
            return response.json()

        try:
            body = response.json()
        except ValueError:
            body = {}
        detail = body.get("detail", f"Request failed with status {response.status_code}")
        if isinstance(detail, list):
            detail = "; ".join(item.get("msg", str(item)) for item in detail)
        raise ApiClientError(
            str(detail),
            status_code=response.status_code,
            code=body.get("code"),
            issues=body.get("issues"),
        )
