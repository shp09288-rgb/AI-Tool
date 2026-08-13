import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ai_work_automation.cutoff import is_after_cutoff
from ai_work_automation.models import AttachmentRef, CaseRecord, WorkOrderRecord
from ai_work_automation.sf.client import SalesforceHttpClient


class SafetyError(Exception):
    pass


@dataclass(frozen=True)
class ExistingTechnicalServiceWo:
    id: str
    work_order_number: str
    case_id: str
    start_date: str | None = None


_SF_TZ_RE = re.compile(r"([+-])(\d{2})(\d{2})$")


def start_date_matches_day(start_raw: object, work_day: date) -> bool:
    """WO StartDate가 작업일(로컬 날짜)과 같은지."""
    if start_raw is None:
        return False
    text = str(start_raw).strip()
    if not text:
        return False
    # 2026-08-07T09:30:00.000+0900 / ...Z
    normalized = text.replace("Z", "+00:00")
    m = _SF_TZ_RE.search(normalized)
    if m and ":" not in normalized[m.start() :]:
        normalized = (
            normalized[: m.start()] + f"{m.group(1)}{m.group(2)}:{m.group(3)}"
        )
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            dt = datetime.fromisoformat(normalized[:19])
        except ValueError:
            return False
    return dt.date() == work_day


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
    owner_name: str = ""
    case_owner_name: str = ""


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
        case_activities_field: str = "Activities__c",
        technical_service_record_type_id: str | None = None,
        voc_record_type_id: str | None = None,
    ) -> None:
        self.client = client
        self.cutoff = cutoff
        self.activities_field = activities_field
        self.case_activities_field = case_activities_field
        self.technical_service_record_type_id = technical_service_record_type_id
        self.voc_record_type_id = voc_record_type_id
        self.case_fields = case_fields or [
            "Id",
            "CaseNumber",
            "Subject",
            "Description",
            "CreatedDate",
            "Status",
            case_activities_field,
        ]
        if case_activities_field not in self.case_fields:
            self.case_fields = [*self.case_fields, case_activities_field]
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
        enforce_cutoff: bool = True,
    ) -> None:
        if not case_selected:
            raise SafetyError("옵트인되지 않은 Case의 Work Order는 수정할 수 없습니다")

        created = wo.created_date
        if enforce_cutoff:
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
        sid_contains: list[str] | None = None,
        status_in: list[str] | None = None,
        owner_contains: str = "",
        limit: int = 50,
    ) -> list[CandidateWorkOrder]:
        """컷오프 이후 생성된 VOC 워크오더를 최신순으로 조회한다.

        조건 결합(SF 리포트와 동일): (장비 OR SID) AND 상태 AND 담당자 AND 부서
        """
        field_list = ", ".join(self._wo_soql_fields())
        cutoff_str = self.cutoff.isoformat()
        conditions = [
            "RecordType.DeveloperName = 'VOC'",
            f"{self.wo_department_soql_field()} = '{department}'",
            f"CreatedDate > {cutoff_str}",
        ]
        # 장비명과 SID는 하나의 OR 그룹으로 묶는다
        group_likes = [
            f"Asset.Name LIKE '%{_soql_escape(kw)}%'" for kw in (asset_contains or [])
        ] + [
            f"Asset_SID__c LIKE '%{_soql_escape(kw)}%'" for kw in (sid_contains or [])
        ]
        if group_likes:
            conditions.append(f"({' OR '.join(group_likes)})")
        if status_in:
            values = ", ".join(f"'{_soql_escape(v)}'" for v in status_in)
            conditions.append(f"Status IN ({values})")
        if owner_contains.strip():
            name = _soql_escape(owner_contains.strip())
            conditions.append(
                f"(Owner.Name LIKE '%{name}%' OR Case.Owner.Name LIKE '%{name}%')"
            )

        soql = (
            f"SELECT {field_list}, Case.CaseNumber, Case.Subject, Case.Owner.Name, "
            f"Asset.Name, Asset_SID__c, Status, Owner.Name FROM WorkOrder "
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
                    owner_name=(row.get("Owner") or {}).get("Name") or "",
                    case_owner_name=((case_info.get("Owner") or {}).get("Name")) or "",
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

    def _case_soql_fields(self) -> list[str]:
        fields = list(self.case_fields)
        if "AssetId" not in fields:
            fields.append("AssetId")
        return fields

    def _row_to_case(self, data: dict[str, Any]) -> CaseRecord:
        created = data.get("CreatedDate") or ""
        return CaseRecord(
            id=data["Id"],
            case_number=data.get("CaseNumber") or "",
            subject=data.get("Subject") or "",
            description=data.get("Description"),
            created_date=datetime.fromisoformat(created.replace("Z", "+00:00")),
            status=data.get("Status"),
            asset_id=data.get("AssetId"),
            activities=data.get(self.case_activities_field),
        )

    def find_case_by_number(self, case_number: str) -> CaseRecord | None:
        field_list = ", ".join(self._case_soql_fields())
        soql = (
            f"SELECT {field_list} FROM Case "
            f"WHERE CaseNumber = '{_soql_escape(case_number)}'"
        )
        records = self.client.query(soql).get("records", [])
        if not records:
            return None
        return self._row_to_case(records[0])

    def get_case(self, case_id: str) -> CaseRecord:
        data = self.client.get_sobject("Case", case_id, self.case_fields)
        return self._row_to_case(data)

    def create_case(self, fields: dict[str, Any]) -> str:
        result = self.client.post_sobject("Case", fields)
        return result["id"]

    def create_voc_work_order(self, *, case_id: str, fields: dict[str, Any]) -> str:
        if not self.voc_record_type_id:
            raise SafetyError("voc_record_type_id 설정이 없습니다")
        body: dict[str, Any] = dict(fields)
        body["RecordTypeId"] = self.voc_record_type_id
        body["CaseId"] = case_id
        result = self.client.post_sobject("WorkOrder", body)
        return result["id"]

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

    def find_technical_service_wos_on_day(
        self, case_id: str, work_day: date
    ) -> list[ExistingTechnicalServiceWo]:
        """같은 Case + Technical Service + StartDate 날짜=작업일인 WO."""
        rt = self.technical_service_record_type_id
        soql = (
            "SELECT Id, WorkOrderNumber, StartDate, RecordTypeId "
            f"FROM WorkOrder WHERE CaseId = '{_soql_escape(case_id)}'"
        )
        if rt:
            soql += f" AND RecordTypeId = '{_soql_escape(rt)}'"
        rows = self.client.query(soql).get("records", [])
        out: list[ExistingTechnicalServiceWo] = []
        for row in rows:
            if not start_date_matches_day(row.get("StartDate"), work_day):
                continue
            out.append(
                ExistingTechnicalServiceWo(
                    id=row["Id"],
                    work_order_number=str(row.get("WorkOrderNumber") or ""),
                    case_id=case_id,
                    start_date=row.get("StartDate"),
                )
            )
        return out

    def append_case_activities(
        self,
        case_id: str,
        line: str,
        *,
        case_selected: bool,
        enforce_cutoff: bool = True,
    ) -> None:
        if not case_selected:
            raise SafetyError("옵트인되지 않은 Case는 수정할 수 없습니다")
        data = self.client.get_sobject("Case", case_id, self.case_fields)
        created = datetime.fromisoformat(data["CreatedDate"].replace("Z", "+00:00"))
        # 출장 보고처럼 사용자가 명시한 Case는 컷오프와 무관하게 Activity 기록이 필요함
        if enforce_cutoff and not is_after_cutoff(created, self.cutoff):
            raise SafetyError("컷오프 이전 Case는 수정할 수 없습니다")
        field = self.case_activities_field
        # 실무: Case Activities는 맨 위가 최신 — 새 줄을 앞에 붙인다(기존 삭제 없음).
        existing = (data.get(field) or "").lstrip("\n")
        new_value = f"{line}\n{existing}" if existing else line
        self.client.patch_sobject(
            "Case",
            case_id,
            {field: new_value},
        )

    def get_case_number(self, case_id: str) -> str | None:
        data = self.client.get_sobject("Case", case_id, ["Id", "CaseNumber"])
        num = data.get("CaseNumber")
        return str(num) if num else None

    def get_work_order_number(self, work_order_id: str) -> str | None:
        data = self.client.get_sobject(
            "WorkOrder", work_order_id, ["Id", "WorkOrderNumber"]
        )
        num = data.get("WorkOrderNumber")
        return str(num) if num else None

    def create_technical_service_work_order(
        self,
        *,
        case_id: str,
        subject: str,
        description: str | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> str:
        if not self.technical_service_record_type_id:
            raise SafetyError("technical_service_record_type_id 설정이 없습니다")
        body: dict[str, Any] = {
            "RecordTypeId": self.technical_service_record_type_id,
            "CaseId": case_id,
            "Subject": subject,
        }
        if description:
            body["Description"] = description
        if status:
            body["Status"] = status
        if start_date:
            body["StartDate"] = start_date
        if end_date:
            body["EndDate"] = end_date
        if extra_fields:
            body.update(extra_fields)
        result = self.client.post_sobject("WorkOrder", body)
        return result["id"]

    def attach_file_to_record(self, record_id: str, file_path: Path, *, title: str | None = None) -> str:
        data = Path(file_path).read_bytes()
        name = Path(file_path).name
        result = self.client.create_content_version_from_bytes(
            title=title or Path(file_path).stem,
            path_on_client=name,
            first_publish_location_id=record_id,
            data=data,
        )
        return result["id"]

