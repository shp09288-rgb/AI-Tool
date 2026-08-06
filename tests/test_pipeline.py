from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from ai_work_automation.job_log import JobLogStore
from ai_work_automation.models import ConnectorResult
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.pipeline import PipelineResult, run_case_automation
from ai_work_automation.router import RouteRule, RouteWhen
from ai_work_automation.idempotency import JsonIdempotencyStore


def _routes():
    return [
        RouteRule(
            id="voc-sw-pms",
            when=RouteWhen(recordType="VOC", department="SW"),
            targets=["pms"],
        )
    ]


def test_skip_when_not_selected(tmp_path: Path, sample_case):
    opt = OptInStore(tmp_path / "opt.json")
    log = JobLogStore(tmp_path / "log.jsonl")
    sf = MagicMock()

    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=MagicMock(),
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
        idempotency=JsonIdempotencyStore(tmp_path / "idempotency.json"),
    )

    assert isinstance(result, PipelineResult)
    assert result.status == "skipped"
    assert result.reason == "not_selected"
    sf.get_case.assert_not_called()


def test_happy_path_pms_writeback(tmp_path: Path, sample_case, sample_wo_voc_sw):
    opt = OptInStore(tmp_path / "opt.json")
    opt.select(sample_case.id)
    log = JobLogStore(tmp_path / "log.jsonl")
    sf = MagicMock()
    sf.get_case.return_value = sample_case
    sf.get_work_orders_for_case.return_value = [sample_wo_voc_sw]
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )

    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=pms,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
        idempotency=JsonIdempotencyStore(tmp_path / "idempotency.json"),
    )

    assert result.status == "success"
    sf.append_work_order_activities.assert_called_once()
    args, kwargs = sf.append_work_order_activities.call_args
    assert "PMS – https://pms.example/issues/4710" in args[1]


def test_skip_wo_with_missing_created_date_before_pms_create(
    tmp_path: Path, sample_case, sample_wo_voc_sw
):
    opt = OptInStore(tmp_path / "opt.json")
    opt.select(sample_case.id)
    log = JobLogStore(tmp_path / "log.jsonl")
    sf = MagicMock()
    sf.get_case.return_value = sample_case
    wo_no_date = sample_wo_voc_sw.model_copy(update={"created_date": None})
    sf.get_work_orders_for_case.return_value = [wo_no_date]
    pms = MagicMock()

    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=pms,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
        idempotency=JsonIdempotencyStore(tmp_path / "idempotency.json"),
    )

    assert result.status == "noop"
    pms.create.assert_not_called()
    sf.append_work_order_activities.assert_not_called()


def test_dry_run_builds_draft_but_makes_no_external_calls(
    tmp_path: Path, sample_case, sample_wo_voc_sw
):
    opt = OptInStore(tmp_path / "opt.json")
    opt.select(sample_case.id)
    log = JobLogStore(tmp_path / "log.jsonl")
    sf = MagicMock()
    sf.get_case.return_value = sample_case
    sf.get_work_orders_for_case.return_value = [sample_wo_voc_sw]
    pms = MagicMock()

    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=pms,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: (_ for _ in ()).throw(AssertionError("dry-run에서는 승인 게이트를 호출하면 안 됩니다")),
        idempotency=JsonIdempotencyStore(tmp_path / "idempotency.json"),
        dry_run=True,
    )

    assert result.status == "dry_run"
    pms.create.assert_not_called()
    sf.append_work_order_activities.assert_not_called()
    would_post = result.details["would_post"]
    assert len(would_post) == 1
    assert would_post[0]["work_order_id"] == sample_wo_voc_sw.id
    assert would_post[0]["target"] == "pms"
    assert would_post[0]["title"]
    assert would_post[0]["body"]


def test_skip_when_own_activities_already_has_issue_link(
    tmp_path: Path, sample_case, sample_wo_voc_sw
):
    """실제 데이터처럼 Activities에 URL만 있어도 이미 연결된 것으로 인식해야 한다."""
    opt = OptInStore(tmp_path / "opt.json")
    opt.select(sample_case.id)
    log = JobLogStore(tmp_path / "log.jsonl")
    wo_linked = sample_wo_voc_sw.model_copy(
        update={"activities": "https://pms.parksystems.com/issues/3807"}
    )
    sf = MagicMock()
    sf.get_case.return_value = sample_case
    sf.get_work_orders_for_case.return_value = [wo_linked]
    pms = MagicMock()

    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=pms,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
        idempotency=JsonIdempotencyStore(tmp_path / "idempotency.json"),
    )

    assert result.status == "noop"
    pms.create.assert_not_called()
    pms.add_comment.assert_not_called()
    sf.append_work_order_activities.assert_not_called()


def test_followup_wo_comments_on_existing_issue_instead_of_creating(
    tmp_path: Path, sample_case, sample_wo_voc_sw
):
    """같은 케이스에 이미 PMS 이슈가 연결된 WO가 있으면, 새 WO는 그 이슈에 댓글을 단다."""
    opt = OptInStore(tmp_path / "opt.json")
    opt.select(sample_case.id)
    log = JobLogStore(tmp_path / "log.jsonl")
    wo_old = sample_wo_voc_sw.model_copy(
        update={
            "id": "0WOOLD",
            "work_order_number": "00023044",
            "activities": "https://pms.parksystems.com/issues/3807",
        }
    )
    wo_new = sample_wo_voc_sw.model_copy(
        update={"id": "0WONEW", "work_order_number": "00023100", "activities": ""}
    )
    sf = MagicMock()
    sf.get_case.return_value = sample_case
    sf.get_work_orders_for_case.return_value = [wo_old, wo_new]
    pms = MagicMock()
    pms.add_comment.return_value = ConnectorResult(
        ok=True, ref="3807", url="https://pms.parksystems.com/issues/3807"
    )

    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=pms,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
        idempotency=JsonIdempotencyStore(tmp_path / "idempotency.json"),
    )

    assert result.status == "success"
    pms.create.assert_not_called()
    pms.add_comment.assert_called_once()
    assert pms.add_comment.call_args.args[0] == "3807"
    sf.append_work_order_activities.assert_called_once()
    appended_wo = sf.append_work_order_activities.call_args.args[0]
    assert appended_wo.id == "0WONEW"
    line = sf.append_work_order_activities.call_args.args[1]
    assert "issues/3807" in line
    assert "댓글" in line


def test_dry_run_shows_comment_action_for_followup(
    tmp_path: Path, sample_case, sample_wo_voc_sw
):
    opt = OptInStore(tmp_path / "opt.json")
    opt.select(sample_case.id)
    log = JobLogStore(tmp_path / "log.jsonl")
    wo_old = sample_wo_voc_sw.model_copy(
        update={
            "id": "0WOOLD",
            "activities": "https://pms.parksystems.com/issues/3807",
        }
    )
    wo_new = sample_wo_voc_sw.model_copy(
        update={"id": "0WONEW", "work_order_number": "00023100", "activities": ""}
    )
    sf = MagicMock()
    sf.get_case.return_value = sample_case
    sf.get_work_orders_for_case.return_value = [wo_old, wo_new]
    pms = MagicMock()

    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=pms,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
        idempotency=JsonIdempotencyStore(tmp_path / "idempotency.json"),
        dry_run=True,
    )

    assert result.status == "dry_run"
    pms.add_comment.assert_not_called()
    would_post = result.details["would_post"]
    assert len(would_post) == 1
    assert would_post[0]["action"] == "comment"
    assert would_post[0]["issue_id"] == "3807"
    assert would_post[0]["work_order_id"] == "0WONEW"


def test_create_passes_tracker_id_and_issue_type(
    tmp_path: Path, sample_case, sample_wo_voc_sw
):
    opt = OptInStore(tmp_path / "opt.json")
    opt.select(sample_case.id)
    log = JobLogStore(tmp_path / "log.jsonl")
    sf = MagicMock()
    sf.get_case.return_value = sample_case
    sf.get_work_orders_for_case.return_value = [sample_wo_voc_sw]
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )

    run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=pms,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
        idempotency=JsonIdempotencyStore(tmp_path / "idempotency.json"),
        issue_type="ER",
    )

    assert pms.create.call_args.kwargs["tracker_id"] == 2


def test_skip_when_idempotency_key_exists(
    tmp_path: Path, sample_case, sample_wo_voc_sw
):
    opt = OptInStore(tmp_path / "opt.json")
    opt.select(sample_case.id)
    log = JobLogStore(tmp_path / "log.jsonl")
    store = JsonIdempotencyStore(tmp_path / "idempotency.json")
    store.record(sample_wo_voc_sw.id, "pms", ref="4710", url="https://pms.example/issues/4710")
    sf = MagicMock()
    sf.get_case.return_value = sample_case
    sf.get_work_orders_for_case.return_value = [sample_wo_voc_sw]
    pms = MagicMock()

    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=pms,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
        idempotency=store,
    )

    assert result.status == "noop"
    pms.create.assert_not_called()
    sf.append_work_order_activities.assert_not_called()
