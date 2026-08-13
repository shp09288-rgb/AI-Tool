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
from ai_work_automation.services import scan_candidates, status_overview
from ai_work_automation.settings import load_settings
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


def _make_sf_adapter(s):
    # 지연 임포트: Streamlit이 adapter를 reload한 뒤에도 최신 클래스를 쓰게 함
    from ai_work_automation.sf.adapter import SalesforceAdapter

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
        case_activities_field=s.field_report.case_activities_field,
        technical_service_record_type_id=s.field_report.technical_service_record_type_id,
        voc_record_type_id=s.field_report.voc_record_type_id,
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


@app.command("scan")
def scan(
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
    department: str = typer.Option("SW", "--department", help="Relevant Department 값"),
) -> None:
    """컷오프 이후 생성된 VOC 워크오더 중 PMS 미연동 후보를 나열한다."""
    s = _settings(settings)
    opt = OptInStore(s.opt_in_path)
    sf_client, sf = _make_sf_adapter(s)
    try:
        rows = scan_candidates(
            sf,
            opt,
            department=department,
            asset_contains=s.scan_filters.asset_contains,
            sid_contains=s.scan_filters.sid_contains,
            status_in=s.scan_filters.status_in,
            owner_contains=s.scan_filters.owner_contains,
        )
    finally:
        sf_client.close()

    if not rows:
        typer.echo("컷오프 이후 생성된 해당 부서 VOC 워크오더가 없습니다.")
        return
    for row in rows:
        mark_link = "연동됨" if row.linked else "미연동"
        mark_sel = "선택됨" if row.selected else "  -  "
        typer.echo(
            f"{row.case_number}  WO {row.work_order_number}  [{mark_link}] [{mark_sel}]  "
            f"{row.created_date[:10]}  {row.title}"
        )


@app.command("status")
def status(
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings"),
) -> None:
    """옵트인된 케이스들의 연결된 PMS 이슈 상태를 보여준다."""
    s = _settings(settings)
    opt = OptInStore(s.opt_in_path)
    sf_client, sf = _make_sf_adapter(s)
    pms_http = httpx.Client(base_url=s.pms_base_url, timeout=60.0)
    try:
        pms = PmsConnector(
            client=pms_http,
            api_key=_require_env(s.pms_api_key_env),
            base_url=s.pms_base_url,
        )
        rows = status_overview(sf, pms, opt)
    finally:
        sf_client.close()
        pms_http.close()

    if not rows:
        typer.echo("옵트인된 케이스에 연결된 PMS 이슈가 없습니다.")
        return
    for row in rows:
        typer.echo(
            f"WO {row.work_order_number}  PMS #{row.issue_id} [{row.issue_status}]  "
            f"{row.issue_updated_on[:10]}  {row.issue_subject}"
        )


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
            custom_fields_config=s.pms_custom_fields,
        )
        typer.echo(result.model_dump_json(ensure_ascii=False, indent=2))
    finally:
        sf_client.close()
        pms_http.close()


if __name__ == "__main__":
    app()
