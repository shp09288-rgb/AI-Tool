import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from ai_work_automation.cutoff import is_after_cutoff
from ai_work_automation.draft_template import build_pms_comment, build_pms_draft
from ai_work_automation.idempotency import JsonIdempotencyStore
from ai_work_automation.job_log import JobLogStore
from ai_work_automation.models import DraftContent, WorkOrderRecord
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.router import RouteRule, resolve_targets
from ai_work_automation.settings import PmsCustomFieldsConfig

_ISSUE_LINK_RE = re.compile(r"/issues/(\d+)")


class PipelineResult(BaseModel):
    status: str
    case_id: str
    reason: str | None = None
    details: dict[str, Any] | None = None


def _skip_result(case_id: str, reason: str) -> PipelineResult:
    return PipelineResult(status="skipped", reason=reason, case_id=case_id)


def _issue_ids_in(text: str | None) -> list[str]:
    if not text:
        return []
    return _ISSUE_LINK_RE.findall(text)


def _existing_issue_id(work_orders: list[WorkOrderRecord]) -> str | None:
    """케이스의 워크오더들에 이미 연결된 PMS 이슈 중 가장 최근 것(최대 번호)."""
    ids: list[str] = []
    for wo in work_orders:
        ids.extend(_issue_ids_in(wo.activities))
    if not ids:
        return None
    return max(ids, key=int)


def run_case_automation(
    *,
    case_id: str,
    opt_in: OptInStore,
    job_log: JobLogStore,
    sf: Any,
    routes: list[RouteRule],
    pms: Any,
    cutoff: datetime,
    pms_project_id: int,
    approve_fn: Callable[[DraftContent], bool],
    idempotency: JsonIdempotencyStore,
    dry_run: bool = False,
    issue_type: str | None = None,
    custom_fields_config: PmsCustomFieldsConfig | None = None,
    only_work_order_ids: set[str] | None = None,
) -> PipelineResult:
    if not opt_in.is_selected(case_id):
        result = _skip_result(case_id, "not_selected")
        job_log.append(result.model_dump())
        return result

    case = sf.get_case(case_id)
    if not is_after_cutoff(case.created_date, cutoff):
        result = _skip_result(case_id, "before_cutoff")
        job_log.append(result.model_dump())
        return result

    work_orders = sf.get_work_orders_for_case(case_id)
    existing_issue = _existing_issue_id(work_orders)
    acted: list[dict[str, Any]] = []
    would_post: list[dict[str, Any]] = []

    for wo in work_orders:
        if only_work_order_ids is not None and wo.id not in only_work_order_ids:
            continue

        targets = resolve_targets(wo, routes)
        if "pms" not in targets:
            continue

        if wo.created_date is None:
            continue

        if not is_after_cutoff(wo.created_date, cutoff):
            continue

        if _issue_ids_in(wo.activities):
            job_log.append(
                {
                    "case_id": case_id,
                    "work_order_id": wo.id,
                    "status": "skipped",
                    "reason": "already_linked",
                }
            )
            if not dry_run and not idempotency.has(wo.id, "pms"):
                idempotency.record(wo.id, "pms", ref=None, url=None)
            continue

        if idempotency.has(wo.id, "pms"):
            job_log.append(
                {
                    "case_id": case_id,
                    "work_order_id": wo.id,
                    "status": "skipped",
                    "reason": "already_linked",
                }
            )
            continue

        attachments = sf.get_attachments(wo.id)

        # 같은 케이스에 이미 PMS 이슈가 있으면 신규 생성 대신 그 이슈에 댓글
        if existing_issue is not None:
            comment = build_pms_comment(case, wo, attachments=attachments)

            if dry_run:
                would_post.append(
                    {
                        "work_order_id": wo.id,
                        "target": "pms",
                        "action": "comment",
                        "issue_id": existing_issue,
                        "title": comment.title,
                        "body": comment.body,
                    }
                )
                continue

            if not approve_fn(comment):
                job_log.append(
                    {
                        "case_id": case_id,
                        "work_order_id": wo.id,
                        "status": "rejected_by_human",
                    }
                )
                continue

            conn_result = pms.add_comment(existing_issue, comment.body)
            if not conn_result.ok:
                job_log.append(
                    {
                        "case_id": case_id,
                        "work_order_id": wo.id,
                        "status": "failed",
                        "error": conn_result.error,
                    }
                )
                continue

            line = f"PMS – {conn_result.url} (댓글)"
            sf.append_work_order_activities(wo, line, case_selected=True)
            idempotency.record(wo.id, "pms", ref=conn_result.ref, url=conn_result.url)
            acted.append(
                {"work_order_id": wo.id, "url": conn_result.url, "action": "comment"}
            )
            continue

        draft = build_pms_draft(
            case,
            wo,
            issue_type=issue_type,
            attachments=attachments,
            custom_fields_config=custom_fields_config,
        )

        if dry_run:
            would_post.append(
                {
                    "work_order_id": wo.id,
                    "target": "pms",
                    "action": "create",
                    "issue_type": draft.extra.get("issue_type"),
                    "title": draft.title,
                    "body": draft.body,
                    "custom_fields": draft.extra.get("custom_fields"),
                }
            )
            continue

        if not approve_fn(draft):
            job_log.append(
                {
                    "case_id": case_id,
                    "work_order_id": wo.id,
                    "status": "rejected_by_human",
                }
            )
            continue

        conn_result = pms.create(
            draft,
            project_id=pms_project_id,
            tracker_id=draft.extra.get("tracker_id"),
            custom_fields=draft.extra.get("custom_fields"),
        )
        if not conn_result.ok:
            job_log.append(
                {
                    "case_id": case_id,
                    "work_order_id": wo.id,
                    "status": "failed",
                    "error": conn_result.error,
                }
            )
            continue

        line = f"PMS – {conn_result.url}"
        sf.append_work_order_activities(wo, line, case_selected=True)
        idempotency.record(wo.id, "pms", ref=conn_result.ref, url=conn_result.url)
        acted.append(
            {"work_order_id": wo.id, "url": conn_result.url, "action": "create"}
        )
        # 이후 워크오더는 방금 만든 이슈에 댓글을 달도록 갱신
        existing_issue = conn_result.ref

    if dry_run:
        result = PipelineResult(
            status="dry_run",
            case_id=case_id,
            details={"would_post": would_post},
        )
    else:
        result = PipelineResult(
            status="success" if acted else "noop",
            case_id=case_id,
            details={"acted": acted},
        )
    job_log.append(result.model_dump())
    return result
