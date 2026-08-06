import json
from pathlib import Path


class OptInStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[str]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, ids: list[str]) -> None:
        self.path.write_text(
            json.dumps(sorted(set(ids)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_selected(self, case_id: str) -> bool:
        return case_id in self._read()

    def select(self, case_id: str) -> None:
        ids = self._read()
        ids.append(case_id)
        self._write(ids)

    def deselect(self, case_id: str) -> None:
        self._write([i for i in self._read() if i != case_id])

    def list_selected(self) -> list[str]:
        return self._read()
