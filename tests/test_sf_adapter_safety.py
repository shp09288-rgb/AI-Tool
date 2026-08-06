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


def test_get_work_orders_maps_voc_title_and_keeps_department():
    client = MagicMock()
    client.query.return_value = {
        "records": [
            {
                "Id": "0WONEW",
                "WorkOrderNumber": "1",
                "Subject": None,
                "CreatedDate": "2026-12-02T00:00:00Z",
                "CaseId": "500CASE1",
                "Priority": "High",
                "VOC_Activities__c": "",
                "VOC_Title__c": "공통 / NX / [PMS] Alarm 분기 요청",
                "Relevant_Department__c": "SW",
                "RecordType": {"Name": "VOC"},
            }
        ]
    }
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        wo_fields=[
            "Id",
            "WorkOrderNumber",
            "Subject",
            "CreatedDate",
            "CaseId",
            "Priority",
            "VOC_Activities__c",
            "VOC_Title__c",
            "Relevant_Department__c",
        ],
    )

    work_orders = adapter.get_work_orders_for_case("500CASE1")

    assert work_orders[0].voc_title == "공통 / NX / [PMS] Alarm 분기 요청"
    assert work_orders[0].relevant_department == "SW"


def test_find_case_id_by_number():
    client = MagicMock()
    client.query.return_value = {
        "records": [{"Id": "500CASE1", "CaseNumber": "00173841"}]
    }
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
    )

    case_id = adapter.find_case_id_by_number("00173841")

    assert case_id == "500CASE1"
    soql = client.query.call_args.args[0]
    assert "CaseNumber = '00173841'" in soql


def test_find_case_id_by_number_returns_none_when_missing():
    client = MagicMock()
    client.query.return_value = {"records": []}
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
    )

    assert adapter.find_case_id_by_number("99999999") is None


def test_get_work_orders_maps_relevant_department_from_custom_field():
    client = MagicMock()
    client.query.return_value = {
        "records": [
            {
                "Id": "0WONEW",
                "WorkOrderNumber": "1",
                "Subject": "VOC case",
                "CreatedDate": "2026-12-02T00:00:00Z",
                "CaseId": "500CASE1",
                "Priority": "High",
                "VOC_Activities__c": "",
                "Relevant_Department__c": "SW",
                "RecordType": {"Name": "VOC"},
            }
        ]
    }
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        wo_fields=[
            "Id",
            "WorkOrderNumber",
            "Subject",
            "CreatedDate",
            "CaseId",
            "Priority",
            "VOC_Activities__c",
            "Relevant_Department__c",
        ],
    )

    work_orders = adapter.get_work_orders_for_case("500CASE1")

    assert work_orders[0].relevant_department == "SW"
    soql = client.query.call_args.args[0]
    assert "Relevant_Department__c" in soql
