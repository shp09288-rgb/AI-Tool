"""CLI와 웹 UI가 공유하는 조회 서비스 (스캔, 상태)."""

from typing import Any

from pydantic import BaseModel

from ai_work_automation.opt_in import OptInStore
from ai_work_automation.pipeline import _issue_ids_in


class ScanRow(BaseModel):
    case_id: str
    case_number: str
    case_subject: str
    work_order_id: str
    work_order_number: str
    title: str
    created_date: str
    asset_name: str = ""
    asset_sid: str = ""
    status: str = ""
    owner_name: str = ""
    linked: bool
    selected: bool


class StatusRow(BaseModel):
    case_id: str
    work_order_id: str
    work_order_number: str
    issue_id: str
    issue_url: str
    issue_subject: str
    issue_status: str
    issue_updated_on: str


def scan_candidates(
    sf: Any,
    opt_in: OptInStore,
    department: str = "SW",
    asset_contains: list[str] | None = None,
    sid_contains: list[str] | None = None,
    status_in: list[str] | None = None,
    owner_contains: str = "",
) -> list[ScanRow]:
    """컷오프 이후 생성된 VOC+부서 워크오더 목록 (PMS 연동 여부/선택 여부 포함)."""
    rows: list[ScanRow] = []
    candidates = sf.find_recent_voc_work_orders(
        department=department,
        asset_contains=asset_contains or [],
        sid_contains=sid_contains or [],
        status_in=status_in or [],
        owner_contains=owner_contains,
    )
    for candidate in candidates:
        wo = candidate.work_order
        rows.append(
            ScanRow(
                case_id=wo.case_id or "",
                case_number=candidate.case_number,
                case_subject=candidate.case_subject,
                work_order_id=wo.id,
                work_order_number=wo.work_order_number,
                title=wo.voc_title or wo.subject or candidate.case_subject,
                created_date=wo.created_date.isoformat() if wo.created_date else "",
                asset_name=candidate.asset_name,
                asset_sid=candidate.asset_sid,
                status=candidate.status,
                owner_name=candidate.owner_name,
                linked=bool(_issue_ids_in(wo.activities)),
                selected=opt_in.is_selected(wo.case_id or ""),
            )
        )
    return rows


def status_overview(sf: Any, pms: Any, opt_in: OptInStore) -> list[StatusRow]:
    """옵트인된 케이스들의 연결된 PMS 이슈 상태를 조회한다."""
    rows: list[StatusRow] = []
    for case_id in opt_in.list_selected():
        for wo in sf.get_work_orders_for_case(case_id):
            for issue_id in _issue_ids_in(wo.activities):
                result = pms.get_issue(issue_id)
                if not result.ok:
                    rows.append(
                        StatusRow(
                            case_id=case_id,
                            work_order_id=wo.id,
                            work_order_number=wo.work_order_number,
                            issue_id=issue_id,
                            issue_url=result.url or "",
                            issue_subject="(조회 실패)",
                            issue_status=result.error or "오류",
                            issue_updated_on="",
                        )
                    )
                    continue
                issue = (result.raw or {}).get("issue", {})
                rows.append(
                    StatusRow(
                        case_id=case_id,
                        work_order_id=wo.id,
                        work_order_number=wo.work_order_number,
                        issue_id=issue_id,
                        issue_url=result.url or "",
                        issue_subject=issue.get("subject") or "",
                        issue_status=(issue.get("status") or {}).get("name") or "",
                        issue_updated_on=issue.get("updated_on") or "",
                    )
                )
    return rows
