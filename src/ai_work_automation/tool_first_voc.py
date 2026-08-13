from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from ai_work_automation.draft_template import (
    build_pms_comment,
    build_pms_draft,
    compact_pms_html,
)
from ai_work_automation.models import CaseRecord, WorkOrderRecord
from ai_work_automation.pipeline import _existing_issue_id, _issue_ids_in

Mode = Literal["new_case", "existing_case"]
PmsAction = Literal["create", "comment", "skip"]


@dataclass
class ToolFirstVocInput:
    mode: Mode
    title: str
    department: str = "SW"
    pms_html_body: str = ""
    case_number: str | None = None
    asset_id: str | None = None
    asset_sid: str | None = None
    sf_summary: str = ""


@dataclass
class ToolFirstVocResult:
    ok: bool
    dry_run: bool
    case_id: str | None
    work_order_id: str | None
    pms_action: PmsAction | None
    pms_issue_id: str | None
    pms_url: str | None
    message: str
    links: dict[str, str] = field(default_factory=dict)


def _result(
    *,
    ok: bool,
    dry_run: bool,
    message: str,
    case_id: str | None = None,
    work_order_id: str | None = None,
    pms_action: PmsAction | None = None,
    pms_issue_id: str | None = None,
    pms_url: str | None = None,
    links: dict[str, str] | None = None,
) -> ToolFirstVocResult:
    return ToolFirstVocResult(
        ok=ok,
        dry_run=dry_run,
        case_id=case_id,
        work_order_id=work_order_id,
        pms_action=pms_action,
        pms_issue_id=pms_issue_id,
        pms_url=pms_url,
        message=message,
        links=links or {},
    )


def _existing_pms_issue(
    case: CaseRecord, work_orders: list[WorkOrderRecord]
) -> str | None:
    ids = list(_issue_ids_in(case.activities))
    wo_issue = _existing_issue_id(work_orders)
    if wo_issue:
        ids.append(wo_issue)
    if not ids:
        return None
    return max(ids, key=int)


def _case_fields(payload: ToolFirstVocInput) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "Subject": payload.title,
        "Description": payload.sf_summary,
    }
    if payload.asset_id:
        fields["AssetId"] = payload.asset_id
    return fields


def _wo_fields(payload: ToolFirstVocInput, settings: Any) -> dict[str, Any]:
    dept_field = getattr(settings, "wo_department_field", "Relevant_Department__c")
    fields: dict[str, Any] = {
        "Subject": payload.title,
        dept_field: payload.department,
    }
    if payload.sf_summary:
        fields["Description"] = payload.sf_summary
    if payload.asset_id:
        fields["AssetId"] = payload.asset_id
    if payload.asset_sid:
        fields["Asset_SID__c"] = payload.asset_sid
    return fields


def _synthetic_case(case_id: str, payload: ToolFirstVocInput) -> CaseRecord:
    return CaseRecord(
        id=case_id,
        case_number=payload.case_number or "",
        subject=payload.title,
        created_date=datetime.now(timezone.utc),
        description=payload.sf_summary or None,
        asset_id=payload.asset_id,
    )


def _synthetic_wo(wo_id: str, case_id: str, payload: ToolFirstVocInput) -> WorkOrderRecord:
    return WorkOrderRecord(
        id=wo_id,
        work_order_number="",
        record_type="VOC",
        relevant_department=payload.department,
        subject=payload.title,
        voc_title=payload.title,
        background=payload.sf_summary or None,
        activities="",
        case_id=case_id,
        created_date=datetime.now(timezone.utc),
    )


def _pms_body(payload: ToolFirstVocInput) -> str:
    return compact_pms_html(payload.pms_html_body) if payload.pms_html_body else ""


def _links(sf: Any, case_id: str | None, wo_id: str | None, pms_url: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    instance = getattr(getattr(sf, "client", None), "instance_url", None)
    if instance and case_id:
        out["case"] = f"{str(instance).rstrip('/')}/{case_id}"
    if instance and wo_id:
        out["work_order"] = f"{str(instance).rstrip('/')}/{wo_id}"
    if pms_url:
        out["pms"] = pms_url
    return out


def run_tool_first_voc(
    sf: Any,
    pms: Any,
    settings: Any,
    payload: ToolFirstVocInput,
    *,
    dry_run: bool,
    approved: bool,
) -> ToolFirstVocResult:
    if not approved:
        return _result(
            ok=False,
            dry_run=dry_run,
            message="승인이 필요합니다. 미리보기만 확인한 뒤 승인 실행하세요.",
            pms_action="skip",
        )

    case: CaseRecord | None = None
    existing_issue: str | None = None

    if payload.mode == "existing_case":
        if not payload.case_number:
            return _result(ok=False, dry_run=dry_run, message="기존 Case 번호가 필요합니다.")
        case = sf.find_case_by_number(payload.case_number)
        if case is None:
            return _result(
                ok=False,
                dry_run=dry_run,
                message=f"Case {payload.case_number}을(를) 찾을 수 없습니다.",
            )
        existing_wos = sf.get_work_orders_for_case(case.id)
        existing_issue = _existing_pms_issue(case, existing_wos)

    pms_action: PmsAction = "comment" if existing_issue else "create"

    if dry_run:
        return _result(
            ok=True,
            dry_run=True,
            case_id=case.id if case else None,
            pms_action=pms_action,
            pms_issue_id=existing_issue,
            pms_url=None,
            message="dry_run: SF/PMS 쓰기를 생략합니다.",
            links=_links(sf, case.id if case else None, None, None),
        )

    if payload.mode == "new_case":
        case_id = sf.create_case(_case_fields(payload))
        case = _synthetic_case(case_id, payload)
    else:
        assert case is not None
        case_id = case.id

    wo_id = sf.create_voc_work_order(
        case_id=case_id, fields=_wo_fields(payload, settings)
    )
    wo = _synthetic_wo(wo_id, case_id, payload)
    body = _pms_body(payload)

    if existing_issue:
        comment = build_pms_comment(case, wo)
        notes = body or comment.body
        conn = pms.add_comment(existing_issue, notes)
        if not conn.ok:
            return _result(
                ok=False,
                dry_run=False,
                case_id=case_id,
                work_order_id=wo_id,
                pms_action="comment",
                pms_issue_id=existing_issue,
                message=f"PMS 댓글 실패: {conn.error}",
                links=_links(sf, case_id, wo_id, None),
            )
        line = f"PMS – {conn.url} (댓글)"
        sf.append_work_order_activities(wo, line, case_selected=True)
        return _result(
            ok=True,
            dry_run=False,
            case_id=case_id,
            work_order_id=wo_id,
            pms_action="comment",
            pms_issue_id=existing_issue,
            pms_url=conn.url,
            message="기존 PMS 이슈에 댓글을 등록했습니다.",
            links=_links(sf, case_id, wo_id, conn.url),
        )

    draft = build_pms_draft(
        case,
        wo,
        custom_fields_config=getattr(settings, "pms_custom_fields", None),
    )
    updates: dict[str, Any] = {"title": payload.title}
    if body:
        updates["body"] = body
    draft = draft.model_copy(update=updates)
    conn = pms.create(
        draft,
        project_id=settings.pms_project_id,
        tracker_id=draft.extra.get("tracker_id"),
        custom_fields=draft.extra.get("custom_fields"),
    )
    if not conn.ok:
        return _result(
            ok=False,
            dry_run=False,
            case_id=case_id,
            work_order_id=wo_id,
            pms_action="create",
            message=f"PMS 이슈 생성 실패: {conn.error}",
            links=_links(sf, case_id, wo_id, None),
        )
    line = f"PMS – {conn.url}"
    sf.append_work_order_activities(wo, line, case_selected=True)
    return _result(
        ok=True,
        dry_run=False,
        case_id=case_id,
        work_order_id=wo_id,
        pms_action="create",
        pms_issue_id=conn.ref,
        pms_url=conn.url,
        message="PMS 이슈를 생성했습니다.",
        links=_links(sf, case_id, wo_id, conn.url),
    )
