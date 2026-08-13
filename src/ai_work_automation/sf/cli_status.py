"""Salesforce CLI org display 상태 헬퍼."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable


class SfCliStatusError(RuntimeError):
    """sf CLI subprocess / JSON 해석 실패."""


def _run_sf_json_subprocess(args: list[str]) -> dict[str, Any]:
    """token_provider._run_sf_json_subprocess 와 동일 패턴 (private 재export 회피용 복제)."""
    exe = shutil.which("sf")
    if exe is None:
        raise SfCliStatusError(
            "Salesforce CLI(sf)를 찾을 수 없습니다. "
            "`1-처음설치.bat`를 다시 실행하거나 "
            "https://developer.salesforce.com/tools/salesforcecli 에서 설치한 뒤 "
            "`sf org login web --alias parksystems` 로 로그인하세요."
        )
    proc = subprocess.run(
        [exe, *args, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SfCliStatusError(
            f"'sf {' '.join(args)}' 출력을 해석할 수 없습니다: {proc.stdout[:200]}"
        ) from exc


@dataclass(frozen=True)
class SfCliStatus:
    ok: bool
    connected: bool
    username: str | None
    alias: str
    message: str


def get_sf_cli_status(
    org_alias: str,
    run_sf_command: Callable[[list[str]], dict[str, Any]] | None = None,
) -> SfCliStatus:
    runner = run_sf_command or _run_sf_json_subprocess
    try:
        data = runner(["org", "display", "--target-org", org_alias])
    except SfCliStatusError as exc:
        return SfCliStatus(
            ok=False, connected=False, username=None, alias=org_alias, message=str(exc)
        )
    if data.get("status") != 0:
        msg = str(data.get("message") or data)[:200]
        return SfCliStatus(
            ok=False, connected=False, username=None, alias=org_alias, message=msg
        )
    result = data.get("result") or {}
    status = str(result.get("connectedStatus") or "")
    connected = status.lower() == "connected"
    return SfCliStatus(
        ok=True,
        connected=connected,
        username=result.get("username"),
        alias=org_alias,
        message=status or ("Connected" if connected else "Not connected"),
    )


@dataclass(frozen=True)
class SfOrgRow:
    alias: str
    username: str | None
    connected: bool


_PREFERRED_ORG_LIST_KEYS = ("other", "sandboxes", "devHubs", "scratchOrgs", "regularOrgs")


def _org_rows_from_list_result(result: object) -> list[SfOrgRow]:
    rows: list[SfOrgRow] = []
    if not isinstance(result, dict):
        return rows
    preferred_present = any(key in result for key in _PREFERRED_ORG_LIST_KEYS)
    values: list[object] = (
        [result[key] for key in _PREFERRED_ORG_LIST_KEYS if key in result]
        if preferred_present
        else list(result.values())
    )
    seen_aliases: set[str] = set()
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            username = item.get("username")
            alias_raw = item.get("alias") or username
            if not alias_raw:
                continue
            alias = str(alias_raw)
            if alias in seen_aliases:
                continue
            seen_aliases.add(alias)
            status = str(item.get("connectedStatus") or "")
            rows.append(
                SfOrgRow(
                    alias=alias,
                    username=str(username) if username else None,
                    connected=status.lower() == "connected",
                )
            )
    return rows


def list_sf_orgs(
    run_sf_command: Callable[[list[str]], dict[str, Any]] | None = None,
) -> list[SfOrgRow]:
    runner = run_sf_command or _run_sf_json_subprocess
    data = runner(["org", "list"])
    if data.get("status") != 0:
        raise SfCliStatusError(str(data.get("message") or data)[:200])
    return _org_rows_from_list_result(data.get("result"))


def logout_sf_org(
    org_alias: str,
    run_sf_command: Callable[[list[str]], dict[str, Any]] | None = None,
) -> None:
    runner = run_sf_command or _run_sf_json_subprocess
    data = runner(["org", "logout", "--target-org", org_alias])
    if data.get("status") != 0:
        raise SfCliStatusError(str(data.get("message") or data)[:200])


def _run_sf_login_subprocess(args: list[str]) -> int:
    exe = shutil.which("sf")
    if exe is None:
        raise SfCliStatusError(
            "Salesforce CLI(sf)를 찾을 수 없습니다. "
            "`1-처음설치.bat`를 다시 실행하거나 "
            "https://developer.salesforce.com/tools/salesforcecli 에서 설치한 뒤 "
            "`sf org login web --alias parksystems` 로 로그인하세요."
        )
    proc = subprocess.run(
        [exe, *args],
        text=True,
        encoding="utf-8",
    )
    return int(proc.returncode)


def login_sf_org(
    org_alias: str,
    run_sf_login: Callable[[list[str]], int] | None = None,
) -> None:
    runner = run_sf_login or _run_sf_login_subprocess
    code = runner(["org", "login", "web", "--alias", org_alias])
    if code != 0:
        raise SfCliStatusError(
            f"Salesforce 로그인에 실패했습니다 (alias={org_alias}, exit={code}). "
            "브라우저에서 로그인했는지 확인하세요."
        )
