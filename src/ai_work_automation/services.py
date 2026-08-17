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
    case_owner_name: str = ""
    linked: bool
    selected: bool


class CaseScanGroup(BaseModel):
    case_id: str
    case_number: str
    case_subject: str
    case_owner_name: str = ""
    unlinked: list[ScanRow]
    linked_count: int = 0


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
                case_owner_name=candidate.case_owner_name,
                linked=bool(_issue_ids_in(wo.activities)),
                selected=opt_in.is_selected(wo.case_id or ""),
            )
        )
    return rows


def _case_group_key(row: ScanRow) -> str:
    return row.case_id if row.case_id else row.case_number


def _newest_unlinked_date(group: CaseScanGroup) -> str:
    return max((row.created_date for row in group.unlinked), default="")


def group_unlinked_by_case(rows: list[ScanRow]) -> list[CaseScanGroup]:
    """Group scan rows by case; unlinked only in .unlinked; sort by newest unlinked created_date desc."""
    buckets: dict[str, list[ScanRow]] = {}
    for row in rows:
        buckets.setdefault(_case_group_key(row), []).append(row)

    groups: list[CaseScanGroup] = []
    for bucket in buckets.values():
        unlinked = [row for row in bucket if not row.linked]
        if not unlinked:
            continue
        meta = next((row for row in bucket if not row.linked), bucket[0])
        groups.append(
            CaseScanGroup(
                case_id=meta.case_id,
                case_number=meta.case_number,
                case_subject=meta.case_subject,
                case_owner_name=meta.case_owner_name,
                unlinked=unlinked,
                linked_count=sum(1 for row in bucket if row.linked),
            )
        )

    groups.sort(key=_newest_unlinked_date, reverse=True)
    return groups


def case_group_label(group: CaseScanGroup, *, title_max: int = 40) -> str:
    """Return '{case_number} · 미연동 {k}건 · {title}' for multiselect."""
    newest = max(group.unlinked, key=lambda row: row.created_date or "", default=None)
    title = (newest.title if newest else group.case_subject)[:title_max]
    return f"{group.case_number} · 미연동 {len(group.unlinked)}건 · {title}"


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
