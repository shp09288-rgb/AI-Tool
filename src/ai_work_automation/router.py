from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ai_work_automation.models import WorkOrderRecord


class RouteWhen(BaseModel):
    recordType: str
    department: str | None = None


class RouteRule(BaseModel):
    id: str
    when: RouteWhen
    targets: list[str]
    require_human_gate: bool = True


class RoutesFile(BaseModel):
    routes: list[RouteRule] = Field(default_factory=list)


def load_routes(path: Path) -> list[RouteRule]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RoutesFile.model_validate(data).routes


def resolve_targets(wo: WorkOrderRecord, routes: list[RouteRule]) -> list[str]:
    matched: list[str] = []
    for rule in routes:
        if rule.when.recordType != wo.record_type:
            continue
        if rule.when.department is not None:
            if (wo.relevant_department or "") != rule.when.department:
                continue
        matched.extend(rule.targets)
    # 순서 유지 중복 제거
    seen: set[str] = set()
    out: list[str] = []
    for t in matched:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
