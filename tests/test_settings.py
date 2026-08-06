from pathlib import Path

from ai_work_automation.settings import load_settings


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
dry_run: true
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.pms_project_id == 7
    assert settings.wo_department_field == "Department__c"
