from ai_work_automation.sf.cli_status import (
    SfCliStatusError,
    get_sf_cli_status,
    list_sf_orgs,
    login_sf_org,
    logout_sf_org,
)


def test_get_sf_cli_status_connected() -> None:
    def fake(args: list[str]) -> dict:
        assert args[:2] == ["org", "display"]
        return {
            "status": 0,
            "result": {
                "connectedStatus": "Connected",
                "username": "ethan.lee@parksystems.com",
            },
        }

    st = get_sf_cli_status("parksystems", run_sf_command=fake)
    assert st.ok is True
    assert st.connected is True
    assert st.username == "ethan.lee@parksystems.com"
    assert st.alias == "parksystems"


def test_get_sf_cli_status_not_connected() -> None:
    def fake(_args: list[str]) -> dict:
        return {"status": 0, "result": {"connectedStatus": "Disconnected"}}

    st = get_sf_cli_status("parksystems", run_sf_command=fake)
    assert st.connected is False
    assert st.ok is True


def test_get_sf_cli_status_cli_error() -> None:
    def fake(_args: list[str]) -> dict:
        return {"status": 1, "message": "no org"}

    st = get_sf_cli_status("x", run_sf_command=fake)
    assert st.ok is False
    assert "no org" in st.message


def test_list_sf_orgs_flattens_non_scratch_and_sandboxes() -> None:
    def fake(args: list[str]) -> dict:
        assert args == ["org", "list"]
        return {
            "status": 0,
            "result": {
                "nonScratchOrgs": [
                    {
                        "alias": "parksystems",
                        "username": "a@example.com",
                        "connectedStatus": "Connected",
                    }
                ],
                "sandboxes": [
                    {
                        "alias": "sbx",
                        "username": "b@example.com",
                        "connectedStatus": "Disconnected",
                    }
                ],
                "other": [],
            },
        }

    rows = list_sf_orgs(run_sf_command=fake)
    assert len(rows) == 2
    assert rows[0].alias == "parksystems"
    assert rows[0].username == "a@example.com"
    assert rows[0].connected is True
    assert rows[1].alias == "sbx"
    assert rows[1].connected is False


def test_list_sf_orgs_skips_entries_without_alias_uses_username_as_fallback_alias() -> None:
    def fake(_args: list[str]) -> dict:
        return {
            "status": 0,
            "result": {
                "nonScratchOrgs": [
                    {"username": "only@example.com", "connectedStatus": "Connected"},
                ]
            },
        }

    rows = list_sf_orgs(run_sf_command=fake)
    assert len(rows) == 1
    assert rows[0].alias == "only@example.com"
    assert rows[0].username == "only@example.com"


def test_list_sf_orgs_cli_status_error() -> None:
    def fake(_args: list[str]) -> dict:
        return {"status": 1, "message": "list failed"}

    try:
        list_sf_orgs(run_sf_command=fake)
        assert False, "expected SfCliStatusError"
    except SfCliStatusError as exc:
        assert "list failed" in str(exc)


def test_logout_sf_org_ok() -> None:
    calls: list[list[str]] = []

    def fake(args: list[str]) -> dict:
        calls.append(args)
        return {"status": 0, "result": {}}

    logout_sf_org("parksystems", run_sf_command=fake)
    assert calls == [["org", "logout", "--target-org", "parksystems"]]


def test_logout_sf_org_raises_on_failure() -> None:
    def fake(_args: list[str]) -> dict:
        return {"status": 1, "message": "not logged in"}

    try:
        logout_sf_org("x", run_sf_command=fake)
        assert False, "expected SfCliStatusError"
    except SfCliStatusError as exc:
        assert "not logged in" in str(exc)


def test_login_sf_org_ok() -> None:
    calls: list[list[str]] = []

    def fake_login(args: list[str]) -> int:
        calls.append(args)
        return 0

    login_sf_org("parksystems", run_sf_login=fake_login)
    assert calls == [["org", "login", "web", "--alias", "parksystems"]]


def test_login_sf_org_raises_on_nonzero() -> None:
    def fake_login(_args: list[str]) -> int:
        return 1

    try:
        login_sf_org("x", run_sf_login=fake_login)
        assert False, "expected SfCliStatusError"
    except SfCliStatusError as exc:
        assert "login" in str(exc).lower() or "x" in str(exc)
