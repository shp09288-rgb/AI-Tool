# 출장 보고 + PMS 통합 UI 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Streamlit 한 앱에 PMS 등록과 출장 보고(Excel→Case Activity→WO 첨부)를 탭으로 통합.

**Architecture:** `field_report` 패키지(엑셀·파이프라인) + SF 어댑터 확장(Case Activity, WO create, ContentVersion) + `webui.py` 탭 추가.

**Tech Stack:** Python 3.11, openpyxl, httpx, Streamlit, pytest

## File map

| File | Responsibility |
|------|----------------|
| `src/ai_work_automation/field_report/excel_ops.py` | 리포트 탐색, 일자 시트 생성, 메타 읽기, 단일 시트 export |
| `src/ai_work_automation/field_report/pipeline.py` | dry-run/real 오케스트레이션 |
| `src/ai_work_automation/sf/client.py` | `post_sobject`, `create_content_version` |
| `src/ai_work_automation/sf/adapter.py` | Case activity append, WO create, attach file |
| `src/ai_work_automation/settings.py` | `field_report_*` 설정 |
| `src/ai_work_automation/webui.py` | 통합 탭 UI |
| `tests/test_field_report_excel.py` | 엑셀 단위 테스트 |
| `tests/test_field_report_sf.py` | SF 어댑터 mock 테스트 |

### Task 1: Settings + excel_ops + tests

- [ ] `FieldReportConfig` 추가, example/settings 경로 반영
- [ ] excel_ops: find report, ensure day sheet, read meta, export sheet
- [ ] pytest green

### Task 2: SF client/adapter

- [ ] post_sobject, content version upload
- [ ] append_case_activities, create_technical_service_wo, attach_file
- [ ] pytest green

### Task 3: pipeline + webui tab

- [ ] field_report.pipeline
- [ ] webui 4번째 탭 + 제목/사이드바 통합
- [ ] 수동 스모크: 로컬 DFS2 경로·dry-run
