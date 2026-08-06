from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from ai_work_automation.cutoff import is_after_cutoff
from ai_work_automation.draft_template import build_pms_draft
from ai_work_automation.job_log import JobLogStore
from ai_work_automation.models import DraftContent
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.router import RouteRule, RouteWhen, resolve_targets


class PipelineResult(BaseModel):
    status: str
    case_id: str
    reason: str | None = None
    details: dict[str, Any] | None = None


def _skip_result(case_id: str, reason: str) -> PipelineResult:
    return PipelineResult(status="skipped", reason=reason, case_id=case_id)


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
    acted: list[dict[str, Any]] = []

    for wo in work_orders:
        targets = resolve_targets(wo, routes)
        if "pms" not in targets:
            continue

        if wo.created_date is None:
            continue

        if not is_after_cutoff(wo.created_date, cutoff):
            continue

        draft = build_pms_draft(case, wo)
        if not approve_fn(draft):
            job_log.append(
                {
                    "case_id": case_id,
                    "work_order_id": wo.id,
                    "status": "rejected_by_human",
                }
            )
            continue

        existing_activities = wo.activities or ""
        if "PMS – " in existing_activities and "pms." in existing_activities.lower():
            job_log.append(
                {
                    "case_id": case_id,
                    "work_order_id": wo.id,
                    "status": "skipped",
                    "reason": "already_linked",
                }
            )
            continue

        conn_result = pms.create(draft, project_id=pms_project_id)
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
        acted.append({"work_order_id": wo.id, "url": conn_result.url})

    result = PipelineResult(
        status="success" if acted else "noop",
        case_id=case_id,
        details={"acted": acted},
    )
    job_log.append(result.model_dump())
    return result
