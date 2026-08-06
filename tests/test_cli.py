from pathlib import Path

from typer.testing import CliRunner

from ai_work_automation.cli import app


def _write_settings(tmp_path: Path) -> Path:
    opt_in_path = tmp_path / "opt_in.json"
    job_log_path = tmp_path / "job_log.jsonl"
    routes_path = tmp_path / "routes.yaml"
    routes_path.write_text("routes: []\n", encoding="utf-8")
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        f"""
automation_enabled_after: "2026-12-01T00:00:00+09:00"
opt_in_path: {opt_in_path.as_posix()}
job_log_path: {job_log_path.as_posix()}
idempotency_path: { (tmp_path / "idempotency.json").as_posix() }
routes_path: {routes_path.as_posix()}
pms_base_url: https://pms.parksystems.com
pms_project_id: 9
wo_department_field: Department__c
dry_run: true
""".strip(),
        encoding="utf-8",
    )
    return settings_file


def test_select_deselect_and_list_selected(tmp_path: Path):
    runner = CliRunner()
    settings_file = _write_settings(tmp_path)

    result = runner.invoke(
        app,
        ["select", "500CASE1", "--settings", str(settings_file)],
    )
    assert result.exit_code == 0, result.output
    assert "선택됨: 500CASE1" in result.output

    result = runner.invoke(
        app,
        ["list-selected", "--settings", str(settings_file)],
    )
    assert result.exit_code == 0, result.output
    assert result.output.strip().splitlines() == ["500CASE1"]

    result = runner.invoke(
        app,
        ["deselect", "500CASE1", "--settings", str(settings_file)],
    )
    assert result.exit_code == 0, result.output
    assert "선택 해제: 500CASE1" in result.output


def test_run_wires_dependencies_and_prints_result(tmp_path: Path, monkeypatch):
    from ai_work_automation import cli

    runner = CliRunner()
    settings_file = _write_settings(tmp_path)
    seen: dict[str, object] = {}

    monkeypatch.setenv("SF_INSTANCE_URL", "https://example.salesforce.com")
    monkeypatch.setenv("SF_ACCESS_TOKEN", "sf-token")
    monkeypatch.setenv("PMS_API_KEY", "pms-token")

    class FakeResponse:
        def model_dump_json(self, *, ensure_ascii: bool, indent: int) -> str:
            seen["dump_args"] = (ensure_ascii, indent)
            return '{"status":"success","case_id":"500CASE1"}'

    class FakeSFClient:
        def __init__(self, instance_url: str, access_token: str) -> None:
            seen["sf_client"] = (instance_url, access_token)

        def close(self) -> None:
            seen["sf_client_closed"] = True

    class FakeSFAdapter:
        def __init__(self, *, client, cutoff, wo_fields=None) -> None:
            seen["sf_adapter"] = (client, cutoff, wo_fields)

    class FakeHTTPXClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            seen["httpx_client"] = (base_url, timeout)

        def close(self) -> None:
            seen["httpx_client_closed"] = True

    class FakePmsConnector:
        def __init__(self, *, client, api_key: str, base_url: str) -> None:
            seen["pms_connector"] = (client, api_key, base_url)

    def fake_run_case_automation(**kwargs):
        seen["run_kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr(cli, "SalesforceHttpClient", FakeSFClient)
    monkeypatch.setattr(cli, "SalesforceAdapter", FakeSFAdapter)
    monkeypatch.setattr(cli.httpx, "Client", FakeHTTPXClient)
    monkeypatch.setattr(cli, "PmsConnector", FakePmsConnector)
    monkeypatch.setattr(cli, "run_case_automation", fake_run_case_automation)

    result = runner.invoke(
        app,
        ["run", "500CASE1", "--settings", str(settings_file), "--yes"],
    )

    assert result.exit_code == 0, result.output
    assert '"status":"success"' in result.output
    assert seen["sf_client"] == ("https://example.salesforce.com", "sf-token")
    assert seen["pms_connector"][1:] == ("pms-token", "https://pms.parksystems.com")
    assert "Department__c" in seen["sf_adapter"][2]
    assert "VOC_Title__c" in seen["sf_adapter"][2]
    assert "Background_Problem__c" in seen["sf_adapter"][2]
    assert seen["run_kwargs"]["idempotency"].path == tmp_path / "idempotency.json"
    assert seen["run_kwargs"]["case_id"] == "500CASE1"
    assert seen["run_kwargs"]["pms_project_id"] == 9
    assert seen["run_kwargs"]["approve_fn"] is not None
    assert seen["run_kwargs"]["dry_run"] is True  # settings.yaml의 dry_run: true 반영


def _patch_run_fakes(monkeypatch, seen: dict):
    from ai_work_automation import cli

    class FakeResponse:
        def model_dump_json(self, *, ensure_ascii: bool, indent: int) -> str:
            return '{"status":"dry_run"}'

    class FakeSFClient:
        def __init__(self, instance_url: str, access_token: str) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeSFAdapter:
        def __init__(self, *, client, cutoff, wo_fields=None) -> None:
            pass

        def find_case_id_by_number(self, case_number: str) -> str | None:
            seen["resolved_number"] = case_number
            return "500RESOLVED"

    class FakeHTTPXClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        def close(self) -> None:
            pass

    class FakePmsConnector:
        def __init__(self, *, client, api_key: str, base_url: str) -> None:
            pass

    def fake_run_case_automation(**kwargs):
        seen["run_kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr(cli, "resolve_sf_credentials", lambda *a, **k: ("https://x", "T"))
    monkeypatch.setattr(cli, "SalesforceHttpClient", FakeSFClient)
    monkeypatch.setattr(cli, "SalesforceAdapter", FakeSFAdapter)
    monkeypatch.setattr(cli.httpx, "Client", FakeHTTPXClient)
    monkeypatch.setattr(cli, "PmsConnector", FakePmsConnector)
    monkeypatch.setattr(cli, "run_case_automation", fake_run_case_automation)


def test_run_accepts_case_number_and_resolves_id(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    settings_file = _write_settings(tmp_path)
    seen: dict[str, object] = {}
    monkeypatch.setenv("PMS_API_KEY", "pms-token")
    _patch_run_fakes(monkeypatch, seen)

    result = runner.invoke(
        app,
        ["run", "00173841", "--settings", str(settings_file)],
    )

    assert result.exit_code == 0, result.output
    assert seen["resolved_number"] == "00173841"
    assert seen["run_kwargs"]["case_id"] == "500RESOLVED"


def test_run_flags_override_dry_run_and_type(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    settings_file = _write_settings(tmp_path)  # settings dry_run: true
    seen: dict[str, object] = {}
    monkeypatch.setenv("PMS_API_KEY", "pms-token")
    _patch_run_fakes(monkeypatch, seen)

    result = runner.invoke(
        app,
        ["run", "500CASE1", "--settings", str(settings_file), "--real", "--type", "er", "--yes"],
    )

    assert result.exit_code == 0, result.output
    assert seen["run_kwargs"]["dry_run"] is False
    assert seen["run_kwargs"]["issue_type"] == "ER"


def test_select_accepts_case_number(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    settings_file = _write_settings(tmp_path)
    seen: dict[str, object] = {}
    monkeypatch.setenv("PMS_API_KEY", "pms-token")
    _patch_run_fakes(monkeypatch, seen)

    result = runner.invoke(
        app,
        ["select", "00173841", "--settings", str(settings_file)],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app,
        ["list-selected", "--settings", str(settings_file)],
    )
    assert "500RESOLVED" in result.output


def test_run_falls_back_to_sf_cli_when_env_missing(tmp_path: Path, monkeypatch):
    from ai_work_automation import cli

    runner = CliRunner()
    settings_file = _write_settings(tmp_path)
    seen: dict[str, object] = {}

    monkeypatch.delenv("SF_INSTANCE_URL", raising=False)
    monkeypatch.delenv("SF_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("PMS_API_KEY", "pms-token")

    def fake_resolve(instance_url, access_token, org_alias, **kwargs):
        seen["resolve_args"] = (instance_url, access_token, org_alias)
        return ("https://cli.my.salesforce.com", "CLI_TOKEN")

    class FakeResponse:
        def model_dump_json(self, *, ensure_ascii: bool, indent: int) -> str:
            return '{"status":"success"}'

    class FakeSFClient:
        def __init__(self, instance_url: str, access_token: str) -> None:
            seen["sf_client"] = (instance_url, access_token)

        def close(self) -> None:
            pass

    class FakeSFAdapter:
        def __init__(self, *, client, cutoff, wo_fields=None) -> None:
            pass

    class FakeHTTPXClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        def close(self) -> None:
            pass

    class FakePmsConnector:
        def __init__(self, *, client, api_key: str, base_url: str) -> None:
            pass

    monkeypatch.setattr(cli, "resolve_sf_credentials", fake_resolve)
    monkeypatch.setattr(cli, "SalesforceHttpClient", FakeSFClient)
    monkeypatch.setattr(cli, "SalesforceAdapter", FakeSFAdapter)
    monkeypatch.setattr(cli.httpx, "Client", FakeHTTPXClient)
    monkeypatch.setattr(cli, "PmsConnector", FakePmsConnector)
    monkeypatch.setattr(cli, "run_case_automation", lambda **kwargs: FakeResponse())

    result = runner.invoke(
        app,
        ["run", "500CASE1", "--settings", str(settings_file), "--yes"],
    )

    assert result.exit_code == 0, result.output
    assert seen["resolve_args"] == (None, None, "parksystems")
    assert seen["sf_client"] == ("https://cli.my.salesforce.com", "CLI_TOKEN")
