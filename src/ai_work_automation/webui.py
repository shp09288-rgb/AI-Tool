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
                  only_wo_ids: set[str] | None = None):
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
        )
    finally:
        sf_client.close()
        pms_http.close()


def _render_would_post(items: list[dict]) -> None:
    for item in items:
        action = "기존 이슈에 댓글" if item["action"] == "comment" else "신규 이슈 생성"
        st.markdown(
            f"**동작**: {action}"
            + (f" (#{item['issue_id']})" if item.get("issue_id") else "")
            + (f" / 타입: {item.get('issue_type')}" if item.get("issue_type") else "")
        )
        st.markdown(f"**제목**: {item['title']}")
        if item.get("custom_fields"):
            st.markdown(
                "**커스텀 필드**: "
                + ", ".join(f"{f['id']}={f['value']}" for f in item["custom_fields"])
            )
        st.markdown("**본문 미리보기**:")
        components.html(
            f'<div style="border:1px solid #ddd;border-radius:6px;'
            f'padding:12px;font-family:sans-serif">{item["body"]}</div>',
            height=280,
            scrolling=True,
        )
        st.divider()


def _process_selection(s, targets: list, issue_type: str | None, key_prefix: str) -> None:
    """선택된 워크오더들(케이스별 그룹)을 미리보기 -> 승인 -> 등록하는 공용 위젯."""
    if st.button("미리보기 (dry-run)", key=f"{key_prefix}_preview"):
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
            _render_would_post(would)

    if total_items == 0:
        return

    confirmed = st.checkbox(
        f"위 {total_items}건을 확인했으며 실제 등록에 동의합니다", key=f"{key_prefix}_confirm"
    )
    if st.button("실제 등록", type="primary", disabled=not confirmed, key=f"{key_prefix}_real"):
        with st.spinner("PMS 등록 및 Salesforce 기록 중..."):
            for case_id, wo_ids, _r in previews:
                real = _run_pipeline(
                    s, case_id, dry_run=False, issue_type=issue_type, only_wo_ids=wo_ids
                )
                if real.status == "success":
                    for acted in (real.details or {}).get("acted", []):
                        st.success(f"완료: {acted['url']} ({acted['action']})")
                else:
                    st.error(f"케이스 {case_id}: {real.status} / {real.reason or ''}")
        st.session_state.pop(f"{key_prefix}_previews", None)
        st.session_state.pop("scan_rows", None)


s = _settings()

st.title("AI 업무 자동화 — PMS 연동")

with st.sidebar:
    st.subheader("스캔 필터")
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
    st.markdown(f"**컷오프**: {s.automation_enabled_after:%Y-%m-%d %H:%M}")
    st.markdown(f"**PMS 프로젝트**: {s.pms_project_id} (XEA Request)")
    st.markdown(f"**설정 dry_run**: `{s.dry_run}`")

tab_scan, tab_search, tab_status = st.tabs(["후보 스캔·등록", "케이스 검색", "PMS 이슈 상태"])

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
                    "워크오더": r.work_order_number,
                    "장비": r.asset_name,
                    "SID": r.asset_sid,
                    "상태": r.status,
                    "담당자": r.owner_name,
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
