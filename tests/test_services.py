from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from ai_work_automation.models import ConnectorResult, WorkOrderRecord
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.services import (
    CaseScanGroup,
    ScanRow,
    case_group_label,
    group_unlinked_by_case,
    scan_candidates,
    status_overview,
)
from ai_work_automation.sf.adapter import CandidateWorkOrder


def _wo(id: str, activities: str = "", case_id: str = "500CASE1") -> WorkOrderRecord:
    return WorkOrderRecord(
        id=id,
        work_order_number=f"WO-{id}",
        record_type="VOC",
        relevant_department="SW",
        voc_title=f"제목 {id}",
        activities=activities,
        case_id=case_id,
        created_date=datetime(2026, 8, 6, tzinfo=timezone.utc),
    )


def test_scan_candidates_marks_linked_and_selected(tmp_path: Path):
    sf = MagicMock()
    sf.find_recent_voc_work_orders.return_value = [
        CandidateWorkOrder(
            work_order=_wo("0WO1", activities=""),
            case_number="00200750",
            case_subject="케이스 A",
            asset_name="NX-TSH2326",
            asset_sid="D25003-230523",
            status="New",
        ),
        CandidateWorkOrder(
            work_order=_wo("0WO2", activities="https://pms.parksystems.com/issues/3807", case_id="500CASE2"),
            case_number="00173841",
            case_subject="케이스 B",
        ),
    ]
    opt = OptInStore(tmp_path / "opt.json")
    opt.select("500CASE1")

    rows = scan_candidates(
        sf,
        opt,
        department="SW",
        asset_contains=["NX-TSH2326"],
        sid_contains=["D25003"],
        status_in=["New"],
        owner_contains="이동한",
    )

    assert len(rows) == 2
    first = rows[0]
    assert first.case_number == "00200750"
    assert first.linked is False
    assert first.selected is True
    assert first.asset_name == "NX-TSH2326"
    assert first.asset_sid == "D25003-230523"
    assert first.status == "New"
    second = rows[1]
    assert second.linked is True
    assert second.selected is False
    sf.find_recent_voc_work_orders.assert_called_once_with(
        department="SW",
        asset_contains=["NX-TSH2326"],
        sid_contains=["D25003"],
        status_in=["New"],
        owner_contains="이동한",
    )


def test_status_overview_fetches_issue_states(tmp_path: Path):
    sf = MagicMock()
    sf.get_work_orders_for_case.return_value = [
        _wo("0WO1", activities="https://pms.parksystems.com/issues/3807"),
        _wo("0WO2", activities=""),  # 링크 없음 -> 상태 조회 대상 아님
    ]
    pms = MagicMock()
    pms.get_issue.return_value = ConnectorResult(
        ok=True,
        ref="3807",
        url="https://pms.parksystems.com/issues/3807",
        raw={
            "issue": {
                "id": 3807,
                "subject": "이슈 제목",
                "status": {"name": "Closed"},
                "updated_on": "2026-01-12T04:28:42Z",
            }
        },
    )
    opt = OptInStore(tmp_path / "opt.json")
    opt.select("500CASE1")

    rows = status_overview(sf, pms, opt)

    assert len(rows) == 1
    row = rows[0]
    assert row.case_id == "500CASE1"
    assert row.work_order_number == "WO-0WO1"
    assert row.issue_id == "3807"
    assert row.issue_status == "Closed"
    assert row.issue_subject == "이슈 제목"
    pms.get_issue.assert_called_once_with("3807")


def _row(**kwargs) -> ScanRow:
    data = dict(
        case_id="500A",
        case_number="00183895",
        case_subject="Subject",
        work_order_id="0WO1",
        work_order_number="00025526",
        title="VOC A",
        created_date="2026-08-12T10:00:00+00:00",
        linked=False,
        selected=False,
    )
    data.update(kwargs)
    return ScanRow(**data)


def test_group_same_case_two_unlinked_into_one_group():
    rows = [
        _row(work_order_id="0WO1", work_order_number="00025526", title="First",
             created_date="2026-08-12T09:00:00+00:00"),
        _row(work_order_id="0WO2", work_order_number="00025527", title="Second",
             created_date="2026-08-12T11:00:00+00:00"),
    ]
    groups = group_unlinked_by_case(rows)
    assert len(groups) == 1
    assert len(groups[0].unlinked) == 2
    assert groups[0].linked_count == 0
    assert case_group_label(groups[0]).startswith("00183895 · 미연동 2건 ·")


def test_group_counts_linked_but_excludes_from_unlinked():
    rows = [
        _row(work_order_id="0WO1", linked=False),
        _row(work_order_id="0WO2", work_order_number="00025527", linked=True,
             created_date="2026-08-12T12:00:00+00:00"),
    ]
    groups = group_unlinked_by_case(rows)
    assert len(groups) == 1
    assert len(groups[0].unlinked) == 1
    assert groups[0].linked_count == 1


def test_group_key_falls_back_to_case_number_when_case_id_empty():
    rows = [
        _row(case_id="", case_number="00190001", work_order_id="0WO1"),
        _row(case_id="", case_number="00190001", work_order_id="0WO2",
             work_order_number="0002"),
    ]
    groups = group_unlinked_by_case(rows)
    assert len(groups) == 1
    assert groups[0].case_number == "00190001"


def test_group_omits_cases_with_only_linked_rows():
    rows = [_row(linked=True)]
    assert group_unlinked_by_case(rows) == []


def test_groups_sorted_by_newest_unlinked_created_date_desc():
    older = _row(case_id="500OLD", case_number="00100001",
                 created_date="2026-01-01T00:00:00+00:00")
    newer = _row(case_id="500NEW", case_number="00100002",
                 created_date="2026-08-15T00:00:00+00:00")
    groups = group_unlinked_by_case([older, newer])
    assert [g.case_id for g in groups] == ["500NEW", "500OLD"]
