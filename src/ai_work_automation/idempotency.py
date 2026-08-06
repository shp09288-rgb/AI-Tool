from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonIdempotencyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"entries": {}}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return {"entries": {}}
        if not raw:
            return {"entries": {}}
        data = json.loads(raw)
        if "entries" not in data or not isinstance(data["entries"], dict):
            return {"entries": {}}
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def has(self, work_order_id: str, target: str) -> bool:
        data = self._read()
        return target in data.get("entries", {}).get(work_order_id, {})

    def record(self, work_order_id: str, target: str, ref: str | None, url: str | None) -> None:
        data = self._read()
        entries = data.setdefault("entries", {})
        work_order_entries = entries.setdefault(work_order_id, {})
        work_order_entries[target] = {
            "ref": ref,
            "url": url,
        }
        self._write(data)
