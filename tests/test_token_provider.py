import pytest

from ai_work_automation.sf.token_provider import SfCredentialError, resolve_sf_credentials


def _fail_runner(args: list[str]) -> dict:
    raise AssertionError("환경변수가 있으면 sf CLI를 호출하면 안 됩니다")


def _fake_sf_runner(calls: list[list[str]] | None = None):
    """org display에서는 URL만, show-access-token에서는 실제 토큰을 돌려주는 sf CLI 흉내."""

    def runner(args: list[str]) -> dict:
        if calls is not None:
            calls.append(args)
        if args[:2] == ["org", "display"]:
            return {
                "status": 0,
                "result": {
                    "instanceUrl": "https://parksystems.my.salesforce.com",
                    "accessToken": "[REDACTED] Use 'sf org auth show-access-token' to view",
                },
            }
        if args[:3] == ["org", "auth", "show-access-token"]:
            return {"status": 0, "result": {"accessToken": "00Dxx!REAL_TOKEN"}}
        raise AssertionError(f"예상하지 못한 sf 명령: {args}")

    return runner


def test_env_values_used_when_present():
    url, token = resolve_sf_credentials(
        "https://example.my.salesforce.com",
        "TOKEN123",
        org_alias="parksystems",
        run_sf_command=_fail_runner,
    )
    assert url == "https://example.my.salesforce.com"
    assert token == "TOKEN123"


def test_falls_back_to_sf_cli_when_env_missing():
    calls: list[list[str]] = []

    url, token = resolve_sf_credentials(
        None, None, org_alias="parksystems", run_sf_command=_fake_sf_runner(calls)
    )

    assert url == "https://parksystems.my.salesforce.com"
    assert token == "00Dxx!REAL_TOKEN"
    assert ["org", "display", "--target-org", "parksystems"] in calls
    assert ["org", "auth", "show-access-token", "--target-org", "parksystems"] in calls


def test_empty_string_env_treated_as_missing():
    url, token = resolve_sf_credentials(
        "", "", org_alias="parksystems", run_sf_command=_fake_sf_runner()
    )
    assert token == "00Dxx!REAL_TOKEN"


def test_raises_clear_error_when_cli_result_invalid():
    def bad_runner(args: list[str]) -> dict:
        return {"status": 1, "message": "No authorization information found"}

    with pytest.raises(SfCredentialError):
        resolve_sf_credentials(None, None, org_alias="parksystems", run_sf_command=bad_runner)
