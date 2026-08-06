import json

import httpx

from ai_work_automation.connectors.pms import PmsConnector
from ai_work_automation.models import DraftContent


def test_create_issue_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/issues.json")
        assert request.headers.get("X-Redmine-API-Key") == "secret"
        assert json.loads(request.content) == {
            "issue": {
                "project_id": 1,
                "subject": "제목",
                "description": "본문",
            }
        }
        return httpx.Response(201, json={"issue": {"id": 4710}})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://pms.example")
    connector = PmsConnector(client=client, api_key="secret", base_url="https://pms.example")

    result = connector.create(DraftContent(title="제목", body="본문"), project_id=1)

    assert result.ok is True
    assert result.ref == "4710"
    assert result.url == "https://pms.example/issues/4710"


def test_create_issue_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://pms.example")
    connector = PmsConnector(client=client, api_key="secret", base_url="https://pms.example")

    result = connector.create(DraftContent(title="t", body="b"), project_id=1)

    assert result.ok is False
    assert result.retryable is True
