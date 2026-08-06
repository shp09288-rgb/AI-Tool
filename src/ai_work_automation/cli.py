from __future__ import annotations

import os
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


@app.command("select")
def select_case(
    case_id: str,
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
) -> None:
    s = _settings(settings)
    OptInStore(s.opt_in_path).select(case_id)
    typer.echo(f"선택됨: {case_id}")


@app.command("deselect")
def deselect_case(
    case_id: str,
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
) -> None:
    s = _settings(settings)
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
    case_id: str,
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
    yes: bool = typer.Option(False, "--yes", help="Human Gate 자동 승인(테스트용)"),
) -> None:
    s = _settings(settings)
    opt = OptInStore(s.opt_in_path)
    log = JobLogStore(s.job_log_path)
    routes = load_routes(s.routes_path)

    # 환경변수에 없으면 로그인된 sf CLI에서 토큰을 자동으로 가져온다
    sf_instance_url, sf_access_token = resolve_sf_credentials(
        os.environ.get(s.sf_instance_url_env),
        os.environ.get(s.sf_access_token_env),
        s.sf_org_alias,
    )
    sf_client = SalesforceHttpClient(sf_instance_url, sf_access_token)
    pms_http = httpx.Client(base_url=s.pms_base_url, timeout=60.0)
    try:
        sf = SalesforceAdapter(
            client=sf_client,
            cutoff=s.automation_enabled_after,
            wo_fields=[
                "Id",
                "WorkOrderNumber",
                "Subject",
                "CreatedDate",
                "CaseId",
                "Priority",
                s.wo_department_field,
                "VOC_Activities__c",
            ],
        )
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
        )
        typer.echo(result.model_dump_json(ensure_ascii=False, indent=2))
    finally:
        sf_client.close()
        pms_http.close()


if __name__ == "__main__":
    app()
