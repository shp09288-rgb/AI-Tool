from datetime import datetime
from typing import Any

from pydantic import BaseModel

from ai_work_automation.cutoff import is_after_cutoff
from ai_work_automation.models import AttachmentRef, CaseRecord, WorkOrderRecord
from ai_work_automation.sf.client import SalesforceHttpClient


class SafetyError(Exception):
    pass


def _soql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class CandidateWorkOrder(BaseModel):
    """스캔 결과: 케이스 정보가 붙은 워크오더."""

    work_order: WorkOrderRecord
    case_number: str
    case_subject: str
    asset_name: str = ""
    asset_sid: str = ""
    status: str = ""


class CaseSearchResult(BaseModel):
    case_id: str
    case_number: str
    subject: str
    created_date: str


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

    def get_attachments(self, record_id: str) -> list[AttachmentRef]:
        soql = (
            "SELECT ContentDocumentId, ContentDocument.Title, ContentDocument.FileExtension "
            f"FROM ContentDocumentLink WHERE LinkedEntityId = '{record_id}'"
        )
        records = self.client.query(soql).get("records", [])
        out: list[AttachmentRef] = []
        for row in records:
            doc = row.get("ContentDocument") or {}
            title = doc.get("Title") or "첨부파일"
            extension = doc.get("FileExtension")
            if extension:
                title = f"{title}.{extension}"
            out.append(
                AttachmentRef(
                    title=title,
                    url=(
                        f"{self.client.instance_url}"
                        f"/sfc/servlet.shepherd/document/download/{row['ContentDocumentId']}"
                    ),
                )
            )
        return out

    def _row_to_work_order(self, row: dict[str, Any]) -> WorkOrderRecord:
        created = row.get("CreatedDate")
        activities = (
            row.get(self.activities_field)
            if self.activities_field in self.wo_fields
            else None
        )
        return WorkOrderRecord(
            id=row["Id"],
            work_order_number=row.get("WorkOrderNumber") or "",
            record_type=(row.get("RecordType") or {}).get("Name") or "",
            relevant_department=self._relevant_department_from_row(row),
            subject=row.get("Subject"),
            voc_title=row.get("VOC_Title__c"),
            background=row.get("Background_Problem__c"),
            activities=activities,
            case_id=row.get("CaseId"),
            created_date=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
            priority=row.get("Priority"),
        )

    def find_recent_voc_work_orders(
        self,
        department: str,
        asset_contains: list[str] | None = None,
        status_in: list[str] | None = None,
        limit: int = 50,
    ) -> list[CandidateWorkOrder]:
        """컷오프 이후 생성된 VOC 워크오더 중 지정 부서의 것을 최신순으로 조회한다."""
        field_list = ", ".join(self._wo_soql_fields())
        cutoff_str = self.cutoff.isoformat()
        conditions = [
            "RecordType.DeveloperName = 'VOC'",
            f"{self.wo_department_soql_field()} = '{department}'",
            f"CreatedDate > {cutoff_str}",
        ]
        if asset_contains:
            likes = " OR ".join(
                f"Asset.Name LIKE '%{_soql_escape(kw)}%'" for kw in asset_contains
            )
            conditions.append(f"({likes})")
        if status_in:
            values = ", ".join(f"'{_soql_escape(v)}'" for v in status_in)
            conditions.append(f"Status IN ({values})")

        soql = (
            f"SELECT {field_list}, Case.CaseNumber, Case.Subject, "
            f"Asset.Name, Asset_SID__c, Status FROM WorkOrder "
            f"WHERE {' AND '.join(conditions)} "
            f"ORDER BY CreatedDate DESC LIMIT {limit}"
        )
        data = self.client.query(soql)
        out: list[CandidateWorkOrder] = []
        for row in data.get("records", []):
            case_info = row.get("Case") or {}
            out.append(
                CandidateWorkOrder(
                    work_order=self._row_to_work_order(row),
                    case_number=case_info.get("CaseNumber") or "",
                    case_subject=case_info.get("Subject") or "",
                    asset_name=(row.get("Asset") or {}).get("Name") or "",
                    asset_sid=row.get("Asset_SID__c") or "",
                    status=row.get("Status") or "",
                )
            )
        return out

    def search_cases(self, keyword: str, limit: int = 20) -> list[CaseSearchResult]:
        """케이스 번호 또는 제목에 키워드가 포함된 케이스를 최신순으로 검색한다."""
        kw = _soql_escape(keyword)
        soql = (
            "SELECT Id, CaseNumber, Subject, CreatedDate FROM Case "
            f"WHERE (CaseNumber LIKE '%{kw}%' OR Subject LIKE '%{kw}%') "
            f"ORDER BY CreatedDate DESC LIMIT {limit}"
        )
        data = self.client.query(soql)
        return [
            CaseSearchResult(
                case_id=row["Id"],
                case_number=row.get("CaseNumber") or "",
                subject=row.get("Subject") or "",
                created_date=row.get("CreatedDate") or "",
            )
            for row in data.get("records", [])
        ]

    def wo_department_soql_field(self) -> str:
        """wo_fields 중 부서 커스텀 필드를 찾는다 (기본 Relevant_Department__c)."""
        standard = {
            "Id",
            "WorkOrderNumber",
            "Subject",
            "CreatedDate",
            "CaseId",
            "Priority",
            "VOC_Title__c",
            "Background_Problem__c",
            self.activities_field,
            "RecordType.Name",
        }
        for field in self.wo_fields:
            if field not in standard:
                return field
        return "Relevant_Department__c"

    def find_case_id_by_number(self, case_number: str) -> str | None:
        soql = f"SELECT Id, CaseNumber FROM Case WHERE CaseNumber = '{case_number}'"
        records = self.client.query(soql).get("records", [])
        if not records:
            return None
        return records[0]["Id"]

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
            "VOC_Title__c",
            "Background_Problem__c",
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
        return [self._row_to_work_order(row) for row in data.get("records", [])]

