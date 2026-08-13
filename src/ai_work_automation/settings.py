from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PmsCustomFieldsConfig(BaseModel):
    """PMS 이슈 커스텀 필드 자동 입력 규칙.

    - defaults: 항상 넣는 값 (필드ID -> 값)
    - customer_field/customer_detail_field: 고객사/사이트 필드 ID
    - customer_map: 제목 첫 구간의 키워드 -> Customer 필드 값
    """

    defaults: dict[str, str] = Field(default_factory=dict)
    customer_field: str | None = None
    customer_detail_field: str | None = None
    customer_map: dict[str, str] = Field(default_factory=dict)


class ScanFiltersConfig(BaseModel):
    """스캔 기본 필터. 비어 있으면 조건을 적용하지 않는다.

    조건 결합: (asset_contains OR sid_contains) AND status_in AND owner_contains
    """

    asset_contains: list[str] = Field(default_factory=list)
    sid_contains: list[str] = Field(default_factory=list)
    status_in: list[str] = Field(default_factory=list)
    owner_contains: str = ""


class FieldReportConfig(BaseModel):
    """로컬 DFS2 출장 보고 → SF Case/WO."""

    case_activities_field: str = "Activities__c"
    technical_service_record_type_id: str = "0120o000001lQJ5AAM"
    voc_record_type_id: str | None = None
    case_id_cell: str = "T9"
    fse_name_cell: str = "V5"
    report_date_cell: str = "V4"
    summary_cell: str = "B23"
    start_date_cell: str = "L11"
    start_time_cell: str = "L12"
    end_time_cell: str = "L13"
    # Work Order 기본값 (API picklist value)
    default_status: str = "Completed"
    default_equipment_survey: str = "비대상"  # Field25__c
    default_survey: str = "설문 비대상"  # Survey_1__c
    equipment_survey_field: str = "Field25__c"
    survey_field: str = "Survey_1__c"


class Settings(BaseModel):
    automation_enabled_after: datetime
    opt_in_path: Path = Path("data/opt_in.json")
    job_log_path: Path = Path("data/job_log.jsonl")
    idempotency_path: Path = Path("data/idempotency.json")
    routes_path: Path = Path("config/routes.yaml")
    pms_base_url: str = "https://pms.parksystems.com"
    pms_project_id: int = 1
    wo_department_field: str = "Relevant_Department__c"
    pms_api_key_env: str = "PMS_API_KEY"
    sf_instance_url_env: str = "SF_INSTANCE_URL"
    sf_access_token_env: str = "SF_ACCESS_TOKEN"
    sf_org_alias: str = "parksystems"
    pms_custom_fields: PmsCustomFieldsConfig = Field(default_factory=PmsCustomFieldsConfig)
    scan_filters: ScanFiltersConfig = Field(default_factory=ScanFiltersConfig)
    field_report_root: Path | None = None
    field_report: FieldReportConfig = Field(default_factory=FieldReportConfig)
    dry_run: bool = False


def load_settings(path: Path) -> Settings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Settings.model_validate(raw)
