from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_work_automation.sf.adapter import SafetyError, SalesforceAdapter


def test_append_case_activities_respects_cutoff() -> None:
    client = MagicMock()
    client.get_sobject.return_value = {
        "Id": "500xx",
        "CaseNumber": "00196633",
        "Subject": "t",
        "Description": None,
        "CreatedDate": "2020-01-01T00:00:00.000+0000",
        "Status": "New",
        "Activities__c": "old",
    }
    adapter = SalesforceAdapter(
        client,
        cutoff=datetime(2025, 1, 1, tzinfo=timezone.utc),
        case_fields=[
            "Id",
            "CaseNumber",
            "Subject",
            "Description",
            "CreatedDate",
            "Status",
            "Activities__c",
        ],
        case_activities_field="Activities__c",
    )
    with pytest.raises(SafetyError):
        adapter.append_case_activities("500xx", "2026-08-07 [이동현] tip", case_selected=True)
    # 출장 보고 경로: 컷오프 무시
    adapter.append_case_activities(
        "500xx",
        "2026-08-07 [이동현] tip",
        case_selected=True,
        enforce_cutoff=False,
    )
    client.patch_sobject.assert_called()


def test_append_case_activities_prepends_newest_first() -> None:
    """Case Activities는 맨 위가 최신 — 새 줄을 앞에 붙인다."""
    client = MagicMock()
    client.get_sobject.return_value = {
        "Id": "500xx",
        "CaseNumber": "00196633",
        "Subject": "t",
        "Description": None,
        "CreatedDate": "2026-06-01T00:00:00.000+0000",
        "Status": "New",
        "Activities__c": "2026-06-12 [이동현] old\n2026-06-11 [이동현] older",
    }
    adapter = SalesforceAdapter(
        client,
        cutoff=datetime(2025, 1, 1, tzinfo=timezone.utc),
        case_fields=[
            "Id",
            "CaseNumber",
            "Subject",
            "Description",
            "CreatedDate",
            "Status",
            "Activities__c",
        ],
        case_activities_field="Activities__c",
    )
    adapter.append_case_activities("500xx", "2026-08-07 [이동현] tip", case_selected=True)
    client.patch_sobject.assert_called_once_with(
        "Case",
        "500xx",
        {
            "Activities__c": (
                "2026-08-07 [이동현] tip\n"
                "2026-06-12 [이동현] old\n"
                "2026-06-11 [이동현] older"
            )
        },
    )


def test_append_case_activities_empty_field_writes_line_only() -> None:
    client = MagicMock()
    client.get_sobject.return_value = {
        "Id": "500xx",
        "CaseNumber": "00196633",
        "Subject": "t",
        "Description": None,
        "CreatedDate": "2026-06-01T00:00:00.000+0000",
        "Status": "New",
        "Activities__c": "",
    }
    adapter = SalesforceAdapter(
        client,
        cutoff=datetime(2025, 1, 1, tzinfo=timezone.utc),
        case_fields=[
            "Id",
            "CaseNumber",
            "Subject",
            "Description",
            "CreatedDate",
            "Status",
            "Activities__c",
        ],
        case_activities_field="Activities__c",
    )
    adapter.append_case_activities("500xx", "2026-08-07 [이동현] tip", case_selected=True)
    client.patch_sobject.assert_called_once_with(
        "Case",
        "500xx",
        {"Activities__c": "2026-08-07 [이동현] tip"},
    )


def test_create_wo_and_attach(tmp_path: Path) -> None:
    client = MagicMock()
    client.post_sobject.return_value = {"id": "0WOxx", "success": True}
    client.create_content_version.return_value = {"id": "068xx", "success": True}
    adapter = SalesforceAdapter(
        client,
        cutoff=datetime(2025, 1, 1, tzinfo=timezone.utc),
        technical_service_record_type_id="0120o000001lQJ5AAM",
    )
    wo_id = adapter.create_technical_service_work_order(
        case_id="500xx",
        subject="SDC A6 Tip 교체",
        description="field report",
        status="Completed",
        start_date="2026-08-07T09:30:00.000+0900",
        end_date="2026-08-07T15:00:00.000+0900",
        extra_fields={"Field25__c": "비대상", "Survey_1__c": "설문 비대상"},
    )
    assert wo_id == "0WOxx"
    body = client.post_sobject.call_args.args[1]
    assert body["Status"] == "Completed"
    assert body["Field25__c"] == "비대상"
    assert body["Survey_1__c"] == "설문 비대상"
    f = tmp_path / "day.xlsx"
    f.write_bytes(b"PK\x03\x04fake")
    adapter.attach_file_to_record(wo_id, f, title="2026.08.07")
    client.create_content_version_from_bytes.assert_called_once()
    kwargs = client.create_content_version_from_bytes.call_args.kwargs
    assert kwargs["first_publish_location_id"] == "0WOxx"
    assert kwargs["data"] == b"PK\x03\x04fake"
