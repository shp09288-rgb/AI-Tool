"""Salesforce 인증 정보 리졸버.

환경변수에 값이 있으면 그대로 사용하고, 없으면 로그인된 Salesforce CLI에서 가져온다.
- 인스턴스 URL: `sf org display`
- 액세스 토큰: `sf org auth show-access-token` (org display의 토큰은 REDACTED 처리됨)
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any, Callable


class SfCredentialError(RuntimeError):
    pass


def _run_sf_json_subprocess(args: list[str]) -> dict[str, Any]:
    exe = shutil.which("sf")
    if exe is None:
        raise SfCredentialError(
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
        raise SfCredentialError(
            f"'sf {' '.join(args)}' 출력을 해석할 수 없습니다: {proc.stdout[:200]}"
        ) from exc


def resolve_sf_credentials(
    instance_url: str | None,
    access_token: str | None,
    org_alias: str,
    run_sf_command: Callable[[list[str]], dict[str, Any]] = _run_sf_json_subprocess,
) -> tuple[str, str]:
    """(instance_url, access_token) 튜플을 반환한다."""
    if instance_url and access_token:
        return instance_url, access_token

    display = run_sf_command(["org", "display", "--target-org", org_alias])
    cli_url = (display.get("result") or {}).get("instanceUrl")
    if display.get("status") != 0 or not cli_url:
        _raise_credential_error(org_alias, display)

    token_data = run_sf_command(["org", "auth", "show-access-token", "--target-org", org_alias])
    cli_token = (token_data.get("result") or {}).get("accessToken")
    if token_data.get("status") != 0 or not cli_token:
        _raise_credential_error(org_alias, token_data)

    return cli_url, cli_token


def _raise_credential_error(org_alias: str, data: dict[str, Any]) -> None:
    message = data.get("message") or json.dumps(data, ensure_ascii=False)[:200]
    raise SfCredentialError(
        f"sf CLI에서 인증 정보를 가져오지 못했습니다 (org: {org_alias}): {message}\n"
        f"'sf org login web --alias {org_alias}' 로 로그인했는지 확인하세요."
    )
