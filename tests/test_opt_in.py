from pathlib import Path

from ai_work_automation.opt_in import OptInStore


def test_select_and_check(tmp_path: Path):
    store = OptInStore(tmp_path / "opt_in.json")
    assert store.is_selected("500A") is False
    store.select("500A")
    assert store.is_selected("500A") is True
    assert "500A" in store.list_selected()


def test_deselect(tmp_path: Path):
    store = OptInStore(tmp_path / "opt_in.json")
    store.select("500A")
    store.deselect("500A")
    assert store.is_selected("500A") is False
