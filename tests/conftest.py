from datetime import datetime, timezone

import pytest

from ai_work_automation.models import CaseRecord, WorkOrderRecord


@pytest.fixture
def sample_case() -> CaseRecord:
    return CaseRecord(
        id="500CASE1",
        case_number="00190001",
        subject="AST / NX / Servo OFF",
        created_date=datetime(2026, 12, 2, 1, 0, tzinfo=timezone.utc),
        description="상세 설명",
    )


@pytest.fixture
def sample_wo_voc_sw(sample_case: CaseRecord) -> WorkOrderRecord:
    return WorkOrderRecord(
        id="0WORK1",
        work_order_number="00025947",
        record_type="VOC",
        relevant_department="SW",
        subject=sample_case.subject,
        activities="",
        case_id=sample_case.id,
        created_date=sample_case.created_date,
        priority="High",
    )
