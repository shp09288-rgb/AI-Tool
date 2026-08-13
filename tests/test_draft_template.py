from ai_work_automation.draft_template import (
    build_custom_fields,
    build_pms_comment,
    build_pms_draft,
    classify_issue_type,
    compact_pms_html,
)
from ai_work_automation.models import AttachmentRef
from ai_work_automation.settings import PmsCustomFieldsConfig

_CF_CONFIG = PmsCustomFieldsConfig(
    defaults={"30": "414", "15": "81", "33": "564"},
    customer_field="17",
    customer_detail_field="29",
    customer_map={"LGD": "131", "SDC": "132", "공통": "143"},
)


def test_custom_fields_include_defaults():
    fields = build_custom_fields("아무 제목", _CF_CONFIG)
    as_dict = {f["id"]: f["value"] for f in fields}
    assert as_dict[30] == "414"
    assert as_dict[15] == "81"
    assert as_dict[33] == "564"


def test_custom_fields_detect_customer_and_detail_from_title():
    fields = build_custom_fields(
        "SDC A6 / NX-TSH2326 #1 / [PMS] Shutter 이동시 오류", _CF_CONFIG
    )
    as_dict = {f["id"]: f["value"] for f in fields}
    assert as_dict[17] == "132"  # SDC
    assert as_dict[29] == "A6"


def test_custom_fields_customer_without_detail():
    fields = build_custom_fields(
        "공통 / NX-TSH1518, 2225, 2326 / [PMS] Alarm 분기 요청", _CF_CONFIG
    )
    as_dict = {f["id"]: f["value"] for f in fields}
    assert as_dict[17] == "143"  # 공통
    assert 29 not in as_dict


def test_custom_fields_unknown_customer_skips_customer_field():
    fields = build_custom_fields("AST / NX-TSH600 / [PMS] Servo Off", _CF_CONFIG)
    as_dict = {f["id"]: f["value"] for f in fields}
    assert 17 not in as_dict


def test_draft_includes_custom_fields_in_extra(sample_case, sample_wo_voc_sw):
    wo = sample_wo_voc_sw.model_copy(
        update={"voc_title": "SDC A6 / NX-TSH2326 / [PMS] 오류 발생"}
    )
    draft = build_pms_draft(sample_case, wo, issue_type="SR", custom_fields_config=_CF_CONFIG)
    as_dict = {f["id"]: f["value"] for f in draft.extra["custom_fields"]}
    assert as_dict[30] == "414"
    assert as_dict[17] == "132"
    assert as_dict[29] == "A6"


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


def test_body_uses_compact_line_height(sample_case, sample_wo_voc_sw):
    """PMS CKEditor 본문은 줄마다 <p>라 기본 여백이 커서, 1.2배로 고정한다."""
    wo = sample_wo_voc_sw.model_copy(
        update={"background": "현상\n1. 첫 줄\n2. 둘째 줄"}
    )
    draft = build_pms_draft(sample_case, wo, issue_type="SR")
    assert 'style="margin:0;line-height:1.2"' in draft.body
    assert draft.body.count('style="margin:0;line-height:1.2"') >= 3
    comment = build_pms_comment(sample_case, wo)
    assert 'style="margin:0;line-height:1.2"' in comment.body


def test_compact_pms_html_rewrites_quill_paragraphs():
    raw = "<p>현상</p><p style=\"color:red\">강조</p>"
    out = compact_pms_html(raw)
    assert out.startswith('<p style="margin:0;line-height:1.2">현상</p>')
    assert 'style="margin:0;line-height:1.2;color:red"' in out


def test_comment_mentions_followup_work_order(sample_case, sample_wo_voc_sw):
    wo = sample_wo_voc_sw.model_copy(update={"voc_title": "후속 확인 요청"})
    comment = build_pms_comment(sample_case, wo)
    assert wo.work_order_number in comment.body
    assert "후속" in comment.body
    assert "상세 설명" in comment.body  # background 없으면 case description 사용


def test_comment_prefers_wo_background_over_case_description(sample_case, sample_wo_voc_sw):
    wo = sample_wo_voc_sw.model_copy(
        update={"background": "디버깅 버전 적용 후에도 현상 재발"}
    )
    comment = build_pms_comment(sample_case, wo)
    assert "디버깅 버전 적용 후에도 현상 재발" in comment.body
    assert "상세 설명" not in comment.body  # case description 대신 background


def test_draft_prefers_wo_background_over_case_description(sample_case, sample_wo_voc_sw):
    wo = sample_wo_voc_sw.model_copy(update={"background": "스테이지 구동 불가"})
    draft = build_pms_draft(sample_case, wo, issue_type="SR")
    assert "스테이지 구동 불가" in draft.body
    assert "상세 설명" not in draft.body


def test_comment_includes_attachment_links(sample_case, sample_wo_voc_sw):
    attachments = [
        AttachmentRef(
            title="Sample chuck 이염.png",
            url="https://parksystems.my.salesforce.com/sfc/servlet.shepherd/document/download/069DOC1",
        )
    ]
    comment = build_pms_comment(sample_case, sample_wo_voc_sw, attachments=attachments)
    assert "첨부 파일" in comment.body
    assert 'href="https://parksystems.my.salesforce.com/sfc/servlet.shepherd/document/download/069DOC1"' in comment.body
    assert "Sample chuck 이염.png" in comment.body


def test_draft_includes_attachment_links(sample_case, sample_wo_voc_sw):
    attachments = [AttachmentRef(title="log.zip", url="https://sf.example/dl/069DOC2")]
    draft = build_pms_draft(sample_case, sample_wo_voc_sw, issue_type="SR", attachments=attachments)
    assert "첨부 파일" in draft.body
    assert 'href="https://sf.example/dl/069DOC2"' in draft.body


def test_no_attachment_section_when_empty(sample_case, sample_wo_voc_sw):
    comment = build_pms_comment(sample_case, sample_wo_voc_sw, attachments=[])
    assert "첨부 파일" not in comment.body
