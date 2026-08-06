from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from ai_work_automation.models import WorkOrderRecord
from ai_work_automation.sf.adapter import SafetyError, SalesforceAdapter


def test_append_blocked_before_cutoff():
    client = MagicMock()
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
    )
    wo = WorkOrderRecord(
        id="0WOOLD",
        work_order_number="1",
        record_type="VOC",
        activities="old",
        created_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(SafetyError):
        adapter.append_work_order_activities(
            wo,
            line="PMS - https://pms.example/issues/1",
            case_selected=True,
        )

    client.patch_sobject.assert_not_called()


def test_append_blocked_when_not_selected():
    client = MagicMock()
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
    )
    wo = WorkOrderRecord(
        id="0WONEW",
        work_order_number="1",
        record_type="VOC",
        activities="",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(SafetyError):
        adapter.append_work_order_activities(
            wo,
            line="PMS - https://pms.example/issues/1",
            case_selected=False,
        )

    client.patch_sobject.assert_not_called()


def test_append_succeeds_when_allowed():
    client = MagicMock()
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        activities_field="VOC_Activities__c",
    )
    wo = WorkOrderRecord(
        id="0WONEW",
        work_order_number="1",
        record_type="VOC",
        activities="기존메모",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )

    adapter.append_work_order_activities(
        wo,
        line="PMS - https://pms.example/issues/1",
        case_selected=True,
    )

    client.patch_sobject.assert_called_once()
    args, kwargs = client.patch_sobject.call_args
    assert args[0] == "WorkOrder"
    assert args[1] == "0WONEW"
    body = args[2]
    assert "기존메모" in body["VOC_Activities__c"]
    assert "PMS - https://pms.example/issues/1" in body["VOC_Activities__c"]
