from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from ai_work_automation.models import ConnectorResult, WorkOrderRecord
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.services import scan_candidates, status_overview
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
        ),
        CandidateWorkOrder(
            work_order=_wo("0WO2", activities="https://pms.parksystems.com/issues/3807", case_id="500CASE2"),
            case_number="00173841",
            case_subject="케이스 B",
        ),
    ]
    opt = OptInStore(tmp_path / "opt.json")
    opt.select("500CASE1")

    rows = scan_candidates(sf, opt, department="SW")

    assert len(rows) == 2
    first = rows[0]
    assert first.case_number == "00200750"
    assert first.linked is False
    assert first.selected is True
    second = rows[1]
    assert second.linked is True
    assert second.selected is False
    sf.find_recent_voc_work_orders.assert_called_once_with(department="SW")


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
