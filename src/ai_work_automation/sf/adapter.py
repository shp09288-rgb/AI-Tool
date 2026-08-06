from datetime import datetime
from typing import Any

from ai_work_automation.cutoff import is_after_cutoff
from ai_work_automation.models import CaseRecord, WorkOrderRecord
from ai_work_automation.sf.client import SalesforceHttpClient


class SafetyError(Exception):
    pass


class SalesforceAdapter:
    def __init__(
        self,
        client: SalesforceHttpClient | Any,
        cutoff: datetime,
        activities_field: str = "VOC_Activities__c",
        case_fields: list[str] | None = None,
        wo_fields: list[str] | None = None,
    ) -> None:
        self.client = client
        self.cutoff = cutoff
        self.activities_field = activities_field
        self.case_fields = case_fields or [
            "Id",
            "CaseNumber",
            "Subject",
            "Description",
            "CreatedDate",
            "Status",
        ]
        self.wo_fields = wo_fields or [
            "Id",
            "WorkOrderNumber",
            "Subject",
            "CreatedDate",
            "CaseId",
            "Priority",
            activities_field,
        ]

    def append_work_order_activities(
        self,
        wo: WorkOrderRecord,
        line: str,
        *,
        case_selected: bool,
    ) -> None:
        if not case_selected:
            raise SafetyError("옵트인되지 않은 Case의 Work Order는 수정할 수 없습니다")

        created = wo.created_date
        if created is None:
            raise SafetyError("Work Order CreatedDate가 없어 컷오프를 검사할 수 없습니다")
        if not is_after_cutoff(created, self.cutoff):
            raise SafetyError("컷오프 이전 Work Order는 수정할 수 없습니다")

        existing = wo.activities or ""
        separator = "\n" if existing and not existing.endswith("\n") else ""
        new_value = f"{existing}{separator}{line}"
        self.client.patch_sobject(
            "WorkOrder",
            wo.id,
            {self.activities_field: new_value},
        )

    def get_case(self, case_id: str) -> CaseRecord:
        data = self.client.get_sobject("Case", case_id, self.case_fields)
        return CaseRecord(
            id=data["Id"],
            case_number=data.get("CaseNumber") or "",
            subject=data.get("Subject") or "",
            description=data.get("Description"),
            created_date=datetime.fromisoformat(data["CreatedDate"].replace("Z", "+00:00")),
            status=data.get("Status"),
        )

    def _wo_soql_fields(self) -> list[str]:
        fields = list(self.wo_fields)
        if "RecordType.Name" not in fields:
            fields.append("RecordType.Name")
        return fields

    def _relevant_department_from_row(self, row: dict[str, Any]) -> str | None:
        standard = {
            "Id",
            "WorkOrderNumber",
            "Subject",
            "CreatedDate",
            "CaseId",
            "Priority",
            self.activities_field,
            "RecordType.Name",
        }
        for field in self.wo_fields:
            if field in standard:
                continue
            value = row.get(field)
            if value is not None:
                return str(value)
        return None

    def get_work_orders_for_case(self, case_id: str) -> list[WorkOrderRecord]:
        field_list = ", ".join(self._wo_soql_fields())
        soql = f"SELECT {field_list} FROM WorkOrder WHERE CaseId = '{case_id}'"
        data = self.client.query(soql)
        out: list[WorkOrderRecord] = []
        for row in data.get("records", []):
            created = row.get("CreatedDate")
            activities = (
                row.get(self.activities_field)
                if self.activities_field in self.wo_fields
                else None
            )
            out.append(
                WorkOrderRecord(
                    id=row["Id"],
                    work_order_number=row.get("WorkOrderNumber") or "",
                    record_type=(row.get("RecordType") or {}).get("Name") or "",
                    relevant_department=self._relevant_department_from_row(row),
                    subject=row.get("Subject"),
                    activities=activities,
                    case_id=row.get("CaseId"),
                    created_date=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
                    priority=row.get("Priority"),
                )
            )
        return out

