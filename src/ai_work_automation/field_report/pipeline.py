"""출장 보고 파이프라인: 엑셀 일자 시트 → Case Activity → Technical Service WO + 첨부."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ai_work_automation.field_report.excel_ops import (
    DaySheetMeta,
    FieldIssue,
    export_sheet_workbook,
    find_report_workbook,
    format_activity_line,
    format_wo_description,
    list_day_sheets,
    read_day_sheet_meta,
    resolve_report_mode,
    to_sf_datetime,
)
from ai_work_automation.sf.adapter import SafetyError
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.settings import FieldReportConfig
from ai_work_automation.sf.adapter import SalesforceAdapter


@dataclass
class WorkOrderFieldValues:
    status: str
    start_date: str | None
    end_date: str | None
    equipment_survey: str
    survey: str

    def as_preview_rows(self) -> list[dict[str, str]]:
        return [
            {"항목": "Status", "값": self.status},
            {"항목": "Start Date/Time", "값": self.start_date or "(없음)"},
            {"항목": "End Date/Time", "값": self.end_date or "(없음)"},
            {"항목": "장비 실태 조사", "값": self.equipment_survey},
            {"항목": "Survey 여부", "값": self.survey},
        ]


@dataclass
class FieldReportPlan:
    asset_dir: Path
    workbook: Path
    mode: str
    sheet_name: str
    sheet_created: bool
    meta: DaySheetMeta
    activity_line: str
    case_ids: list[str] = field(default_factory=list)
    case_numbers: list[str] = field(default_factory=list)
    wo_subject: str = ""
    wo_fields: WorkOrderFieldValues | None = None


@dataclass
class FieldReportResult:
    status: str
    reason: str | None = None
    details: dict | None = None


def build_wo_fields(
    meta: DaySheetMeta,
    cfg: FieldReportConfig,
    *,
    status: str | None = None,
    equipment_survey: str | None = None,
    survey: str | None = None,
) -> WorkOrderFieldValues:
    return WorkOrderFieldValues(
        status=status or cfg.default_status,
        start_date=to_sf_datetime(meta.start_datetime()),
        end_date=to_sf_datetime(meta.end_datetime()),
        equipment_survey=equipment_survey or cfg.default_equipment_survey,
        survey=survey or cfg.default_survey,
    )


def load_field_report(
    asset_dir: Path,
    *,
    sheet_name: str,
    mode: str | None = None,
    summary: str | None = None,
    fse_name: str | None = None,
    cfg: FieldReportConfig | None = None,
    workbook: Path | None = None,
) -> FieldReportPlan:
    """사용자가 이미 작성한 일자 시트를 읽어 자동화 계획을 만든다 (시트 생성 없음)."""
    cfg = cfg or FieldReportConfig()
    mode = mode or resolve_report_mode(asset_dir)
    workbook = workbook or find_report_workbook(asset_dir, mode=mode)
    if workbook is None:
        raise FileNotFoundError(f"{mode} 리포트 xlsx를 찾을 수 없습니다: {asset_dir}")
    available = list_day_sheets(workbook)
    if sheet_name not in available and sheet_name not in _all_sheet_names(workbook):
        raise FileNotFoundError(
            f"시트 '{sheet_name}' 이(가) 없습니다. 엑셀에서 해당 일자 시트를 만든 뒤 다시 불러오세요."
        )
    meta = read_day_sheet_meta(
        workbook,
        sheet_name,
        case_id_cell=cfg.case_id_cell,
        fse_name_cell=cfg.fse_name_cell,
        report_date_cell=cfg.report_date_cell,
        summary_cell=cfg.summary_cell,
        start_date_cell=cfg.start_date_cell,
        start_time_cell=cfg.start_time_cell,
        end_time_cell=cfg.end_time_cell,
    )
    day = meta.report_date or meta.start_date or _day_from_sheet_name(sheet_name) or date.today()
    fse = fse_name if fse_name is not None else meta.fse_name
    summ = summary if summary is not None else (meta.summary_hint or sheet_name)
    line = format_activity_line(day, fse, summ)
    subject = f"[{asset_dir.parent.name} {asset_dir.name}] {summ[:80]}"
    return FieldReportPlan(
        asset_dir=asset_dir,
        workbook=workbook,
        mode=mode,
        sheet_name=sheet_name,
        sheet_created=False,
        meta=meta,
        activity_line=line,
        case_numbers=list(meta.case_numbers),
        wo_subject=subject,
        wo_fields=build_wo_fields(meta, cfg),
    )


def _all_sheet_names(workbook_path: Path) -> list[str]:
    from ai_work_automation.field_report.excel_ops import load_workbook_resilient

    with load_workbook_resilient(workbook_path, read_only=True) as wb:
        return list(wb.sheetnames)


def _day_from_sheet_name(sheet_name: str) -> date | None:
    try:
        # "2026.08.07" / "2026-08-07" / "2026.08.07(…)"
        base = sheet_name[:10].replace(".", "-")
        return date.fromisoformat(base)
    except ValueError:
        return None


# 하위 호환: 예전 이름
def prepare_field_report(
    asset_dir: Path,
    *,
    day: date | None = None,
    mode: str | None = None,
    summary: str | None = None,
    fse_name: str | None = None,
    cfg: FieldReportConfig | None = None,
    recreate_sheet: bool = False,
) -> FieldReportPlan:
    """deprecated: 시트 생성 없이, 해당 일자 시트명을 찾아 load_field_report 호출."""
    from ai_work_automation.field_report.excel_ops import sheet_name_aliases_for_day

    del recreate_sheet  # 더 이상 시트를 만들지 않음
    mode = mode or resolve_report_mode(asset_dir)
    workbook = find_report_workbook(asset_dir, mode=mode)
    if workbook is None:
        raise FileNotFoundError(f"{mode} 리포트 xlsx를 찾을 수 없습니다: {asset_dir}")
    day = day or date.today()
    aliases = sheet_name_aliases_for_day(day)
    sheets = list_day_sheets(workbook)
    match = next((n for n in sheets if n in aliases), None)
    if match is None:
        match = next((n for n in sheets if any(n.startswith(a) for a in aliases)), None)
    if match is None:
        raise FileNotFoundError(
            f"엑셀에 '{aliases[0]}' / '{aliases[1]}' 시트가 없습니다. "
            "Excel에서 일자 시트를 작성·저장한 뒤 「시트 불러오기」를 사용하세요."
        )
    return load_field_report(
        asset_dir,
        sheet_name=match,
        mode=mode,
        summary=summary,
        fse_name=fse_name,
        cfg=cfg,
    )


def run_field_report(
    plan: FieldReportPlan,
    *,
    sf: SalesforceAdapter,
    opt_in: OptInStore,
    case_ids: list[str],
    dry_run: bool,
    cfg: FieldReportConfig | None = None,
    wo_fields: WorkOrderFieldValues | None = None,
    issues: list[FieldIssue] | None = None,
) -> FieldReportResult:
    cfg = cfg or FieldReportConfig()
    wo = wo_fields or plan.wo_fields or build_wo_fields(plan.meta, cfg)

    active_issues = [i for i in (issues or []) if i.included and i.case_id]
    if active_issues:
        return _run_field_report_issues(
            plan,
            sf=sf,
            opt_in=opt_in,
            dry_run=dry_run,
            cfg=cfg,
            wo=wo,
            issues=active_issues,
        )

    if not case_ids:
        return FieldReportResult(status="skipped", reason="선택된 Case 없음")

    for cid in case_ids:
        opt_in.select(cid)

    preview = {
        "workbook": str(plan.workbook),
        "sheet": plan.sheet_name,
        "activity_line": plan.activity_line,
        "case_ids": case_ids,
        "wo_subject": plan.wo_subject,
        "attach": f"{plan.sheet_name}.xlsx",
        "wo_fields": {
            "Status": wo.status,
            "StartDate": wo.start_date,
            "EndDate": wo.end_date,
            cfg.equipment_survey_field: wo.equipment_survey,
            cfg.survey_field: wo.survey,
        },
    }

    if dry_run:
        return FieldReportResult(status="dry_run", details={"would": preview})

    acted: list[dict] = []
    skipped_existing: list[dict] = []
    extra = {
        cfg.equipment_survey_field: wo.equipment_survey,
        cfg.survey_field: wo.survey,
    }
    failures: list[dict] = []
    work_day = plan.meta.report_date or date.today()
    with tempfile.TemporaryDirectory(prefix="field_report_") as tmp:
        export_path = Path(tmp) / f"{plan.sheet_name}.xlsx"
        export_sheet_workbook(plan.workbook, plan.sheet_name, export_path)
        for cid in case_ids:
            try:
                existing = sf.find_technical_service_wos_on_day(cid, work_day)
                if existing:
                    hit = existing[0]
                    row = {
                        "case_id": cid,
                        "case_number": sf.get_case_number(cid),
                        "work_order_id": hit.id,
                        "work_order_number": hit.work_order_number,
                        "content_version_id": None,
                        "skipped": True,
                    }
                    acted.append(row)
                    skipped_existing.append(row)
                    continue
                # Case Activities = 요약 / WO Description = 상세(동일 요약+맥락)
                sf.append_case_activities(
                    cid,
                    plan.activity_line,
                    case_selected=True,
                    enforce_cutoff=False,
                )
                wo_id = sf.create_technical_service_work_order(
                    case_id=cid,
                    subject=plan.wo_subject,
                    description=(
                        f"{plan.activity_line}\n\n"
                        f"설비: {plan.asset_dir.parent.name} {plan.asset_dir.name}\n"
                        f"(일자 시트 첨부: {plan.sheet_name}.xlsx)"
                    ),
                    status=wo.status,
                    start_date=wo.start_date,
                    end_date=wo.end_date,
                    extra_fields=extra,
                )
                file_id = sf.attach_file_to_record(
                    wo_id, export_path, title=plan.sheet_name
                )
                acted.append(
                    {
                        "case_id": cid,
                        "case_number": sf.get_case_number(cid),
                        "work_order_id": wo_id,
                        "work_order_number": sf.get_work_order_number(wo_id),
                        "content_version_id": file_id,
                        "skipped": False,
                    }
                )
            except (SafetyError, Exception) as exc:  # noqa: BLE001
                failures.append({"case_id": cid, "error": str(exc)})

    if acted and not failures:
        status = "success"
    elif acted and failures:
        status = "partial"
    else:
        status = "error"
    return FieldReportResult(
        status=status,
        reason=(failures[0]["error"] if failures and not acted else None),
        details={
            "acted": acted,
            "failed": failures,
            "applied": preview,
            "skipped_existing": skipped_existing,
        },
    )


def _run_field_report_issues(
    plan: FieldReportPlan,
    *,
    sf: SalesforceAdapter,
    opt_in: OptInStore,
    dry_run: bool,
    cfg: FieldReportConfig,
    wo: WorkOrderFieldValues,
    issues: list[FieldIssue],
) -> FieldReportResult:
    for issue in issues:
        assert issue.case_id
        opt_in.select(issue.case_id)

    asset_label = f"{plan.asset_dir.parent.name} {plan.asset_dir.name}"
    issue_rows = []
    for issue in issues:
        start_sf = to_sf_datetime(issue.start) or wo.start_date
        end_sf = to_sf_datetime(issue.end) or wo.end_date
        subject = f"[{asset_label}] {issue.issue_line[:80]}"
        wo_desc = format_wo_description(
            issue, asset_label=asset_label, fse_name=plan.meta.fse_name
        )
        issue_rows.append(
            {
                "case_id": issue.case_id,
                "case_number": issue.case_number,
                "activity_line": issue.activity_line,  # Case Activities 요약
                "wo_description": wo_desc,  # WO Description 상세
                "wo_subject": subject,
                "start_date": start_sf,
                "end_date": end_sf,
            }
        )

    preview = {
        "workbook": str(plan.workbook),
        "sheet": plan.sheet_name,
        "attach": f"{plan.sheet_name}.xlsx",
        "mode": "multi_issue",
        "issues": issue_rows,
        "wo_fields_common": {
            "Status": wo.status,
            cfg.equipment_survey_field: wo.equipment_survey,
            cfg.survey_field: wo.survey,
        },
    }
    if dry_run:
        return FieldReportResult(status="dry_run", details={"would": preview})

    acted: list[dict] = []
    skipped_existing: list[dict] = []
    failures: list[dict] = []
    extra = {
        cfg.equipment_survey_field: wo.equipment_survey,
        cfg.survey_field: wo.survey,
    }
    work_day = plan.meta.report_date or date.today()
    with tempfile.TemporaryDirectory(prefix="field_report_") as tmp:
        export_path = Path(tmp) / f"{plan.sheet_name}.xlsx"
        export_sheet_workbook(plan.workbook, plan.sheet_name, export_path)
        for row in issue_rows:
            cid = row["case_id"]
            assert cid
            try:
                existing = sf.find_technical_service_wos_on_day(cid, work_day)
                if existing:
                    hit = existing[0]
                    skip_row = {
                        "case_id": cid,
                        "case_number": row["case_number"],
                        "work_order_id": hit.id,
                        "work_order_number": hit.work_order_number,
                        "content_version_id": None,
                        "activity_line": row["activity_line"],
                        "skipped": True,
                    }
                    acted.append(skip_row)
                    skipped_existing.append(skip_row)
                    continue
                # Case Detail > Activities = 요약 한 줄
                sf.append_case_activities(
                    cid,
                    row["activity_line"],
                    case_selected=True,
                    enforce_cutoff=False,
                )
                # Work Order Description = 상세
                wo_id = sf.create_technical_service_work_order(
                    case_id=cid,
                    subject=row["wo_subject"],
                    description=row["wo_description"],
                    status=wo.status,
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    extra_fields=extra,
                )
                file_id = sf.attach_file_to_record(
                    wo_id, export_path, title=plan.sheet_name
                )
                acted.append(
                    {
                        "case_id": cid,
                        "case_number": row["case_number"],
                        "work_order_id": wo_id,
                        "work_order_number": sf.get_work_order_number(wo_id),
                        "content_version_id": file_id,
                        "activity_line": row["activity_line"],
                        "skipped": False,
                    }
                )
            except (SafetyError, Exception) as exc:  # noqa: BLE001
                failures.append(
                    {
                        "case_id": cid,
                        "case_number": row["case_number"],
                        "error": str(exc),
                    }
                )

    if acted and not failures:
        status = "success"
    elif acted and failures:
        status = "partial"
    else:
        status = "error"
    return FieldReportResult(
        status=status,
        reason=(failures[0]["error"] if failures and not acted else None),
        details={
            "acted": acted,
            "failed": failures,
            "applied": preview,
            "skipped_existing": skipped_existing,
        },
    )
