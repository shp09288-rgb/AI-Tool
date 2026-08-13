from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from ai_work_automation.sf.adapter import SafetyError, SalesforceAdapter

VOC_RECORD_TYPE_ID = "012VOC000000000AAA"


def _adapter(**kwargs) -> SalesforceAdapter:
    client = kwargs.pop("client", MagicMock())
    return SalesforceAdapter(
        client,
        cutoff=datetime(2025, 1, 1, tzinfo=timezone.utc),
        voc_record_type_id=kwargs.pop("voc_record_type_id", VOC_RECORD_TYPE_ID),
        **kwargs,
    )


def test_create_voc_work_order_posts_case_id_and_voc_type():
    client = MagicMock()
    client.post_sobject.return_value = {"id": "0WOVOC1", "success": True}
    adapter = _adapter(client=client)

    wo_id = adapter.create_voc_work_order(
        case_id="500xx",
        fields={
            "Subject": "정전기 센서 불량",
            "Relevant_Department__c": "SW",
        },
    )

    assert wo_id == "0WOVOC1"
    client.post_sobject.assert_called_once()
    object_name, body = client.post_sobject.call_args.args
    assert object_name == "WorkOrder"
    assert body["CaseId"] == "500xx"
    assert body["RecordTypeId"] == VOC_RECORD_TYPE_ID
    assert body["Subject"] == "정전기 센서 불량"
    assert body["Relevant_Department__c"] == "SW"


def test_create_voc_work_order_forces_case_id_over_fields():
    client = MagicMock()
    client.post_sobject.return_value = {"id": "0WOVOC1", "success": True}
    adapter = _adapter(client=client)

    adapter.create_voc_work_order(
        case_id="500xx",
        fields={"CaseId": "500other", "RecordTypeId": "012wrong"},
    )

    body = client.post_sobject.call_args.args[1]
    assert body["CaseId"] == "500xx"
    assert body["RecordTypeId"] == VOC_RECORD_TYPE_ID


def test_create_voc_work_order_raises_without_record_type_id():
    client = MagicMock()
    adapter = SalesforceAdapter(
        client,
        cutoff=datetime(2025, 1, 1, tzinfo=timezone.utc),
        voc_record_type_id=None,
    )

    with pytest.raises(SafetyError, match="voc_record_type_id"):
        adapter.create_voc_work_order(case_id="500xx", fields={"Subject": "x"})

    client.post_sobject.assert_not_called()


def test_create_case_posts_sobject_and_returns_id():
    client = MagicMock()
    client.post_sobject.return_value = {"id": "500NEW", "success": True}
    adapter = _adapter(client=client)

    case_id = adapter.create_case(
        {"Subject": "정전기 센서 불량", "Description": "요약"}
    )

    assert case_id == "500NEW"
    client.post_sobject.assert_called_once_with(
        "Case",
        {"Subject": "정전기 센서 불량", "Description": "요약"},
    )


def test_find_case_by_number_returns_case_record():
    client = MagicMock()
    client.query.return_value = {
        "records": [
            {
                "Id": "500CASE1",
                "CaseNumber": "00173841",
                "Subject": "Motor 축 SOL 이상",
                "Description": "상세",
                "CreatedDate": "2025-12-19T06:51:38.000+00:00",
                "Status": "New",
                "Activities__c": "PMS - https://pms.example/issues/1",
                "AssetId": "02iASSET1",
            }
        ]
    }
    adapter = _adapter(client=client)

    case = adapter.find_case_by_number("00173841")

    assert case is not None
    assert case.id == "500CASE1"
    assert case.case_number == "00173841"
    assert case.subject == "Motor 축 SOL 이상"
    assert case.description == "상세"
    assert case.status == "New"
    assert case.asset_id == "02iASSET1"
    assert case.activities == "PMS - https://pms.example/issues/1"
    soql = client.query.call_args.args[0]
    assert "FROM Case" in soql
    assert "CaseNumber = '00173841'" in soql
    assert "AssetId" in soql


def test_find_case_by_number_parses_salesforce_offset_without_colon():
    client = MagicMock()
    client.query.return_value = {
        "records": [
            {
                "Id": "500CASE1",
                "CaseNumber": "00173841",
                "Subject": "Motor",
                "CreatedDate": "2025-12-19T06:51:38.000+0000",
                "Status": "New",
            }
        ]
    }
    adapter = _adapter(client=client)

    case = adapter.find_case_by_number("00173841")

    assert case is not None
    assert case.created_date == datetime(2025, 12, 19, 6, 51, 38, tzinfo=timezone.utc)


def test_find_case_by_number_returns_none_when_missing():
    client = MagicMock()
    client.query.return_value = {"records": []}
    adapter = _adapter(client=client)

    assert adapter.find_case_by_number("99999999") is None


def test_find_case_by_number_escapes_soql():
    client = MagicMock()
    client.query.return_value = {"records": []}
    adapter = _adapter(client=client)

    adapter.find_case_by_number("0017'341")

    soql = client.query.call_args.args[0]
    assert "CaseNumber = '0017\\'341'" in soql
