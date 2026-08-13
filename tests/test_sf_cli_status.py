from ai_work_automation.sf.cli_status import get_sf_cli_status


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
