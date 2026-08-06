from typing import Any

import httpx

from ai_work_automation.models import ConnectorResult, DraftContent


class PmsConnector:
    def __init__(self, client: httpx.Client, api_key: str, base_url: str) -> None:
        self.client = client
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def create(
        self,
        draft: DraftContent,
        *,
        project_id: int,
        tracker_id: int | None = None,
        priority_id: int | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
    ) -> ConnectorResult:
        payload: dict[str, Any] = {
            "issue": {
                "project_id": project_id,
                "subject": draft.title,
                "description": draft.body,
            }
        }
        if tracker_id is not None:
            payload["issue"]["tracker_id"] = tracker_id
        if priority_id is not None:
            payload["issue"]["priority_id"] = priority_id
        if custom_fields:
            payload["issue"]["custom_fields"] = custom_fields

        try:
            response = self.client.post(
                "/issues.json",
                json=payload,
                headers={"X-Redmine-API-Key": self.api_key},
            )
        except httpx.HTTPError as exc:
            return ConnectorResult(ok=False, error=str(exc), retryable=True)

        if response.status_code >= 400:
            return ConnectorResult(
                ok=False,
                error=f"HTTP {response.status_code}: {response.text[:500]}",
                retryable=response.status_code >= 500,
            )

        data = response.json()
        issue_id = str(data["issue"]["id"])
        return ConnectorResult(
            ok=True,
            ref=issue_id,
            url=f"{self.base_url}/issues/{issue_id}",
            raw=data,
        )

    def add_comment(self, issue_id: str, notes: str) -> ConnectorResult:
        try:
            response = self.client.put(
                f"/issues/{issue_id}.json",
                json={"issue": {"notes": notes}},
                headers={"X-Redmine-API-Key": self.api_key},
            )
        except httpx.HTTPError as exc:
            return ConnectorResult(ok=False, error=str(exc), retryable=True)

        if response.status_code >= 400:
            return ConnectorResult(
                ok=False,
                error=f"HTTP {response.status_code}: {response.text[:500]}",
                retryable=response.status_code >= 500,
            )

        return ConnectorResult(
            ok=True,
            ref=issue_id,
            url=f"{self.base_url}/issues/{issue_id}",
        )
