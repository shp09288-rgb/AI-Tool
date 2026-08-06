from ai_work_automation.draft_template import build_pms_draft


def test_build_pms_draft_uses_case_subject(sample_case, sample_wo_voc_sw):
    draft = build_pms_draft(sample_case, sample_wo_voc_sw)
    assert draft.title == sample_case.subject
    assert "상세" in draft.body or (sample_case.description or "") in draft.body
