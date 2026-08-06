from datetime import datetime, timezone
from pathlib import Path

from ai_work_automation.models import WorkOrderRecord
from ai_work_automation.router import load_routes, resolve_targets


def test_voc_sw_routes_to_pms(tmp_path: Path):
    routes_file = tmp_path / "routes.yaml"
    routes_file.write_text(
        """
routes:
  - id: voc-sw-pms
    when:
      recordType: VOC
      department: SW
    targets: [pms]
""",
        encoding="utf-8",
    )
    routes = load_routes(routes_file)
    wo = WorkOrderRecord(
        id="1",
        work_order_number="1",
        record_type="VOC",
        relevant_department="SW",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )
    assert resolve_targets(wo, routes) == ["pms"]


def test_unmatched_returns_empty(tmp_path: Path):
    routes_file = tmp_path / "routes.yaml"
    routes_file.write_text(
        "routes:\n  - id: x\n    when: {recordType: VOC, department: SW}\n    targets: [pms]\n",
        encoding="utf-8",
    )
    routes = load_routes(routes_file)
    wo = WorkOrderRecord(
        id="1",
        work_order_number="1",
        record_type="VOC",
        relevant_department="HW",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )
    assert resolve_targets(wo, routes) == []
