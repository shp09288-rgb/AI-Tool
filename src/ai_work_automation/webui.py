"""로컬 웹 UI (Streamlit).

실행: streamlit run src/ai_work_automation/webui.py
CLI와 같은 파이프라인/서비스 코드를 재사용한다.
"""

from pathlib import Path

import httpx
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from ai_work_automation.connectors.pms import PmsConnector
from ai_work_automation.idempotency import JsonIdempotencyStore
from ai_work_automation.job_log import JobLogStore
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.pipeline import run_case_automation
from ai_work_automation.router import load_routes
from ai_work_automation.services import scan_candidates, status_overview
from ai_work_automation.settings import load_settings

load_dotenv()

SETTINGS_PATH = Path("config/settings.yaml")

st.set_page_config(page_title="AI 업무 자동화", page_icon="🔧", layout="wide")


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


def _run_pipeline(s, case_id: str, *, dry_run: bool, issue_type: str | None):
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
        )
    finally:
        sf_client.close()
        pms_http.close()


s = _settings()

st.title("AI 업무 자동화 — PMS 연동")
with st.sidebar:
    st.markdown(f"**컷오프**: {s.automation_enabled_after:%Y-%m-%d %H:%M}")
    st.markdown(f"**PMS 프로젝트**: {s.pms_project_id} (XEA Request)")
    st.markdown(f"**설정 dry_run**: `{s.dry_run}`")
    st.caption("설정 변경은 config/settings.yaml 에서")

tab_scan, tab_status = st.tabs(["후보 스캔·등록", "PMS 이슈 상태"])

with tab_scan:
    col_btn, col_dept = st.columns([1, 3])
    with col_btn:
        do_scan = st.button("Salesforce 스캔", type="primary", use_container_width=True)
    with col_dept:
        department = st.text_input("Relevant Department", value="SW", label_visibility="collapsed")

    if do_scan:
        with st.spinner("Salesforce에서 워크오더 조회 중..."):
            sf_client, sf = _sf(s)
            try:
                st.session_state["scan_rows"] = scan_candidates(
                    sf, OptInStore(s.opt_in_path), department=department
                )
            finally:
                sf_client.close()

    rows = st.session_state.get("scan_rows")
    if rows is not None:
        unlinked = [r for r in rows if not r.linked]
        st.caption(f"전체 {len(rows)}건 중 PMS 미연동 {len(unlinked)}건 (컷오프 이후 생성분)")

        table = [
            {
                "케이스": r.case_number,
                "워크오더": r.work_order_number,
                "제목": r.title,
                "생성일": r.created_date[:10],
                "PMS": "연동됨" if r.linked else "미연동",
                "선택됨": r.selected,
            }
            for r in rows
        ]
        st.dataframe(table, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("케이스 처리")
        options = {
            f"{r.case_number} / WO {r.work_order_number} / {r.title[:40]}": r
            for r in unlinked
        }
        if not options:
            st.info("미연동 후보가 없습니다.")
        else:
            picked = st.selectbox("처리할 워크오더 선택", list(options.keys()))
            target = options[picked]
            issue_type_label = st.radio(
                "PMS 이슈 타입",
                ["자동 추정", "SR (문제/버그)", "ER (개선/추가 요청)"],
                horizontal=True,
            )
            issue_type = {"SR (문제/버그)": "SR", "ER (개선/추가 요청)": "ER"}.get(issue_type_label)

            if st.button("미리보기 (dry-run)"):
                OptInStore(s.opt_in_path).select(target.case_id)
                with st.spinner("초안 생성 중..."):
                    result = _run_pipeline(s, target.case_id, dry_run=True, issue_type=issue_type)
                st.session_state["preview"] = (target.case_id, result)

            preview = st.session_state.get("preview")
            if preview and preview[0] == target.case_id:
                _, result = preview
                would = (result.details or {}).get("would_post", [])
                if not would:
                    st.warning("등록할 항목이 없습니다 (이미 연동됐거나 컷오프/라우팅 제외).")
                for item in would:
                    action = "기존 이슈에 댓글" if item["action"] == "comment" else "신규 이슈 생성"
                    st.markdown(f"**동작**: {action}"
                                + (f" (#{item['issue_id']})" if item.get("issue_id") else "")
                                + (f" / 타입: {item.get('issue_type')}" if item.get("issue_type") else ""))
                    st.markdown(f"**제목**: {item['title']}")
                    if item.get("custom_fields"):
                        st.markdown("**커스텀 필드**: " + ", ".join(
                            f"{f['id']}={f['value']}" for f in item["custom_fields"]
                        ))
                    st.markdown("**본문 미리보기**:")
                    components.html(
                        f'<div style="border:1px solid #ddd;border-radius:6px;'
                        f'padding:12px;font-family:sans-serif">{item["body"]}</div>',
                        height=300,
                        scrolling=True,
                    )

                st.divider()
                confirmed = st.checkbox("위 내용을 확인했으며 실제 등록에 동의합니다")
                if st.button("실제 등록", type="primary", disabled=not confirmed):
                    with st.spinner("PMS 등록 및 Salesforce 기록 중..."):
                        real = _run_pipeline(s, target.case_id, dry_run=False, issue_type=issue_type)
                    if real.status == "success":
                        for acted in (real.details or {}).get("acted", []):
                            st.success(f"완료: {acted['url']} ({acted['action']})")
                        st.session_state.pop("preview", None)
                        st.session_state.pop("scan_rows", None)
                    else:
                        st.error(f"결과: {real.status} / {real.reason or ''}")
                        st.json(real.model_dump())

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
