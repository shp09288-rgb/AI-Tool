from ai_work_automation.draft_template import (
    build_pms_comment,
    build_pms_draft,
    classify_issue_type,
)


def test_classify_issue_type_er_when_title_is_request():
    assert classify_issue_type("공통 / NX / [PMS] Motor 축 SOL Alarm 분기 요청") == "ER"


def test_classify_issue_type_sr_for_problem_report():
    assert classify_issue_type("AST / NX-TSH600 / [PMS] Servo Off 시 Side air 안꺼짐 발생") == "SR"


def test_title_prefers_voc_title(sample_case, sample_wo_voc_sw):
    wo = sample_wo_voc_sw.model_copy(
        update={"voc_title": "VOC 제목입니다", "subject": "서브젝트"}
    )
    draft = build_pms_draft(sample_case, wo, issue_type="SR")
    assert draft.title == "VOC 제목입니다"


def test_title_falls_back_to_case_subject(sample_case, sample_wo_voc_sw):
    wo = sample_wo_voc_sw.model_copy(update={"voc_title": None, "subject": None})
    draft = build_pms_draft(sample_case, wo, issue_type="SR")
    assert draft.title == sample_case.subject


def test_sr_draft_uses_sr_template_and_tracker(sample_case, sample_wo_voc_sw):
    draft = build_pms_draft(sample_case, sample_wo_voc_sw, issue_type="SR")
    assert "[상황/문제 설명]" in draft.body
    assert draft.extra["tracker_id"] == 1
    assert draft.extra["issue_type"] == "SR"
    assert "상세 설명" in draft.body  # case description 포함
    assert sample_wo_voc_sw.work_order_number in draft.body


def test_er_draft_uses_er_template_and_tracker(sample_case, sample_wo_voc_sw):
    draft = build_pms_draft(sample_case, sample_wo_voc_sw, issue_type="ER")
    assert "[요청 배경]" in draft.body
    assert draft.extra["tracker_id"] == 2
    assert draft.extra["issue_type"] == "ER"


def test_draft_auto_classifies_when_type_not_given(sample_case, sample_wo_voc_sw):
    wo = sample_wo_voc_sw.model_copy(update={"voc_title": "[PMS] 기능 추가 요청"})
    draft = build_pms_draft(sample_case, wo)
    assert draft.extra["issue_type"] == "ER"


def test_body_escapes_html(sample_case, sample_wo_voc_sw):
    case = sample_case.model_copy(update={"description": "값이 <100 인 경우 & 오류"})
    draft = build_pms_draft(case, sample_wo_voc_sw, issue_type="SR")
    assert "<100" not in draft.body
    assert "&lt;100" in draft.body


def test_comment_mentions_followup_work_order(sample_case, sample_wo_voc_sw):
    wo = sample_wo_voc_sw.model_copy(update={"voc_title": "후속 확인 요청"})
    comment = build_pms_comment(sample_case, wo)
    assert wo.work_order_number in comment.body
    assert "후속" in comment.body
    assert "상세 설명" in comment.body  # case description 포함
