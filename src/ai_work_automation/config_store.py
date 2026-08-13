from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import yaml

_ENV_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def format_cutoff_iso_kst(d: date) -> str:
    """사이드바 날짜 → settings.yaml automation_enabled_after 형식."""
    return f"{d.isoformat()}T00:00:00+09:00"


def upsert_env_key(env_path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    found = False
    for line in lines:
        m = _ENV_LINE.match(line)
        if m and m.group(1) == key:
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def env_key_is_set(env_path: Path, key: str) -> bool:
    if not env_path.exists():
        return False
    for line in env_path.read_text(encoding="utf-8").splitlines():
        m = _ENV_LINE.match(line)
        if m and m.group(1) == key:
            return bool(m.group(2).strip())
    return False


def apply_env_key_to_process(key: str, value: str) -> None:
    os.environ[key] = value


def update_settings_yaml(path: Path, updates: dict[str, object]) -> None:
    raw: dict = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"settings root must be a mapping: {path}")
        raw = loaded
    for key, value in updates.items():
        if isinstance(value, Path):
            raw[key] = str(value)
        else:
            raw[key] = value
    path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
