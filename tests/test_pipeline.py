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
