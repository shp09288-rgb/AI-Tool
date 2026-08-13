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
            "환경변수(SF_INSTANCE_URL/SF_ACCESS_TOKEN)를 설정하거나 sf CLI를 설치하세요."
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
