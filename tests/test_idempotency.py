from ai_work_automation.idempotency import JsonIdempotencyStore


def test_idempotency_store_persists_keys(tmp_path):
    store = JsonIdempotencyStore(tmp_path / "idempotency.json")

    assert store.has("0WO1", "pms") is False

    store.record("0WO1", "pms", ref="4710", url="https://pms.example/issues/4710")

    assert store.has("0WO1", "pms") is True

    reloaded = JsonIdempotencyStore(tmp_path / "idempotency.json")
    assert reloaded.has("0WO1", "pms") is True
