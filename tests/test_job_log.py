from pathlib import Path

from ai_work_automation.job_log import JobLogStore


def test_append_and_read(tmp_path: Path):
    store = JobLogStore(tmp_path / "job.jsonl")
    store.append({"case_id": "500A", "status": "skipped", "reason": "not_selected"})
    rows = store.read_all()
    assert len(rows) == 1
    assert rows[0]["reason"] == "not_selected"
