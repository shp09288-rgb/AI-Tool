from pathlib import Path
import os

import yaml

from ai_work_automation.config_store import (
    upsert_env_key,
    env_key_is_set,
    apply_env_key_to_process,
    update_settings_yaml,
)
from ai_work_automation.settings import load_settings


def test_upsert_env_key_adds_new_key(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("FOO=1\n", encoding="utf-8")
    upsert_env_key(env, "PMS_API_KEY", "secret-abc")
    text = env.read_text(encoding="utf-8")
    assert "FOO=1" in text
    assert "PMS_API_KEY=secret-abc" in text


def test_upsert_env_key_replaces_existing(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("PMS_API_KEY=old\nBAR=2\n", encoding="utf-8")
    upsert_env_key(env, "PMS_API_KEY", "new")
    lines = env.read_text(encoding="utf-8").splitlines()
    assert lines.count("PMS_API_KEY=new") == 1
    assert "PMS_API_KEY=old" not in lines
    assert "BAR=2" in lines


def test_upsert_env_key_creates_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    upsert_env_key(env, "PMS_API_KEY", "x")
    assert env.read_text(encoding="utf-8").strip() == "PMS_API_KEY=x"


def test_env_key_is_set(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("PMS_API_KEY=\n", encoding="utf-8")
    assert env_key_is_set(env, "PMS_API_KEY") is False
    env.write_text("PMS_API_KEY=abc\n", encoding="utf-8")
    assert env_key_is_set(env, "PMS_API_KEY") is True
    assert env_key_is_set(env, "MISSING") is False


def test_apply_env_key_to_process() -> None:
    apply_env_key_to_process("PMS_API_KEY", "runtime-val")
    assert os.environ["PMS_API_KEY"] == "runtime-val"


def test_update_settings_yaml_preserves_other_keys(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text(
        'automation_enabled_after: "2026-12-01T00:00:00+09:00"\n'
        "dry_run: true\n"
        "pms_project_id: 1\n",
        encoding="utf-8",
    )
    update_settings_yaml(path, {"dry_run": False, "sf_org_alias": "parksystems"})
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["dry_run"] is False
    assert raw["sf_org_alias"] == "parksystems"
    assert raw["pms_project_id"] == 1
    s = load_settings(path)
    assert s.dry_run is False
    assert s.sf_org_alias == "parksystems"


def test_update_settings_yaml_field_report_root(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text(
        'automation_enabled_after: "2026-12-01T00:00:00+09:00"\n',
        encoding="utf-8",
    )
    root = str(tmp_path / "DFS2")
    update_settings_yaml(path, {"field_report_root": root})
    s = load_settings(path)
    assert s.field_report_root == Path(root)
