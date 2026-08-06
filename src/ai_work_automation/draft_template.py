"""PMS(Redmine) 초안 생성.

파크시스템스 PMS는 CKEditor 기반이라 본문/댓글이 HTML 형식이다.
트래커: SR(id=1) = 문제/버그 신고, ER(id=2) = 기능 개선·추가 요청.
"""

import html

from ai_work_automation.models import CaseRecord, DraftContent, WorkOrderRecord

TRACKER_ID = {"SR": 1, "ER": 2}

_SR_HEADER = (
    "<p>[상황/문제 설명]<br />\n"
    "* 발생 조건, Sample Tiff File(보유하고 있는 경우 추가), Log File(보유하고 있는 경우 추가)</p>\n"
)
_ER_HEADER = (
    "<p>[요청 배경]<br />\n"
    "* 요청하는 기능에 대한 구체적인 설명</p>\n"
)

# 제목에 개선·추가 '요청' 성격의 단어가 있으면 ER, 그 외(현상/오류 신고)는 SR
_ER_KEYWORDS = ("요청", "개선", "추가")


def classify_issue_type(title: str) -> str:
    if any(keyword in title for keyword in _ER_KEYWORDS):
        return "ER"
    return "SR"


def _resolve_title(case: CaseRecord, wo: WorkOrderRecord) -> str:
    return wo.voc_title or wo.subject or case.subject


def _to_html_paragraphs(text: str) -> str:
    paragraphs = [
        f"<p>{html.escape(line.strip())}</p>"
        for line in text.splitlines()
        if line.strip()
    ]
    return "\n".join(paragraphs)


def build_pms_draft(
    case: CaseRecord,
    wo: WorkOrderRecord,
    issue_type: str | None = None,
) -> DraftContent:
    title = _resolve_title(case, wo)
    resolved_type = issue_type or classify_issue_type(title)
    header = _ER_HEADER if resolved_type == "ER" else _SR_HEADER

    parts = [header]
    if case.description:
        parts.append(_to_html_paragraphs(case.description))
    footer_lines = [f"Salesforce Work Order: {wo.work_order_number}"]
    if wo.priority:
        footer_lines.append(f"Priority: {wo.priority}")
    if wo.sw_version:
        footer_lines.append(f"SW ver.: {wo.sw_version}")
    parts.append(_to_html_paragraphs("\n".join(footer_lines)))

    return DraftContent(
        title=title,
        body="\n<p>&nbsp;</p>\n".join(parts),
        extra={"tracker_id": TRACKER_ID[resolved_type], "issue_type": resolved_type},
    )


def build_pms_comment(case: CaseRecord, wo: WorkOrderRecord) -> DraftContent:
    """후속 워크오더용 댓글. 신규 이슈 대신 기존 이슈에 추가 작성한다."""
    title = _resolve_title(case, wo)
    parts = [
        _to_html_paragraphs(
            f"[후속 워크오더 등록] {wo.work_order_number}\n{title}\n"
            "이전 조치로 해결되지 않아 후속 워크오더가 등록되었습니다."
        )
    ]
    if case.description:
        parts.append(_to_html_paragraphs(case.description))
    return DraftContent(title=title, body="\n<p>&nbsp;</p>\n".join(parts))
