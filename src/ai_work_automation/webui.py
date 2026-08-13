"""로컬 웹 UI (Streamlit).

실행: streamlit run src/ai_work_automation/webui.py
CLI와 같은 파이프라인/서비스 코드를 재사용한다.
"""

from __future__ import annotations

import importlib
import re
import tempfile
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from streamlit_quill import st_quill

# Streamlit은 메인 스크립트만 재실행하고 의존 모듈은 sys.modules에 남을 수 있음
import ai_work_automation.field_report.excel_ops as _fr_excel_ops
import ai_work_automation.field_report.mail_template as _fr_mail_template
import ai_work_automation.field_report.outlook_com as _fr_outlook
import ai_work_automation.field_report.pipeline as _fr_pipeline
import ai_work_automation.sf.adapter as _sf_adapter

importlib.reload(_fr_excel_ops)
importlib.reload(_fr_mail_template)
importlib.reload(_fr_outlook)
importlib.reload(_fr_pipeline)
importlib.reload(_sf_adapter)

from ai_work_automation.connectors.pms import PmsConnector
from ai_work_automation.field_report.excel_ops import (
    FieldIssue,
    export_sheet_workbook,
    find_report_workbook,
    find_time_overlaps,
    format_activity_line,
    list_asset_folders,
    list_customers,
    list_day_sheets,
    list_report_workbooks,
    parse_field_issues,
    render_sheet_preview_png,
    resolve_report_mode,
    sheet_name_aliases_for_day,
    sheet_to_html,
    split_workday_slots,
    to_sf_datetime,
)
from ai_work_automation.field_report.mail_template import ETHAN_EMAIL, build_mail_draft
from ai_work_automation.field_report.outlook_com import MailSendRequest, send_mail_via_outlook
from ai_work_automation.sf.adapter import SafetyError, SalesforceAdapter  # noqa: F401 — reload 반영
from ai_work_automation.field_report.pipeline import (
    build_wo_fields,
    load_field_report,
    run_field_report,
)
from ai_work_automation.idempotency import JsonIdempotencyStore
from ai_work_automation.job_log import JobLogStore
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.pipeline import run_case_automation
from ai_work_automation.router import load_routes
from ai_work_automation.services import scan_candidates, status_overview
from ai_work_automation.settings import load_settings
from ai_work_automation.ui_theme import inject_apple_theme, render_app_hero

load_dotenv()

SETTINGS_PATH = Path("config/settings.yaml")

st.set_page_config(
    page_title="AI 업무 자동화",
    page_icon="◇",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_apple_theme()

# Streamlit 기본 단축키 'C'(Clear cache)가 캡처/입력 중 뜨는 것을 차단
components.html(
    """
<script>
(() => {
  const doc = window.parent.document;
  if (doc.__frBlockCacheKey) return;
  doc.__frBlockCacheKey = true;
  doc.addEventListener('keydown', (e) => {
    const t = e.target;
    const tag = (t && t.tagName) ? t.tagName.toUpperCase() : '';
    const typing = tag === 'INPUT' || tag === 'TEXTAREA' || (t && t.isContentEditable);
    if (!typing && (e.key === 'c' || e.key === 'C') && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.stopPropagation();
      e.preventDefault();
    }
  }, true);
})();
</script>
""",
    height=0,
    width=0,
)

STATUS_OPTIONS = [
    "New",
    "Internal Review",
    "In Progress",
    "On Hold",
    "Completed",
    "Closed",
    "Cannot Complete",
    "Canceled",
]


def _settings():
    return load_settings(SETTINGS_PATH)


def _sf(s):
    # cli의 헬퍼 재사용 (지연 임포트로 순환 참조 방지)
    from ai_work_automation.cli import _make_sf_adapter

    return _make_sf_adapter(s)


def _pms(s):
    import os

    client = httpx.Client(base_url=s.pms_base_url, timeout=60.0)
    return client, PmsConnector(
        client=client,
        api_key=os.environ.get(s.pms_api_key_env, ""),
        base_url=s.pms_base_url,
    )


def _run_pipeline(s, case_id: str, *, dry_run: bool, issue_type: str | None,
                  only_wo_ids: set[str] | None = None,
                  draft_overrides: dict[str, dict[str, str]] | None = None):
    sf_client, sf = _sf(s)
    pms_http, pms = _pms(s)
    try:
        return run_case_automation(
            case_id=case_id,
            opt_in=OptInStore(s.opt_in_path),
            job_log=JobLogStore(s.job_log_path),
            sf=sf,
            routes=load_routes(s.routes_path),
            pms=pms,
            cutoff=s.automation_enabled_after,
            pms_project_id=s.pms_project_id,
            approve_fn=lambda _d: True,  # UI에서 승인 버튼이 Human Gate 역할
            idempotency=JsonIdempotencyStore(s.idempotency_path),
            dry_run=dry_run,
            issue_type=issue_type,
            custom_fields_config=s.pms_custom_fields,
            only_work_order_ids=only_wo_ids,
            draft_overrides=draft_overrides,
        )
    finally:
        sf_client.close()
        pms_http.close()


def _html_preview_box(body_html: str, height: int = 280) -> None:
    # 시스템 다크 테마와 무관하게 항상 흰 배경 + 검정 글자로 고정 (실제 PMS 화면과 동일)
    components.html(
        '<div style="background:#ffffff;color:#1a1a1a;'
        'border:1px solid #ccc;border-radius:6px;padding:14px;'
        "font-family:'Malgun Gothic',sans-serif;font-size:14px;line-height:1.6\">"
        f"{body_html}</div>",
        height=height,
        scrolling=True,
    )


# PMS 본문용 툴바: 볼드/색상/목록 등 (코드·수식 제외)
_QUILL_TOOLBAR = [
    ["bold", "italic", "underline", "strike"],
    [{"color": []}, {"background": []}],
    [{"header": [1, 2, 3, False]}],
    [{"list": "ordered"}, {"list": "bullet"}],
    [{"indent": "-1"}, {"indent": "+1"}, {"align": []}],
    ["link", "clean"],
]


def _uploaded_images_html(files, width_px: int) -> str:
    """업로드된 이미지들을 base64로 본문에 내장한다 (PMS 에디터와 같은 방식)."""
    import base64

    parts = []
    for f in files or []:
        encoded = base64.b64encode(f.getvalue()).decode("ascii")
        mime = f.type or "image/png"
        parts.append(
            f'<p><img src="data:{mime};base64,{encoded}" '
            f'style="width:{width_px}px;max-width:100%" alt="{f.name}" /></p>'
        )
    return "\n".join(parts)


def _body_state_key(key_prefix: str, wo_id: str) -> str:
    return f"{key_prefix}_body_{wo_id}"


def _render_editable_item(item: dict, key_prefix: str) -> None:
    """미리보기 항목 하나를 편집 가능한 형태로 렌더링한다."""
    wo_id = item["work_order_id"]
    body_key = _body_state_key(key_prefix, wo_id)
    action = "기존 이슈에 댓글" if item["action"] == "comment" else "신규 이슈 생성"
    st.markdown(
        f"**동작**: {action}"
        + (f" (#{item['issue_id']})" if item.get("issue_id") else "")
        + (f" / 타입: {item.get('issue_type')}" if item.get("issue_type") else "")
    )
    if item.get("custom_fields"):
        st.markdown(
            "**커스텀 필드**: "
            + ", ".join(f"{f['id']}={f['value']}" for f in item["custom_fields"])
        )

    st.text_input("제목 (수정 가능)", value=item["title"], key=f"{key_prefix}_title_{wo_id}")

    st.caption("본문 — 일반 편집기 (볼드·색상·목록 등)")
    # seed는 미리보기 생성 시 한 번만 고정 (rerun 시 Quill이 초기화되지 않도록)
    seed_key = f"{key_prefix}_body_seed_{wo_id}"
    if seed_key not in st.session_state:
        st.session_state[seed_key] = item["body"] or ""
        st.session_state[body_key] = st.session_state[seed_key]
    edited = st_quill(
        value=st.session_state[seed_key],
        html=True,
        toolbar=_QUILL_TOOLBAR,
        key=f"{key_prefix}_quill_{wo_id}",
    )
    if edited is not None:
        st.session_state[body_key] = edited

    col_img, col_w = st.columns([3, 1])
    with col_img:
        st.file_uploader(
            "이미지 첨부 (본문 하단에 내장됨)",
            type=["png", "jpg", "jpeg", "gif"],
            accept_multiple_files=True,
            key=f"{key_prefix}_imgs_{wo_id}",
        )
    with col_w:
        st.number_input(
            "이미지 너비(px)",
            min_value=100,
            max_value=1400,
            value=600,
            step=50,
            key=f"{key_prefix}_imgw_{wo_id}",
        )

    st.markdown("**등록될 모습 미리보기** (이미지 포함):")
    _html_preview_box(_final_body(item, key_prefix))
    st.divider()


def _final_body(item: dict, key_prefix: str) -> str:
    """편집된 본문 + 내장 이미지가 합쳐진 최종 본문."""
    wo_id = item["work_order_id"]
    body = st.session_state.get(_body_state_key(key_prefix, wo_id), item["body"]) or ""
    files = st.session_state.get(f"{key_prefix}_imgs_{wo_id}")
    width = int(st.session_state.get(f"{key_prefix}_imgw_{wo_id}", 600))
    images_html = _uploaded_images_html(files, width)
    if images_html:
        body = f"{body}\n<p>&nbsp;</p>\n{images_html}"
    return body


def _collect_overrides(previews, key_prefix: str) -> dict[str, dict[str, str]]:
    overrides: dict[str, dict[str, str]] = {}
    for _case_id, _wo_ids, result in previews:
        for item in (result.details or {}).get("would_post", []):
            wo_id = item["work_order_id"]
            overrides[wo_id] = {
                "title": st.session_state.get(f"{key_prefix}_title_{wo_id}", item["title"]),
                "body": _final_body(item, key_prefix),
            }
    return overrides


def _clear_draft_edit_state(key_prefix: str) -> None:
    """미리보기 재생성 시 이전 본문/이미지 편집 상태를 지운다."""
    for key in list(st.session_state.keys()):
        if (
            key.startswith(f"{key_prefix}_body_")
            or key.startswith(f"{key_prefix}_quill_")
            or key.startswith(f"{key_prefix}_imgs_")
            or key.startswith(f"{key_prefix}_imgw_")
            or key.startswith(f"{key_prefix}_title_")
        ):
            del st.session_state[key]


def _process_selection(s, targets: list, issue_type: str | None, key_prefix: str) -> None:
    """선택된 워크오더들(케이스별 그룹)을 미리보기 -> 편집 -> 승인 -> 등록하는 공용 위젯."""
    if st.button("미리보기 (dry-run)", key=f"{key_prefix}_preview"):
        _clear_draft_edit_state(key_prefix)
        opt = OptInStore(s.opt_in_path)
        previews = []
        with st.spinner("초안 생성 중..."):
            case_groups: dict[str, set[str]] = {}
            for t in targets:
                case_groups.setdefault(t.case_id, set()).add(t.work_order_id)
            for case_id, wo_ids in case_groups.items():
                opt.select(case_id)
                result = _run_pipeline(
                    s, case_id, dry_run=True, issue_type=issue_type, only_wo_ids=wo_ids
                )
                previews.append((case_id, wo_ids, result))
        st.session_state[f"{key_prefix}_previews"] = previews

    previews = st.session_state.get(f"{key_prefix}_previews")
    if not previews:
        return

    total_items = 0
    for case_id, _wo_ids, result in previews:
        would = (result.details or {}).get("would_post", [])
        total_items += len(would)
        if not would:
            st.warning(f"케이스 {case_id}: 등록할 항목 없음 (이미 연동/컷오프/라우팅 제외)")
        else:
            for item in would:
                _render_editable_item(item, key_prefix)

    if total_items == 0:
        return

    confirmed = st.checkbox(
        f"위 {total_items}건을 확인했으며 실제 등록에 동의합니다", key=f"{key_prefix}_confirm"
    )
    if st.button("실제 등록", type="primary", disabled=not confirmed, key=f"{key_prefix}_real"):
        overrides = _collect_overrides(previews, key_prefix)
        with st.spinner("PMS 등록 및 Salesforce 기록 중..."):
            for case_id, wo_ids, _r in previews:
                real = _run_pipeline(
                    s,
                    case_id,
                    dry_run=False,
                    issue_type=issue_type,
                    only_wo_ids=wo_ids,
                    draft_overrides=overrides,
                )
                if real.status == "success":
                    for acted in (real.details or {}).get("acted", []):
                        st.success(f"완료: {acted['url']} ({acted['action']})")
                else:
                    st.error(f"케이스 {case_id}: {real.status} / {real.reason or ''}")
        st.session_state.pop(f"{key_prefix}_previews", None)
        st.session_state.pop("scan_rows", None)


def _field_preview_stem(workbook: Path, sheet_name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", f"{workbook.stem}_{sheet_name}")


def _clear_field_preview_cache(workbook: Path, sheet_name: str) -> None:
    """시트 재로드 시 옛 PNG 미리보기를 제거한다."""
    prev = Path("output") / "field_report_previews"
    if not prev.is_dir():
        return
    stem = _field_preview_stem(workbook, sheet_name)
    for f in prev.glob(f"{stem}_*.png"):
        f.unlink(missing_ok=True)


def _render_field_sheet_preview(
    workbook: Path,
    sheet_name: str,
    *,
    title: str | None = None,
    key_prefix: str = "fr_preview",
) -> None:
    """첨부·메일과 동일한 crop 범위 미리보기 (Excel PNG 우선, HTML 폴백)."""
    st.markdown(
        title
        or "**엑셀 시트 미리보기** (첨부·메일과 동일 — 하단「작업 종료 후 근무 형태」제외)"
    )
    width_key = f"{key_prefix}_width"
    if width_key not in st.session_state and "fr_preview_width" in st.session_state:
        # 메인/ dry-run 미리보기 너비 동기화
        st.session_state[width_key] = st.session_state["fr_preview_width"]
    width_pct = st.slider(
        "미리보기 너비",
        min_value=30,
        max_value=100,
        value=55,
        step=5,
        format="%d%%",
        key=width_key,
        help="화면에서 미리보기 이미지 크기만 조절합니다. 첨부 파일에는 영향 없습니다.",
    )
    safe = _field_preview_stem(workbook, sheet_name)
    mtime = int(workbook.stat().st_mtime) if workbook.is_file() else 0
    png_path = Path("output") / "field_report_previews" / f"{safe}_{mtime}.png"
    try:
        if not png_path.is_file():
            with st.spinner("엑셀과 동일하게 미리보기 이미지 생성 중..."):
                render_sheet_preview_png(workbook, sheet_name, png_path)
        # columns 비율로 표시 폭 조절 (use_container_width는 항상 전체 폭)
        show_col, _ = st.columns([width_pct, max(100 - width_pct, 1)])
        with show_col:
            st.image(str(png_path), use_container_width=True)
        st.caption(f"미리보기 범위: crop된 시트 상단 (파일: `{png_path.name}`)")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"이미지 미리보기 실패 → HTML 대체 표시 ({exc})")
        try:
            html_h = int(280 + width_pct * 4)
            components.html(
                sheet_to_html(workbook, sheet_name),
                height=html_h,
                scrolling=True,
            )
        except Exception as html_exc:  # noqa: BLE001
            st.warning(f"시트 미리보기 실패: {html_exc}")


def _apply_existing_wo_mail_ctx(
    *,
    customer: str,
    asset_name: str,
    report_day: date,
    fse_name: str,
    short_title: str,
    workbook: Path,
    sheet_name: str,
    existing_rows: list[dict],
    sf_instance_url: str = "",
) -> None:
    """이미 있는 WO로 메일 초안 컨텍스트를 연다."""
    if not existing_rows:
        return
    case_refs = [
        {"number": r["case_number"], "id": r.get("case_id") or ""}
        for r in existing_rows
        if r.get("case_number")
    ]
    # Case 중복 제거 (같은 Case에 WO 여러 개일 수 있음)
    seen: set[str] = set()
    uniq_cases: list[dict[str, str]] = []
    for ref in case_refs:
        key = ref["number"]
        if key in seen:
            continue
        seen.add(key)
        uniq_cases.append(ref)
    wo_refs = [
        {
            "number": r.get("work_order_number") or "",
            "id": r.get("work_order_id") or "",
        }
        for r in existing_rows
        if r.get("work_order_id")
    ]
    st.session_state["fr_mail_ctx"] = {
        "customer": customer,
        "asset_folder": asset_name,
        "work_day": report_day.isoformat(),
        "fse_name": fse_name,
        "case_numbers": [c["number"] for c in uniq_cases],
        "wo_numbers": [w["number"] for w in wo_refs if w["number"]],
        "case_refs": uniq_cases,
        "wo_refs": wo_refs,
        "sf_instance_url": sf_instance_url,
        "short_title": short_title or sheet_name,
        "workbook": str(workbook),
        "sheet_name": sheet_name,
    }


def _lookup_existing_field_wos(
    sf: SalesforceAdapter,
    *,
    case_entries: list[tuple[str, str]],
    work_day: date,
) -> list[dict]:
    """(case_id, case_number) → 당일 Technical Service WO 목록."""
    rows: list[dict] = []
    for case_id, case_number in case_entries:
        if not case_id:
            continue
        for wo in sf.find_technical_service_wos_on_day(case_id, work_day):
            rows.append(
                {
                    "case_id": case_id,
                    "case_number": case_number,
                    "work_order_id": wo.id,
                    "work_order_number": wo.work_order_number,
                }
            )
    return rows


def _render_field_mail_section() -> None:
    """등록 성공 후 또는 기존 WO 감지 시 작업보고 메일 초안 편집·전송."""
    ctx = st.session_state.get("fr_mail_ctx")
    if not ctx:
        return

    st.divider()
    st.subheader("작업보고 메일")
    st.caption(
        f"From / Bcc: `{ETHAN_EMAIL}` · To/Cc는 아래에서 입력 후 Tool에서 바로 전송합니다."
    )

    if st.button("메일 초안 만들기", key="fr_mail_build"):
        work_day = date.fromisoformat(ctx["work_day"])
        draft = build_mail_draft(
            customer=ctx["customer"],
            asset_folder=ctx["asset_folder"],
            work_day=work_day,
            fse_name=ctx["fse_name"],
            case_numbers=list(ctx.get("case_numbers") or []),
            wo_numbers=list(ctx.get("wo_numbers") or []),
            case_refs=list(ctx.get("case_refs") or []),
            wo_refs=list(ctx.get("wo_refs") or []),
            sf_instance_url=ctx.get("sf_instance_url") or "",
            short_title=ctx.get("short_title") or "작업보고",
        )
        mail_dir = Path(tempfile.mkdtemp(prefix="fr_mail_"))
        png_path = mail_dir / "sheet.png"
        xlsx_path = mail_dir / f"{ctx['sheet_name']}.xlsx"
        wb = Path(ctx["workbook"])
        sheet = ctx["sheet_name"]
        try:
            render_sheet_preview_png(wb, sheet, png_path)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"메일용 PNG 생성 실패(본문만 진행): {exc}")
            png_path = None  # type: ignore[assignment]
        try:
            export_sheet_workbook(wb, sheet, xlsx_path)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"xlsx 첨부 준비 실패: {exc}")
            xlsx_path = None  # type: ignore[assignment]
        st.session_state["fr_mail_draft"] = {
            "png_path": str(png_path) if png_path else "",
            "xlsx_path": str(xlsx_path) if xlsx_path else "",
        }
        st.session_state["fr_mail_to"] = ""
        st.session_state["fr_mail_cc"] = ""
        st.session_state["fr_mail_subject"] = draft.subject
        st.session_state["fr_mail_body_seed"] = draft.body_html
        st.session_state["fr_mail_body"] = draft.body_html
        st.session_state["fr_mail_quill_n"] = (
            int(st.session_state.get("fr_mail_quill_n", 0)) + 1
        )
        st.session_state["fr_mail_attach_xlsx"] = True
        st.session_state.pop("fr_mail_sent", None)
        st.session_state.pop("fr_mail_confirm", None)
        st.rerun()

    draft = st.session_state.get("fr_mail_draft")
    if not draft:
        return

    st.text_input("From", value=ETHAN_EMAIL, disabled=True, key="fr_mail_from")
    to = st.text_input("To (필수)", key="fr_mail_to")
    cc = st.text_input("Cc", key="fr_mail_cc")
    st.text_input("Bcc", value=ETHAN_EMAIL, disabled=True, key="fr_mail_bcc")
    subject = st.text_input("제목", key="fr_mail_subject")
    st.caption("본문 — 볼드·글자색 등 편집 가능 (맑은 고딕 11pt 초안 / 서명은 파란 10pt)")
    quill_n = int(st.session_state.get("fr_mail_quill_n", 0))
    seed = st.session_state.get("fr_mail_body_seed") or ""
    edited = st_quill(
        value=seed,
        html=True,
        toolbar=_QUILL_TOOLBAR,
        key=f"fr_mail_quill_{quill_n}",
    )
    if edited is not None:
        st.session_state["fr_mail_body"] = edited
    body = st.session_state.get("fr_mail_body") or seed
    attach_xlsx = st.checkbox("일자 시트 xlsx 파일 첨부", key="fr_mail_attach_xlsx")
    png = Path(draft["png_path"]) if draft.get("png_path") else None
    if png and png.is_file():
        st.markdown("**작업내용 PNG 미리보기**")
        st.image(str(png), use_container_width=True)

    send_ok = st.checkbox("위 내용으로 메일을 전송합니다", key="fr_mail_confirm")
    if st.button(
        "메일 전송",
        type="primary",
        disabled=not send_ok or not (to or "").strip(),
        key="fr_mail_send",
    ):
        xlsx = Path(draft["xlsx_path"]) if draft.get("xlsx_path") else None
        req = MailSendRequest(
            to=to or "",
            cc=cc or "",
            subject=subject or "",
            body_html=body or "",
            png_path=png if png and png.is_file() else None,
            xlsx_path=xlsx if attach_xlsx and xlsx and xlsx.is_file() else None,
        )
        try:
            with st.spinner("Outlook으로 전송 중..."):
                send_mail_via_outlook(req)
            st.session_state["fr_mail_sent"] = True
            st.success(f"메일을 전송했습니다. (From/Bcc: {ETHAN_EMAIL})")
        except Exception as exc:  # noqa: BLE001
            st.error(f"메일 전송 실패: {exc}")

    if st.session_state.get("fr_mail_sent"):
        st.info("전송 완료. Outlook 보낸 편지함에서 확인하세요.")


def _render_field_report_tab(s) -> None:
    """출장 보고: 로컬 DFS2 엑셀 → Case Activity → Technical Service WO + 첨부."""
    root = s.field_report_root
    if not root:
        st.warning(
            "config/settings.yaml 에 field_report_root 를 설정하세요. "
            "예: C:\\\\Users\\\\…\\\\OneDrive - Park Systems\\\\DFS2 - General\\\\DFS2"
        )
        return
    root = Path(root)
    if not root.is_dir():
        st.error(f"경로 없음: {root}")
        return

    st.caption(f"DFS2 루트: `{root}`")
    customers = list_customers(root)
    if not customers:
        st.info("고객 폴더가 없습니다. OneDrive 동기화를 확인하세요.")
        return

    st.info(
        "흐름: ① Excel에서 일자 시트를 직접 작성·저장 → ② 아래에서 시트를 불러오기 → "
        "③ Case Activity / WO 자동 등록"
    )
    c1, c2 = st.columns(2)
    with c1:
        customer = st.selectbox("고객", customers, index=customers.index("SDC") if "SDC" in customers else 0)
    assets = list_asset_folders(root, customer)
    with c2:
        asset_names = [p.name for p in assets]
        asset_name = st.selectbox("설비 폴더", asset_names) if asset_names else None

    if not asset_name:
        return
    asset_dir = root / customer / asset_name
    mode_label = st.radio(
        "리포트 종류",
        ["자동", "Field Service", "Installation"],
        horizontal=True,
        key="fr_mode",
    )
    mode_map = {"Field Service": "field_service", "Installation": "installation"}
    mode = mode_map.get(mode_label) or resolve_report_mode(asset_dir)
    workbooks = list_report_workbooks(asset_dir, mode=mode)
    if not workbooks:
        st.warning(f"{mode} 리포트 xlsx가 이 설비 폴더에 없습니다.")
        return

    refresh_key = f"fr_sheet_refresh_{asset_dir}"
    refresh_n = int(st.session_state.get(refresh_key, 0))
    wb_names = [p.name for p in workbooks]
    workbook_name = st.selectbox(
        "리포트 파일 (연도별 파일이면 해당 연도 선택)",
        wb_names,
        index=0,
        key=f"fr_wb_sel_{asset_dir.name}_{refresh_n}",
        help="사람마다 파일 명명/연도 분리가 다릅니다. 목록에서 직접 고르세요.",
    )
    workbook = next(p for p in workbooks if p.name == workbook_name)

    try:
        day_sheets = list_day_sheets(workbook)
    except PermissionError:
        st.error(
            "엑셀 파일을 읽을 수 없습니다(잠금/권한). "
            "데스크톱 Excel에서 저장한 뒤 「새로고침」을 눌러 주세요. "
            "(열어 둔 상태에서도 보통은 자동 복사로 읽습니다. 이 메시지가 보이면 복사진송도 실패했습니다.)"
        )
        if st.button("새로고침", key="fr_refresh_sheets_locked"):
            st.session_state[refresh_key] = refresh_n + 1
            st.session_state.pop("fr_plan", None)
            st.rerun()
        return

    mtime = datetime.fromtimestamp(workbook.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    st.caption(f"파일: `{workbook}` · 로컬 수정시각: {mtime}")

    if not day_sheets:
        st.warning(
            f"`{workbook.name}` 에 일자 시트가 없습니다. "
            "지원 형식: `2026.08.07` / `2026-08-07` / `0807`(연도파일의 MMDD). "
            "Excel에서 시트를 저장한 뒤 「새로고침」을 누르세요."
        )
        if st.button("새로고침", key="fr_refresh_sheets_empty"):
            st.session_state[refresh_key] = refresh_n + 1
            st.session_state.pop("fr_plan", None)
            st.rerun()
        return

    today_aliases = set(sheet_name_aliases_for_day(date.today()))
    default_idx = 0
    for i, name in enumerate(day_sheets):
        if name in today_aliases or any(name.startswith(a) for a in today_aliases):
            default_idx = i
            break

    sel_col, ref_col = st.columns([4, 1])
    with sel_col:
        sheet_name = st.selectbox(
            "불러올 일자 시트 (YYYY.MM.DD 또는 MMDD)",
            day_sheets,
            index=default_idx,
            key=f"fr_sheet_sel_{asset_dir.name}_{workbook.name}_{refresh_n}",
        )
    with ref_col:
        st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if st.button(
            "새로고침",
            key="fr_refresh_sheets",
            help="데스크톱 Excel 저장 후 로컬 파일에서 시트 목록을 다시 읽습니다",
        ):
            st.session_state[refresh_key] = refresh_n + 1
            st.session_state.pop("fr_plan", None)
            st.rerun()

    if st.button("시트 불러오기", type="primary", key="fr_load"):
        try:
            plan = load_field_report(
                asset_dir,
                sheet_name=sheet_name,
                mode=mode,
                cfg=s.field_report,
                workbook=workbook,
            )
            st.session_state["fr_plan"] = plan
            # widget key는 한 번 생기면 value=를 무시하므로 엑셀 값으로 강제 갱신
            st.session_state["fr_fse"] = plan.meta.fse_name or ""
            st.session_state["fr_sum"] = plan.meta.summary_hint or ""
            start_dt = plan.meta.start_datetime()
            end_dt = plan.meta.end_datetime()
            st.session_state["fr_start_d"] = (
                start_dt.date() if start_dt else (plan.meta.report_date or date.today())
            )
            st.session_state["fr_start_t"] = (
                start_dt.time() if start_dt else (plan.meta.start_time or time(9, 0))
            )
            st.session_state["fr_end_d"] = (
                end_dt.date()
                if end_dt
                else (plan.meta.report_date or date.today())
            )
            st.session_state["fr_end_t"] = (
                end_dt.time() if end_dt else (plan.meta.end_time or time(18, 0))
            )
            day = (
                plan.meta.report_date
                or plan.meta.start_date
                or date.today()
            )
            tz = ZoneInfo("Asia/Seoul")
            work_start = start_dt or datetime.combine(day, time(9, 0), tzinfo=tz)
            work_end = end_dt or datetime.combine(day, time(18, 0), tzinfo=tz)
            if work_start.tzinfo is None:
                work_start = work_start.replace(tzinfo=tz)
            if work_end.tzinfo is None:
                work_end = work_end.replace(tzinfo=tz)
            st.session_state["fr_issues"] = parse_field_issues(
                plan.workbook,
                plan.sheet_name,
                day=day,
                fse_name=plan.meta.fse_name or "",
                work_start=work_start,
                work_end=work_end,
            )
            st.session_state.pop("fr_extra_issue_rows", None)
            _clear_field_preview_cache(plan.workbook, plan.sheet_name)
            st.success(f"불러옴: {plan.sheet_name}")
            st.rerun()
        except PermissionError:
            st.error("파일이 잠겨 있습니다. Excel에서 저장·닫은 뒤 다시 불러오세요.")
            return
        except Exception as exc:  # noqa: BLE001 — UI에 원인 표시
            st.error(str(exc))
            return

    plan = st.session_state.get("fr_plan")
    if not plan or Path(plan.asset_dir) != asset_dir or plan.sheet_name != sheet_name:
        st.info(
            "브라우저/SharePoint에서 수정한 경우 OneDrive 동기화 후 "
            "「새로고침」→「시트 불러오기」를 다시 누르세요. "
            "(이 도구는 클라우드가 아니라 로컬 동기화 파일을 읽습니다.)"
        )
        return

    report_day = (
        plan.meta.report_date
        or plan.meta.start_date
        or date.today()
    )

    local_mtime = datetime.fromtimestamp(plan.workbook.stat().st_mtime).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    st.markdown(
        f"**파일**: `{plan.workbook.name}` · **모드**: {plan.mode} · **시트**: {plan.sheet_name}"
    )
    st.caption(f"로컬 파일 수정시각: {local_mtime} (이 시각 이후 클라우드 수정분은 동기화·재로드 필요)")
    _render_field_sheet_preview(plan.workbook, plan.sheet_name)

    fse_name = st.text_input("출장자", key="fr_fse")
    if "fr_issues" not in st.session_state:
        # 구 세션 호환: 로드된 시트에서 이슈 재파싱
        tz0 = ZoneInfo("Asia/Seoul")
        ws0 = plan.meta.start_datetime() or datetime.combine(
            report_day, time(9, 0), tzinfo=tz0
        )
        we0 = plan.meta.end_datetime() or datetime.combine(
            report_day, time(18, 0), tzinfo=tz0
        )
        if ws0.tzinfo is None:
            ws0 = ws0.replace(tzinfo=tz0)
        if we0.tzinfo is None:
            we0 = we0.replace(tzinfo=tz0)
        st.session_state["fr_issues"] = parse_field_issues(
            plan.workbook,
            plan.sheet_name,
            day=report_day,
            fse_name=fse_name or plan.meta.fse_name or "",
            work_start=ws0,
            work_end=we0,
        )
    issues: list[FieldIssue] = list(st.session_state.get("fr_issues") or [])
    multi_mode = len(issues) > 0
    if not multi_mode:
        summary = st.text_input("작업 요약 (Case Activity용)", key="fr_sum")
    else:
        summary = ""
        st.caption(
            f"Daily Note에서 이슈 {len(issues)}건을 인식했습니다. "
            "Case Activity는 각 이슈 줄만 사용합니다."
        )

    st.subheader("Work Order 세부 설정")
    meta = plan.meta
    start_default = meta.start_datetime()
    end_default = meta.end_datetime()
    tz = ZoneInfo("Asia/Seoul")

    wc1, wc2 = st.columns(2)
    with wc1:
        wo_status = st.selectbox(
            "Status",
            [
                "Completed",
                "New",
                "In Progress",
                "Internal Review",
                "Quote",
                "PO",
                "Request to Review",
                "Logistics/Closed",
            ],
            index=0,
            key="fr_status",
        )
        equip_survey = st.selectbox(
            "장비 실태 조사",
            ["비대상", "대상"],
            index=0,
            key="fr_equip",
        )
    with wc2:
        survey_val = st.selectbox(
            "Survey 여부",
            ["설문 비대상", "진행 필요", "완료", "비대면 설문 완료"],
            index=0,
            key="fr_survey",
        )
        if "fr_start_d" not in st.session_state:
            st.session_state["fr_start_d"] = (
                start_default.date() if start_default else report_day
            )
        if "fr_start_t" not in st.session_state:
            st.session_state["fr_start_t"] = (
                start_default.time() if start_default else time(9, 0)
            )
        if "fr_end_d" not in st.session_state:
            st.session_state["fr_end_d"] = (
                end_default.date() if end_default else report_day
            )
        if "fr_end_t" not in st.session_state:
            st.session_state["fr_end_t"] = (
                end_default.time() if end_default else time(18, 0)
            )
        st.caption("근무 구간 (균등 분할 기준)")
        start_d = st.date_input("Workday Start Date", key="fr_start_d")
        start_t = st.time_input("Workday Start Time", key="fr_start_t")
        end_d = st.date_input("Workday End Date", key="fr_end_d")
        end_t = st.time_input("Workday End Time", key="fr_end_t")

    work_start = datetime.combine(start_d, start_t, tzinfo=tz)
    work_end = datetime.combine(end_d, end_t, tzinfo=tz)
    wo_fields = build_wo_fields(
        meta,
        s.field_report,
        status=wo_status,
        equipment_survey=equip_survey,
        survey=survey_val,
    )
    wo_fields.start_date = to_sf_datetime(work_start)
    wo_fields.end_date = to_sf_datetime(work_end)

    sf_client, sf = _sf(s)
    try:
        run_issues: list[FieldIssue] = []
        case_ids: list[str] = []
        activity_line = format_activity_line(report_day, fse_name, summary or plan.sheet_name)

        if multi_mode:
            if st.button("균등 분할 다시 적용", key="fr_resplit"):
                all_for_split = issues + list(
                    st.session_state.get("fr_extra_issue_rows") or []
                )
                slots = split_workday_slots(work_start, work_end, len(all_for_split))
                for issue, (sdt, edt) in zip(all_for_split, slots, strict=True):
                    issue.start = sdt
                    issue.end = edt
                n_base = len(issues)
                st.session_state["fr_issues"] = all_for_split[:n_base]
                st.session_state["fr_extra_issue_rows"] = all_for_split[n_base:]
                st.rerun()

            nums = list({i.case_number for i in issues})
            resolved: dict[str, str] = {}
            for num in nums:
                cid = sf.find_case_id_by_number(num)
                if cid:
                    resolved[num] = cid

            extra_kw = st.text_input("Case 추가 검색 (번호/제목)", key="fr_case_kw")
            if st.button("검색 추가", key="fr_case_search") and extra_kw.strip():
                found = sf.search_cases(extra_kw.strip())
                extras = list(st.session_state.get("fr_extra_issue_rows") or [])
                for r in found:
                    extras.append(
                        FieldIssue(
                            case_number=r.case_number,
                            issue_line=f"□ (Case : {r.case_number})",
                            activity_line=format_activity_line(
                                report_day, fse_name, f"□ (Case : {r.case_number})"
                            ),
                            start=None,
                            end=None,
                            included=True,
                            case_id=r.case_id,
                        )
                    )
                st.session_state["fr_extra_issue_rows"] = extras
                st.rerun()

            extras = list(st.session_state.get("fr_extra_issue_rows") or [])
            all_issues = issues + extras
            if extras and any(i.start is None for i in all_issues):
                slots = split_workday_slots(work_start, work_end, len(all_issues))
                for issue, (sdt, edt) in zip(all_issues, slots, strict=True):
                    issue.start = sdt
                    issue.end = edt
                st.session_state["fr_issues"] = issues
                st.session_state["fr_extra_issue_rows"] = extras

            st.markdown("**이슈별 Work Order (Start/End)**")
            edited: list[FieldIssue] = []
            for idx, issue in enumerate(all_issues):
                cols = st.columns([0.7, 1.2, 3.2, 1.2, 1.2])
                with cols[0]:
                    included = st.checkbox(
                        "포함",
                        value=issue.included,
                        key=f"fr_iss_inc_{idx}",
                    )
                with cols[1]:
                    st.text(issue.case_number)
                with cols[2]:
                    line = st.text_input(
                        "이슈 줄",
                        value=issue.issue_line,
                        key=f"fr_iss_line_{idx}",
                        label_visibility="collapsed",
                    )
                with cols[3]:
                    s_t = st.time_input(
                        "Start",
                        value=(issue.start.time() if issue.start else start_t),
                        key=f"fr_iss_st_{idx}",
                        label_visibility="collapsed",
                    )
                with cols[4]:
                    e_t = st.time_input(
                        "End",
                        value=(issue.end.time() if issue.end else end_t),
                        key=f"fr_iss_et_{idx}",
                        label_visibility="collapsed",
                    )
                act = format_activity_line(report_day, fse_name, line)
                st.caption(f"Activity: `{act}`")
                cid = issue.case_id or resolved.get(issue.case_number)
                if not cid and included:
                    st.warning(f"Case {issue.case_number} 를 SF에서 찾지 못했습니다.")
                edited.append(
                    FieldIssue(
                        case_number=issue.case_number,
                        issue_line=line,
                        activity_line=act,
                        detail_text=issue.detail_text,
                        start=datetime.combine(start_d, s_t, tzinfo=tz),
                        end=datetime.combine(end_d, e_t, tzinfo=tz),
                        included=included,
                        case_id=cid,
                    )
                )

            for warn in find_time_overlaps(edited):
                st.error(warn)

            run_issues = edited
            case_ids = [i.case_id for i in edited if i.included and i.case_id]
            st.caption(
                "포함 체크된 이슈마다 "
                "Case Activities(요약 1줄) + Technical Service WO(Description=상세) 1개 "
                "+ 동일 crop 일자 시트 첨부가 생성됩니다. "
                "컷오프 이전 Case도 출장 보고에서는 기록합니다."
            )
            case_entries = [
                (i.case_id, i.case_number)
                for i in edited
                if i.included and i.case_id
            ]
        else:
            # 싱글 모드 (기존)
            st.dataframe(
                wo_fields.as_preview_rows(), hide_index=True, use_container_width=True
            )
            resolved = {}
            for num in plan.meta.case_numbers:
                cid = sf.find_case_id_by_number(num)
                if cid:
                    resolved[num] = cid
            extra_kw = st.text_input("Case 추가 검색 (번호/제목)", key="fr_case_kw")
            if st.button("검색 추가", key="fr_case_search") and extra_kw.strip():
                st.session_state["fr_extra_cases"] = sf.search_cases(extra_kw.strip())
            extras_c = st.session_state.get("fr_extra_cases") or []
            options: dict[str, str] = {}
            for num, cid in resolved.items():
                options[f"{num} (엑셀)"] = cid
            for r in extras_c:
                options[f"{r.case_number} / {r.subject[:40]}"] = r.case_id
            if not options:
                st.warning(
                    "엑셀 CRM Case ID가 비었거나 SF에서 못 찾았습니다. 검색으로 추가하세요."
                )
            picked = st.multiselect(
                "적용할 Case (복수 가능)",
                list(options.keys()),
                default=list(options.keys())[:1],
            )
            case_ids = [options[p] for p in picked]
            activity_line = format_activity_line(report_day, fse_name, summary)
            st.markdown(f"**Case Activity**: `{activity_line}`")
            st.caption(
                "위 한 줄이 Case Activities 맨 위(최신)에 추가되고, "
                "Case마다 Technical Service WO + 일자 시트 xlsx가 첨부됩니다."
            )
            # label → id; reverse for display numbers
            id_to_num = {cid: label.split()[0] for label, cid in options.items()}
            case_entries = [(cid, id_to_num.get(cid, cid)) for cid in case_ids]

        existing_wos = _lookup_existing_field_wos(
            sf, case_entries=case_entries, work_day=report_day
        )
        st.session_state["fr_existing_wos"] = existing_wos
        if existing_wos:
            st.warning(
                f"이미 등록된 Technical Service WO가 {len(existing_wos)}건 있습니다 "
                f"(작업일 {report_day:%Y-%m-%d}, StartDate 기준). "
                "「실제 등록」 시 해당 Case는 건너뛰고, 아래 메일 초안을 바로 쓸 수 있습니다."
            )
            st.dataframe(
                [
                    {
                        "Case": r["case_number"],
                        "Work Order": r["work_order_number"] or r["work_order_id"],
                    }
                    for r in existing_wos
                ],
                hide_index=True,
                use_container_width=True,
            )
            short = (summary or "").strip() or plan.sheet_name
            if multi_mode and run_issues:
                first = next(
                    (i for i in run_issues if i.included and i.case_id), None
                )
                if first:
                    short = (
                        re.sub(r"^\s*[□☐]\s*", "", first.issue_line).strip() or short
                    )
            _apply_existing_wo_mail_ctx(
                customer=customer,
                asset_name=asset_name,
                report_day=report_day,
                fse_name=fse_name,
                short_title=short,
                workbook=plan.workbook,
                sheet_name=plan.sheet_name,
                existing_rows=existing_wos,
                sf_instance_url=getattr(sf.client, "instance_url", "") or "",
            )
        elif "fr_mail_ctx" in st.session_state and not st.session_state.get(
            "fr_mail_draft"
        ):
            # 기존 WO가 없으면(시트 전환 등) 자동으로 연 메일 컨텍스트만 정리
            # 방금 등록 성공으로 세팅된 ctx는 등록 버튼 분기에서 다시 채움
            pass

        confirmed = st.checkbox(
            "내용을 확인했으며 Salesforce에 기록합니다", key="fr_confirm"
        )
        can_run = bool(case_ids) if not multi_mode else any(
            i.included and i.case_id for i in run_issues
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("미리보기 (dry-run)", key="fr_dry"):
                plan.activity_line = activity_line
                plan.wo_subject = f"[{customer} {asset_name}] {(summary or plan.sheet_name)[:80]}"
                result = run_field_report(
                    plan,
                    sf=sf,
                    opt_in=OptInStore(s.opt_in_path),
                    case_ids=case_ids,
                    dry_run=True,
                    cfg=s.field_report,
                    wo_fields=wo_fields,
                    issues=run_issues if multi_mode else None,
                )
                would = (result.details or {}).get("would") or {}
                st.markdown("**등록 예정 요약**")
                if would.get("mode") == "multi_issue":
                    st.dataframe(would.get("issues") or [], hide_index=True, use_container_width=True)
                else:
                    st.dataframe(
                        [
                            {"항목": "엑셀 파일", "값": Path(would.get("workbook", "")).name},
                            {"항목": "시트", "값": would.get("sheet", "")},
                            {"항목": "첨부", "값": would.get("attach", "")},
                            {"항목": "WO 제목", "값": would.get("wo_subject", "")},
                            {"항목": "Case Activity", "값": would.get("activity_line", "")},
                            {"항목": "Case 수", "값": str(len(would.get("case_ids") or []))},
                        ]
                        + wo_fields.as_preview_rows(),
                        hide_index=True,
                        use_container_width=True,
                    )
                _render_field_sheet_preview(
                    plan.workbook,
                    plan.sheet_name,
                    title="**엑셀 시트 (등록·첨부 대상, 하단 근무형태 제외)**",
                    key_prefix="fr_preview_dry",
                )
        with col_b:
            if st.button(
                "실제 등록",
                type="primary",
                disabled=not confirmed or not can_run,
                key="fr_real",
            ):
                plan.activity_line = activity_line
                plan.wo_subject = f"[{customer} {asset_name}] {(summary or plan.sheet_name)[:80]}"
                with st.spinner("Salesforce 기록 중..."):
                    result = run_field_report(
                        plan,
                        sf=sf,
                        opt_in=OptInStore(s.opt_in_path),
                        case_ids=case_ids,
                        dry_run=False,
                        cfg=s.field_report,
                        wo_fields=wo_fields,
                        issues=run_issues if multi_mode else None,
                    )
                details = result.details or {}
                if result.status in ("success", "partial"):
                    acted = details.get("acted") or []
                    for a in acted:
                        label = (
                            f"Case {a.get('case_number') or a['case_id']} → "
                            f"WO {a.get('work_order_number') or a['work_order_id']}"
                        )
                        if a.get("skipped"):
                            st.info(f"{label} — 이미 존재하여 건너뜀")
                        else:
                            st.success(
                                f"{label} (file {a.get('content_version_id')})"
                            )
                    for f in details.get("failed", []):
                        st.error(
                            f"Case {f.get('case_number') or f.get('case_id')}: {f.get('error')}"
                        )
                    if result.status == "partial":
                        st.warning("일부 Case만 등록되었습니다. 실패 건을 확인하세요.")
                    short = (summary or "").strip()
                    if multi_mode and run_issues:
                        first = next(
                            (i for i in run_issues if i.included and i.case_id),
                            None,
                        )
                        if first:
                            short = re.sub(
                                r"^\s*[□☐]\s*", "", first.issue_line
                            ).strip() or short
                    case_refs = []
                    seen_c: set[str] = set()
                    for a in acted:
                        num = a.get("case_number") or ""
                        if not num or num in seen_c:
                            continue
                        seen_c.add(num)
                        case_refs.append(
                            {"number": num, "id": a.get("case_id") or ""}
                        )
                    wo_refs = [
                        {
                            "number": a.get("work_order_number") or "",
                            "id": a.get("work_order_id") or "",
                        }
                        for a in acted
                        if a.get("work_order_id")
                    ]
                    st.session_state["fr_mail_ctx"] = {
                        "customer": customer,
                        "asset_folder": asset_name,
                        "work_day": report_day.isoformat(),
                        "fse_name": fse_name,
                        "case_numbers": [c["number"] for c in case_refs],
                        "wo_numbers": [
                            w["number"] for w in wo_refs if w["number"]
                        ],
                        "case_refs": case_refs,
                        "wo_refs": wo_refs,
                        "sf_instance_url": getattr(
                            sf.client, "instance_url", ""
                        )
                        or "",
                        "short_title": short or plan.sheet_name,
                        "workbook": str(plan.workbook),
                        "sheet_name": plan.sheet_name,
                    }
                    st.session_state.pop("fr_mail_draft", None)
                    st.session_state.pop("fr_mail_sent", None)
                else:
                    st.error(f"{result.status}: {result.reason or ''}")
                    for f in details.get("failed", []):
                        st.error(
                            f"Case {f.get('case_number') or f.get('case_id')}: {f.get('error')}"
                        )

        _render_field_mail_section()
    finally:
        sf_client.close()


def _render_settings_tab() -> None:
    from ai_work_automation.config_store import (
        apply_env_key_to_process,
        env_key_is_set,
        update_settings_yaml,
        upsert_env_key,
    )
    from ai_work_automation.sf.cli_status import (
        SfCliStatusError,
        get_sf_cli_status,
        list_sf_orgs,
        login_sf_org,
        logout_sf_org,
    )

    def _sf_widget_key(prefix: str, org_alias: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", org_alias)
        return f"{prefix}_{safe}"

    def _refresh_sf_session(current_alias: str) -> None:
        try:
            st.session_state["sf_org_rows"] = list_sf_orgs()
            st.session_state["sf_cli_action_error"] = None
        except SfCliStatusError as exc:
            st.session_state["sf_cli_action_error"] = str(exc)
        st.session_state["sf_cli_status"] = get_sf_cli_status(current_alias)

    env_path = Path(".env")
    s = _settings()

    st.subheader("시크릿")
    pms_set = env_key_is_set(env_path, "PMS_API_KEY")
    st.caption("PMS API Key: " + ("저장됨" if pms_set else "미설정"))
    new_key = st.text_input("PMS API Key", type="password", value="", key="settings_pms_key")
    if st.button("PMS 키 저장", key="settings_save_pms"):
        if not new_key.strip():
            st.error("키를 입력하세요.")
        else:
            try:
                upsert_env_key(env_path, "PMS_API_KEY", new_key.strip())
                apply_env_key_to_process("PMS_API_KEY", new_key.strip())
            except Exception:
                st.error("PMS API Key 저장에 실패했습니다.")
            else:
                st.success("PMS API Key를 .env에 저장했습니다.")
                st.rerun()

    st.subheader("일반")
    root_val = str(s.field_report_root) if s.field_report_root else ""
    field_root = st.text_input("field_report_root (DFS2 경로)", value=root_val)
    dry_run = st.toggle("dry_run", value=s.dry_run)
    org_alias = st.text_input("sf_org_alias", value=s.sf_org_alias)
    if field_root.strip():
        exists = Path(field_root.strip()).exists()
        st.caption("경로: " + ("존재함" if exists else "없음(동기화/경로 확인)"))
    if st.button("설정 저장", key="settings_save_yaml"):
        try:
            update_settings_yaml(
                SETTINGS_PATH,
                {
                    "field_report_root": field_root.strip() or None,
                    "dry_run": dry_run,
                    "sf_org_alias": org_alias.strip() or "parksystems",
                },
            )
        except Exception:
            st.error("설정 저장에 실패했습니다.")
        else:
            st.success("config/settings.yaml 저장됨. 다음 동작부터 반영됩니다.")
            st.rerun()

    st.subheader("Salesforce CLI")
    alias = org_alias.strip() or s.sf_org_alias
    if st.button("새로고침", key="settings_sf_refresh"):
        _refresh_sf_session(alias)

    action_error = st.session_state.get("sf_cli_action_error")
    if action_error:
        st.error(action_error)
        st.session_state["sf_cli_action_error"] = None

    status = st.session_state.get("sf_cli_status")
    if status is None:
        st.info("「새로고침」을 눌러 CLI 상태를 확인하세요.")
    elif status.ok and status.connected:
        st.success(f"Connected — {status.username or ''} ({status.alias})")
    elif status.ok:
        st.warning(status.message)
    else:
        st.error(status.message)

    if st.button("로그인", key="settings_sf_login"):
        try:
            with st.spinner("브라우저에서 Salesforce에 로그인하세요…"):
                login_sf_org(alias)
        except SfCliStatusError as exc:
            st.error(str(exc))
        else:
            _refresh_sf_session(alias)
            st.success("Salesforce에 로그인했습니다.")
            st.rerun()

    rows = st.session_state.get("sf_org_rows")
    if rows is None:
        st.caption("새로고침으로 목록을 불러오세요")
    elif not rows:
        st.info("로그인된 org 없음")
    else:
        for row in rows:
            c_alias, c_user, c_conn, c_use, c_out = st.columns([2.2, 3, 1.4, 1.6, 1.2])
            c_alias.write(row.alias)
            c_user.write(row.username or "")
            c_conn.write("Connected" if row.connected else "Disconnected")
            if c_use.button("이 계정 사용", key=_sf_widget_key("settings_sf_use", row.alias)):
                try:
                    update_settings_yaml(SETTINGS_PATH, {"sf_org_alias": row.alias})
                except Exception:
                    st.error("설정 저장에 실패했습니다.")
                else:
                    _refresh_sf_session(row.alias)
                    st.success(f"{row.alias} 계정을 사용합니다.")
                    st.rerun()
            if c_out.button("로그아웃", key=_sf_widget_key("settings_sf_logout", row.alias)):
                st.session_state["sf_logout_pending"] = row.alias
            if st.session_state.get("sf_logout_pending") == row.alias:
                st.warning("정말 로그아웃할까요?")
                c_ok, c_cancel = st.columns(2)
                if c_ok.button(
                    "확인",
                    key=_sf_widget_key("settings_sf_logout_ok", row.alias),
                ):
                    pending = st.session_state.pop("sf_logout_pending", None)
                    logout_error = None
                    if pending:
                        try:
                            logout_sf_org(pending)
                        except SfCliStatusError as exc:
                            logout_error = str(exc)
                    _refresh_sf_session(alias)
                    if logout_error:
                        st.session_state["sf_cli_action_error"] = logout_error
                    st.rerun()
                if c_cancel.button("취소", key="settings_sf_logout_cancel"):
                    st.session_state.pop("sf_logout_pending", None)
                    st.rerun()

    st.caption("토큰은 UI에 저장하지 않습니다. CLI 로그인을 사용합니다.")


s = _settings()

render_app_hero()

with st.sidebar:
    st.markdown("### 필터")
    st.caption("VOC→PMS 스캔 조건")
    department = st.text_input("Relevant Department", value="SW")
    asset_text = st.text_area(
        "장비명 포함 (한 줄에 하나, 비우면 전체)",
        value="\n".join(s.scan_filters.asset_contains),
        height=100,
    )
    asset_contains = [line.strip() for line in asset_text.splitlines() if line.strip()]
    sid_text = st.text_area(
        "SID 포함 (한 줄에 하나, 장비명과 OR 조건)",
        value="\n".join(s.scan_filters.sid_contains),
        height=68,
    )
    sid_contains = [line.strip() for line in sid_text.splitlines() if line.strip()]
    status_in = st.multiselect(
        "워크오더 상태 (비우면 전체)",
        options=sorted(set(STATUS_OPTIONS + s.scan_filters.status_in)),
        default=s.scan_filters.status_in,
    )
    owner_contains = st.text_input(
        "담당자 이름 포함 (AND 조건, 비우면 전체)",
        value=s.scan_filters.owner_contains,
    )
    st.caption(
        "조건 결합: (장비명 OR SID) AND 상태 AND 담당자. "
        "기본값은 config/settings.yaml 의 scan_filters 에서 관리"
    )
    st.divider()
    st.caption("환경")
    st.markdown(
        f"<span style='color:#6e6e73;font-size:0.9rem'>"
        f"컷오프 {s.automation_enabled_after:%Y-%m-%d %H:%M}<br/>"
        f"PMS {s.pms_project_id}<br/>"
        f"{'DFS2 연결됨' if s.field_report_root else 'DFS2 미설정'}"
        f"</span>",
        unsafe_allow_html=True,
    )

tab_scan, tab_search, tab_field, tab_status, tab_settings = st.tabs(
    ["VOC→PMS", "케이스 검색", "출장 보고", "이슈 상태", "설정"]
)

with tab_scan:
    if st.button("Salesforce 스캔", type="primary"):
        with st.spinner("Salesforce에서 워크오더 조회 중..."):
            sf_client, sf = _sf(s)
            try:
                st.session_state["scan_rows"] = scan_candidates(
                    sf,
                    OptInStore(s.opt_in_path),
                    department=department,
                    asset_contains=asset_contains,
                    sid_contains=sid_contains,
                    status_in=status_in,
                    owner_contains=owner_contains,
                )
            finally:
                sf_client.close()

    rows = st.session_state.get("scan_rows")
    if rows is not None:
        unlinked = [r for r in rows if not r.linked]
        st.caption(f"전체 {len(rows)}건 중 PMS 미연동 {len(unlinked)}건 (컷오프 이후 생성분)")

        st.dataframe(
            [
                {
                    "케이스": r.case_number,
                    "케이스 담당자": r.case_owner_name,
                    "워크오더": r.work_order_number,
                    "워크오더 담당자": r.owner_name,
                    "장비": r.asset_name,
                    "SID": r.asset_sid,
                    "상태": r.status,
                    "제목": r.title,
                    "생성일": r.created_date[:10],
                    "PMS": "연동됨" if r.linked else "미연동",
                }
                for r in rows
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("등록할 워크오더 선택 (다중 선택 가능)")
        options = {
            f"{r.case_number} / WO {r.work_order_number} / {r.title[:45]}": r
            for r in unlinked
        }
        if not options:
            st.info("미연동 후보가 없습니다.")
        else:
            picked_labels = st.multiselect("워크오더", list(options.keys()))
            issue_type_label = st.radio(
                "PMS 이슈 타입",
                ["자동 추정", "SR (문제/버그)", "ER (개선/추가 요청)"],
                horizontal=True,
                key="scan_type",
            )
            issue_type = {"SR (문제/버그)": "SR", "ER (개선/추가 요청)": "ER"}.get(issue_type_label)
            targets = [options[label] for label in picked_labels]
            if targets:
                _process_selection(s, targets, issue_type, key_prefix="scan")

with tab_search:
    with st.form("case_search_form"):
        keyword = st.text_input("케이스 번호 또는 제목 키워드", placeholder="예: 00173841 또는 Motor")
        submitted = st.form_submit_button("검색")
    if submitted and keyword.strip():
        with st.spinner("케이스 검색 중..."):
            sf_client, sf = _sf(s)
            try:
                st.session_state["search_results"] = sf.search_cases(keyword.strip())
            finally:
                sf_client.close()

    results = st.session_state.get("search_results")
    if results is not None:
        if not results:
            st.info("검색 결과가 없습니다.")
        else:
            st.dataframe(
                [
                    {
                        "케이스": r.case_number,
                        "제목": r.subject,
                        "생성일": r.created_date[:10],
                    }
                    for r in results
                ],
                use_container_width=True,
                hide_index=True,
            )
            case_options = {f"{r.case_number} / {r.subject[:50]}": r for r in results}
            picked_case = st.selectbox("처리할 케이스", list(case_options.keys()))
            target_case = case_options[picked_case]

            if st.button("워크오더 조회"):
                with st.spinner("워크오더 조회 중..."):
                    sf_client, sf = _sf(s)
                    try:
                        st.session_state["search_wos"] = (
                            target_case.case_id,
                            sf.get_work_orders_for_case(target_case.case_id),
                        )
                    finally:
                        sf_client.close()

            search_wos = st.session_state.get("search_wos")
            if search_wos and search_wos[0] == target_case.case_id:
                from ai_work_automation.pipeline import _issue_ids_in
                from ai_work_automation.services import ScanRow

                wo_rows = []
                for wo in search_wos[1]:
                    wo_rows.append(
                        ScanRow(
                            case_id=target_case.case_id,
                            case_number=target_case.case_number,
                            case_subject=target_case.subject,
                            work_order_id=wo.id,
                            work_order_number=wo.work_order_number,
                            title=wo.voc_title or wo.subject or target_case.subject,
                            created_date=wo.created_date.isoformat() if wo.created_date else "",
                            status="",
                            linked=bool(_issue_ids_in(wo.activities)),
                            selected=False,
                        )
                    )
                st.dataframe(
                    [
                        {
                            "워크오더": r.work_order_number,
                            "레코드타입": next(
                                (w.record_type for w in search_wos[1] if w.id == r.work_order_id), ""
                            ),
                            "부서": next(
                                (w.relevant_department for w in search_wos[1] if w.id == r.work_order_id), ""
                            ),
                            "제목": r.title,
                            "PMS": "연동됨" if r.linked else "미연동",
                        }
                        for r in wo_rows
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
                sel_options = {
                    f"WO {r.work_order_number} / {r.title[:45]}": r
                    for r in wo_rows
                    if not r.linked
                }
                if sel_options:
                    picked_wos = st.multiselect("등록할 워크오더", list(sel_options.keys()))
                    issue_type_label2 = st.radio(
                        "PMS 이슈 타입",
                        ["자동 추정", "SR (문제/버그)", "ER (개선/추가 요청)"],
                        horizontal=True,
                        key="search_type",
                    )
                    issue_type2 = {"SR (문제/버그)": "SR", "ER (개선/추가 요청)": "ER"}.get(issue_type_label2)
                    targets2 = [sel_options[label] for label in picked_wos]
                    if targets2:
                        _process_selection(s, targets2, issue_type2, key_prefix="search")
                else:
                    st.info("이 케이스의 모든 워크오더가 이미 PMS에 연동돼 있습니다.")

with tab_field:
    _render_field_report_tab(s)

with tab_status:
    if st.button("상태 새로고침"):
        with st.spinner("PMS 이슈 상태 조회 중..."):
            sf_client, sf = _sf(s)
            pms_http, pms = _pms(s)
            try:
                st.session_state["status_rows"] = status_overview(
                    sf, pms, OptInStore(s.opt_in_path)
                )
            finally:
                sf_client.close()
                pms_http.close()

    status_rows = st.session_state.get("status_rows")
    if status_rows is not None:
        if not status_rows:
            st.info("옵트인된 케이스에 연결된 PMS 이슈가 없습니다.")
        else:
            st.dataframe(
                [
                    {
                        "워크오더": r.work_order_number,
                        "PMS 이슈": r.issue_url,
                        "상태": r.issue_status,
                        "제목": r.issue_subject,
                        "최종 수정": r.issue_updated_on[:10],
                    }
                    for r in status_rows
                ],
                use_container_width=True,
                hide_index=True,
                column_config={"PMS 이슈": st.column_config.LinkColumn()},
            )

with tab_settings:
    _render_settings_tab()
