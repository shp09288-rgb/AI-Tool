from ai_work_automation.gate.human import human_approve
from ai_work_automation.models import DraftContent


def test_approve_yes():
    draft = DraftContent(title="t", body="b")
    assert human_approve(draft, prompt_fn=lambda _: "y") is True


def test_reject_no():
    draft = DraftContent(title="t", body="b")
    assert human_approve(draft, prompt_fn=lambda _: "n") is False
