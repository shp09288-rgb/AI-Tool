from datetime import datetime, timezone
from unittest.mock import MagicMock

from ai_work_automation.models import CaseRecord, ConnectorResult, WorkOrderRecord
from ai_work_automation.settings import Settings
from ai_work_automation.sf.adapter import SafetyError
from ai_work_automation.tool_first_voc import (
    ToolFirstVocInput,
    run_tool_first_voc,
)

CUTOFF = datetime(2025, 1, 1, tzinfo=timezone.utc)
PMS_URL = "https://pms.example/issues/3807"


def _settings() -> Settings:
    return Settings(
        automation_enabled_after=CUTOFF,
        pms_project_id=1,
        pms_base_url="https://pms.example",
        wo_department_field="Relevant_Department__c",
    )


def _payload(**kwargs) -> ToolFirstVocInput:
    data = dict(
        mode="existing_case",
        title="정전기 센서 불량",
        department="SW",
        pms_html_body="<p>현장 본문</p>",
        case_number="00173841",
        sf_summary="요약",
    )
    data.update(kwargs)
    return ToolFirstVocInput(**data)


def _case(**kwargs) -> CaseRecord:
    data = dict(
        id="500CASE1",
        case_number="00173841",
        subject="기존 Case",
        created_date=datetime(2026, 1, 2, tzinfo=timezone.utc),
        description="설명",
        activities="",
    )
    data.update(kwargs)
    return CaseRecord(**data)


def _wo(**kwargs) -> WorkOrderRecord:
    data = dict(
        id="0WOOLD",
        work_order_number="00023044",
        record_type="VOC",
        relevant_department="SW",
        subject="이전 VOC",
        activities="",
        case_id="500CASE1",
        created_date=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    data.update(kwargs)
    return WorkOrderRecord(**data)


def _sf(*, case: CaseRecord | None = None, existing_wos: list | None = None) -> MagicMock:
    sf = MagicMock()
    sf.client = MagicMock()
    sf.client.instance_url = "https://sf.example"
    sf.client.post_sobject = MagicMock()
    sf.find_case_by_number.return_value = case
    sf.get_work_orders_for_case.return_value = existing_wos or []
    sf.create_case.return_value = "500NEW"
    sf.create_voc_work_order.return_value = "0WONEW"
    return sf


def test_existing_case_with_pms_issue_adds_comment_not_create():
    case = _case()
    old_wo = _wo(activities=f"PMS – {PMS_URL}")
    sf = _sf(case=case, existing_wos=[old_wo])
    pms = MagicMock()
    pms.add_comment.return_value = ConnectorResult(ok=True, ref="3807", url=PMS_URL)

    result = run_tool_first_voc(
        sf, pms, _settings(), _payload(), dry_run=False, approved=True
    )

    assert result.ok is True
    assert result.pms_action == "comment"
    assert result.pms_issue_id == "3807"
    assert result.work_order_id == "0WONEW"
    pms.create.assert_not_called()
    pms.add_comment.assert_called_once()
    assert pms.add_comment.call_args.args[0] == "3807"
    assert "현장 본문" in pms.add_comment.call_args.args[1]
    sf.create_voc_work_order.assert_called_once()
    sf.append_work_order_activities.assert_called_once()
    wo_arg, line = sf.append_work_order_activities.call_args.args[:2]
    assert wo_arg.id == "0WONEW"
    assert f"PMS – {PMS_URL}" in line
    assert sf.append_work_order_activities.call_args.kwargs["case_selected"] is True
    assert sf.append_work_order_activities.call_args.kwargs.get("enforce_cutoff") is False


def test_existing_case_without_issue_creates_pms_issue():
    case = _case(activities="")
    sf = _sf(case=case, existing_wos=[_wo(activities="")])
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )

    result = run_tool_first_voc(
        sf, pms, _settings(), _payload(), dry_run=False, approved=True
    )

    assert result.ok is True
    assert result.pms_action == "create"
    assert result.pms_issue_id == "4710"
    pms.add_comment.assert_not_called()
    pms.create.assert_called_once()
    draft = pms.create.call_args.args[0]
    assert draft.title == "정전기 센서 불량"
    assert "현장 본문" in draft.body
    assert pms.create.call_args.kwargs["project_id"] == 1
    line = sf.append_work_order_activities.call_args.args[1]
    assert line == "PMS – https://pms.example/issues/4710"


def test_existing_case_finds_issue_id_on_case_activities():
    case = _case(activities=f"PMS - {PMS_URL}")
    sf = _sf(case=case, existing_wos=[])
    pms = MagicMock()
    pms.add_comment.return_value = ConnectorResult(ok=True, ref="3807", url=PMS_URL)

    result = run_tool_first_voc(
        sf, pms, _settings(), _payload(), dry_run=False, approved=True
    )

    assert result.pms_action == "comment"
    pms.create.assert_not_called()
    pms.add_comment.assert_called_once()
    assert pms.add_comment.call_args.args[0] == "3807"


def test_dry_run_does_not_post_sobject_or_write_pms():
    case = _case()
    sf = _sf(case=case, existing_wos=[])
    pms = MagicMock()

    result = run_tool_first_voc(
        sf, pms, _settings(), _payload(), dry_run=True, approved=True
    )

    assert result.dry_run is True
    assert result.ok is True
    assert result.pms_action == "create"
    sf.create_case.assert_not_called()
    sf.create_voc_work_order.assert_not_called()
    sf.append_work_order_activities.assert_not_called()
    sf.client.post_sobject.assert_not_called()
    pms.create.assert_not_called()
    pms.add_comment.assert_not_called()


def test_not_approved_does_not_write():
    sf = _sf(case=_case())
    pms = MagicMock()

    result = run_tool_first_voc(
        sf, pms, _settings(), _payload(), dry_run=False, approved=False
    )

    assert result.ok is False
    assert "승인" in result.message
    sf.create_case.assert_not_called()
    sf.create_voc_work_order.assert_not_called()
    sf.append_work_order_activities.assert_not_called()
    sf.client.post_sobject.assert_not_called()
    pms.create.assert_not_called()
    pms.add_comment.assert_not_called()


def test_attachments_uploaded_to_case_and_wo_after_create():
    sf = _sf()
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )
    payload = _payload(
        mode="new_case",
        case_number=None,
        attachment_files=[("shot.png", b"PNGDATA")],
    )

    result = run_tool_first_voc(
        sf, pms, _settings(), payload, dry_run=False, approved=True
    )

    assert result.ok is True
    calls = sf.client.create_content_version_from_bytes.call_args_list
    assert len(calls) == 2
    locations = {c.kwargs["first_publish_location_id"] for c in calls}
    assert locations == {"500NEW", "0WONEW"}
    assert all(c.kwargs["data"] == b"PNGDATA" for c in calls)
    assert all(c.kwargs["path_on_client"] == "shot.png" for c in calls)


def test_dry_run_does_not_attach_files():
    case = _case()
    sf = _sf(case=case, existing_wos=[])
    pms = MagicMock()
    payload = _payload(attachment_files=[("shot.png", b"PNGDATA")])

    run_tool_first_voc(sf, pms, _settings(), payload, dry_run=True, approved=True)

    sf.client.create_content_version_from_bytes.assert_not_called()
    sf.create_case.assert_not_called()
    sf.create_voc_work_order.assert_not_called()


def test_attach_failure_does_not_fail_voc():
    sf = _sf()
    sf.client.create_content_version_from_bytes.side_effect = RuntimeError("sf down")
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )
    payload = _payload(
        mode="new_case",
        case_number=None,
        attachment_files=[("shot.png", b"PNGDATA")],
    )

    result = run_tool_first_voc(
        sf, pms, _settings(), payload, dry_run=False, approved=True
    )

    assert result.ok is True
    assert result.pms_action == "create"
    pms.create.assert_called_once()


def test_new_case_creates_case_wo_and_pms_issue():
    sf = _sf()
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )
    payload = _payload(
        mode="new_case",
        case_number=None,
        asset_id="02iASSET1",
        asset_sid="SID-1",
    )

    result = run_tool_first_voc(
        sf, pms, _settings(), payload, dry_run=False, approved=True
    )

    assert result.ok is True
    assert result.case_id == "500NEW"
    assert result.work_order_id == "0WONEW"
    assert result.pms_action == "create"
    sf.find_case_by_number.assert_not_called()
    sf.create_case.assert_called_once()
    case_fields = sf.create_case.call_args.args[0]
    assert case_fields["Subject"] == "정전기 센서 불량"
    assert case_fields["Description"] == "요약"
    sf.create_voc_work_order.assert_called_once()
    wo_kwargs = sf.create_voc_work_order.call_args.kwargs
    assert wo_kwargs["case_id"] == "500NEW"
    assert wo_kwargs["fields"]["Subject"] == "정전기 센서 불량"
    assert wo_kwargs["fields"]["Relevant_Department__c"] == "SW"
    assert wo_kwargs["fields"]["AssetId"] == "02iASSET1"
    assert wo_kwargs["fields"]["Asset_SID__c"] == "SID-1"
    pms.create.assert_called_once()
    pms.add_comment.assert_not_called()
    line = sf.append_work_order_activities.call_args.args[1]
    assert line == "PMS – https://pms.example/issues/4710"
    assert result.links["pms"] == "https://pms.example/issues/4710"
    assert sf.append_work_order_activities.call_args.kwargs.get("enforce_cutoff") is False


def test_activities_append_failure_still_returns_created_ids():
    sf = _sf()
    sf.append_work_order_activities.side_effect = SafetyError(
        "컷오프 이전 Work Order는 수정할 수 없습니다"
    )
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )
    payload = _payload(mode="new_case", case_number=None)

    result = run_tool_first_voc(
        sf, pms, _settings(), payload, dry_run=False, approved=True
    )

    assert result.ok is True
    assert result.case_id == "500NEW"
    assert result.work_order_id == "0WONEW"
    assert result.pms_issue_id == "4710"
    assert result.pms_url == "https://pms.example/issues/4710"
    assert result.links["case"] == "https://sf.example/500NEW"
    assert result.links["work_order"] == "https://sf.example/0WONEW"
    assert result.links["pms"] == "https://pms.example/issues/4710"
    assert "Activities" in result.message
