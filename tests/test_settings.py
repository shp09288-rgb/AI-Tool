from pathlib import Path

from ai_work_automation.settings import load_settings


def test_load_settings_parses_pms_custom_fields(tmp_path: Path):
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
automation_enabled_after: "2026-12-01T00:00:00+09:00"
pms_custom_fields:
  defaults:
    "30": "414"
    "15": "81"
  customer_field: "17"
  customer_detail_field: "29"
  customer_map:
    LGD: "131"
    SDC: "132"
    공통: "143"
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.pms_custom_fields.defaults == {"30": "414", "15": "81"}
    assert settings.pms_custom_fields.customer_field == "17"
    assert settings.pms_custom_fields.customer_map["SDC"] == "132"


def test_load_settings_parses_scan_filters(tmp_path: Path):
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
automation_enabled_after: "2026-12-01T00:00:00+09:00"
scan_filters:
  asset_contains: [NX-TSH1518, NX-TSH2225]
  sid_contains: [D160025-230523]
  status_in: [New, In Progress]
  owner_contains: 이동한
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.scan_filters.asset_contains == ["NX-TSH1518", "NX-TSH2225"]
    assert settings.scan_filters.sid_contains == ["D160025-230523"]
    assert settings.scan_filters.status_in == ["New", "In Progress"]
    assert settings.scan_filters.owner_contains == "이동한"


def test_load_settings_scan_filters_default_empty(tmp_path: Path):
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        'automation_enabled_after: "2026-12-01T00:00:00+09:00"',
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.scan_filters.asset_contains == []
    assert settings.scan_filters.status_in == []


def test_load_settings_custom_fields_default_empty(tmp_path: Path):
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        'automation_enabled_after: "2026-12-01T00:00:00+09:00"',
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.pms_custom_fields.defaults == {}
    assert settings.pms_custom_fields.customer_map == {}


def test_load_settings_defaults_missing_project_and_department(tmp_path: Path):
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
automation_enabled_after: "2026-12-01T00:00:00+09:00"
opt_in_path: data/opt_in.json
job_log_path: data/job_log.jsonl
routes_path: config/routes.yaml
pms_base_url: https://pms.parksystems.com
dry_run: true
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.pms_project_id == 1
    assert settings.wo_department_field == "Relevant_Department__c"
    assert settings.idempotency_path == Path("data/idempotency.json")
    assert settings.sf_org_alias == "parksystems"


def test_load_settings_overrides_project_and_department(tmp_path: Path):
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
automation_enabled_after: "2026-12-01T00:00:00+09:00"
opt_in_path: data/opt_in.json
job_log_path: data/job_log.jsonl
routes_path: config/routes.yaml
pms_base_url: https://pms.parksystems.com
pms_project_id: 7
wo_department_field: Department__c
idempotency_path: custom/idempotency.json
sf_org_alias: my-sandbox
dry_run: true
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.pms_project_id == 7
    assert settings.wo_department_field == "Department__c"
    assert settings.idempotency_path == Path("custom/idempotency.json")
    assert settings.sf_org_alias == "my-sandbox"


def test_load_settings_voc_record_type_id_defaults_none(tmp_path: Path):
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        'automation_enabled_after: "2026-12-01T00:00:00+09:00"',
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.field_report.voc_record_type_id is None


def test_load_settings_parses_voc_record_type_id(tmp_path: Path):
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
automation_enabled_after: "2026-12-01T00:00:00+09:00"
field_report:
  voc_record_type_id: "0122j000000CglcAAC"
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.field_report.voc_record_type_id == "0122j000000CglcAAC"


def test_make_sf_adapter_passes_voc_record_type_id(tmp_path: Path, monkeypatch):
    from ai_work_automation.cli import _make_sf_adapter
    from ai_work_automation.sf import adapter as adapter_mod

    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        """
automation_enabled_after: "2026-12-01T00:00:00+09:00"
field_report:
  voc_record_type_id: "0122j000000CglcAAC"
""".strip(),
        encoding="utf-8",
    )
    settings = load_settings(settings_file)
    seen: dict[str, object] = {}

    class FakeAdapter:
        def __init__(self, client, cutoff, **kwargs) -> None:
            seen["kwargs"] = kwargs

    class FakeClient:
        def __init__(self, instance_url: str, access_token: str) -> None:
            pass

    monkeypatch.setattr(adapter_mod, "SalesforceAdapter", FakeAdapter)
    monkeypatch.setattr(
        "ai_work_automation.cli.SalesforceHttpClient", FakeClient
    )
    monkeypatch.setattr(
        "ai_work_automation.cli.resolve_sf_credentials",
        lambda *a, **k: ("https://example.salesforce.com", "token"),
    )

    _make_sf_adapter(settings)

    assert seen["kwargs"]["voc_record_type_id"] == "0122j000000CglcAAC"
    assert seen["kwargs"]["technical_service_record_type_id"] == (
        settings.field_report.technical_service_record_type_id
    )
