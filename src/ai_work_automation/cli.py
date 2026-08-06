from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
import typer
from dotenv import load_dotenv

from ai_work_automation.connectors.pms import PmsConnector
from ai_work_automation.gate.human import human_approve
from ai_work_automation.idempotency import JsonIdempotencyStore
from ai_work_automation.job_log import JobLogStore
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.pipeline import run_case_automation
from ai_work_automation.router import load_routes
from ai_work_automation.settings import load_settings
from ai_work_automation.sf.adapter import SalesforceAdapter
from ai_work_automation.sf.client import SalesforceHttpClient
from ai_work_automation.sf.token_provider import resolve_sf_credentials

load_dotenv()

app = typer.Typer(help="AI 업무 자동화 CLI (MVP)")


def _settings(path: Path):
    return load_settings(path)


def _require_env(name: str) -> str:
    try:
        return os.environ[name]
    except KeyError as exc:
        raise typer.BadParameter(f"필수 환경변수 누락: {name}") from exc


def _make_sf_adapter(s) -> tuple[SalesforceHttpClient, SalesforceAdapter]:
    # 환경변수에 없으면 로그인된 sf CLI에서 토큰을 자동으로 가져온다
    sf_instance_url, sf_access_token = resolve_sf_credentials(
        os.environ.get(s.sf_instance_url_env),
        os.environ.get(s.sf_access_token_env),
        s.sf_org_alias,
    )
    sf_client = SalesforceHttpClient(sf_instance_url, sf_access_token)
    adapter = SalesforceAdapter(
        client=sf_client,
        cutoff=s.automation_enabled_after,
        wo_fields=[
            "Id",
            "WorkOrderNumber",
            "Subject",
            "CreatedDate",
            "CaseId",
            "Priority",
            "VOC_Title__c",
            "Background_Problem__c",
            s.wo_department_field,
            "VOC_Activities__c",
        ],
    )
    return sf_client, adapter


def _resolve_case_id(s, case: str) -> str:
    """Case Number(예: 00173841)를 Salesforce Id로 변환한다. 이미 Id면 그대로 반환."""
    if not re.fullmatch(r"\d{6,10}", case):
        return case
    sf_client, adapter = _make_sf_adapter(s)
    try:
        case_id = adapter.find_case_id_by_number(case)
    finally:
        sf_client.close()
    if case_id is None:
        raise typer.BadParameter(f"Case Number {case} 를 찾을 수 없습니다")
    return case_id


@app.command("select")
def select_case(
    case: str = typer.Argument(..., help="Case Id 또는 Case Number(예: 00173841)"),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
) -> None:
    s = _settings(settings)
    case_id = _resolve_case_id(s, case)
    OptInStore(s.opt_in_path).select(case_id)
    typer.echo(f"선택됨: {case_id}")


@app.command("deselect")
def deselect_case(
    case: str = typer.Argument(..., help="Case Id 또는 Case Number(예: 00173841)"),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
) -> None:
    s = _settings(settings)
    case_id = _resolve_case_id(s, case)
    OptInStore(s.opt_in_path).deselect(case_id)
    typer.echo(f"선택 해제: {case_id}")


def _list_selected(settings: Path) -> None:
    s = _settings(settings)
    for case_id in OptInStore(s.opt_in_path).list_selected():
        typer.echo(case_id)


@app.command("list-selected")
def list_selected(
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
) -> None:
    _list_selected(settings)


@app.command("list")
def list_alias(
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
) -> None:
    _list_selected(settings)


@app.command("run")
def run(
    case: str = typer.Argument(..., help="Case Id 또는 Case Number(예: 00173841)"),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
    yes: bool = typer.Option(False, "--yes", help="Human Gate 자동 승인(테스트용)"),
    dry_run: bool = typer.Option(
        None,
        "--dry-run/--real",
        help="dry-run 강제 또는 실제 실행 강제. 생략하면 settings.yaml의 dry_run 값을 따름",
    ),
    issue_type: str = typer.Option(
        None,
        "--type",
        help="PMS 이슈 타입(sr|er). 생략하면 제목으로 자동 추정",
    ),
) -> None:
    s = _settings(settings)
    opt = OptInStore(s.opt_in_path)
    log = JobLogStore(s.job_log_path)
    routes = load_routes(s.routes_path)

    resolved_type: str | None = None
    if issue_type is not None:
        resolved_type = issue_type.upper()
        if resolved_type not in ("SR", "ER"):
            raise typer.BadParameter("--type 은 sr 또는 er 이어야 합니다")

    case_id = _resolve_case_id(s, case)

    sf_client, sf = _make_sf_adapter(s)
    pms_http = httpx.Client(base_url=s.pms_base_url, timeout=60.0)
    try:
        pms = PmsConnector(
            client=pms_http,
            api_key=_require_env(s.pms_api_key_env),
            base_url=s.pms_base_url,
        )
        idempotency = JsonIdempotencyStore(s.idempotency_path)

        approve_fn = (lambda _draft: True) if yes else human_approve
        result = run_case_automation(
            case_id=case_id,
            opt_in=opt,
            job_log=log,
            sf=sf,
            routes=routes,
            pms=pms,
            cutoff=s.automation_enabled_after,
            pms_project_id=s.pms_project_id,
            approve_fn=approve_fn,
            idempotency=idempotency,
            dry_run=s.dry_run if dry_run is None else dry_run,
            issue_type=resolved_type,
        )
        typer.echo(result.model_dump_json(ensure_ascii=False, indent=2))
    finally:
        sf_client.close()
        pms_http.close()


if __name__ == "__main__":
    app()
