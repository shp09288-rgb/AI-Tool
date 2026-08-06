from ai_work_automation.models import CaseRecord, DraftContent, WorkOrderRecord


def build_pms_draft(case: CaseRecord, wo: WorkOrderRecord) -> DraftContent:
    title = wo.subject or case.subject
    parts = [
        case.description or "",
        f"Work Order: {wo.work_order_number}",
        f"Priority: {wo.priority or ''}",
    ]
    if wo.sw_version:
        parts.append(f"SW ver.: {wo.sw_version}")
    body = "\n\n".join(p for p in parts if p)
    return DraftContent(title=title, body=body)
