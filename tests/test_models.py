from datetime import datetime, timezone
from ai_work_automation.models import CaseRecord, WorkOrderRecord, ConnectorResult


def test_case_record_requires_id_and_created_date():
    c = CaseRecord(
        id="500XX000001",
        case_number="00196720",
        subject="테스트",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )
    assert c.id == "500XX000001"


def test_connector_result_ok_has_url():
    r = ConnectorResult(ok=True, ref="4710", url="https://pms.example/issues/4710")
    assert r.ok is True
    assert r.url.endswith("4710")
