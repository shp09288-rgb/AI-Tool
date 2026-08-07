# 출장 보고(Excel→SF) + PMS 통합 UI 설계

**날짜:** 2026-08-07  
**상태:** 구현 진행  
**전제:** DFS2 로컬 동기화, Azure Graph 없음, SF는 기존 CLI 토큰

## 목표

하나의 Streamlit Tool에서:

1. **VOC → PMS** 일괄 등록 (기존)
2. **출장 보고:** 로컬 Field Service / Installation 엑셀 일자 시트 → Case Activity → Technical Service WO + 일자 시트 파일 첨부

## UI 통합

| 탭 | 역할 |
|----|------|
| VOC→PMS 등록 | 기존 후보 스캔·일괄 등록 |
| 케이스 검색 | 기존 |
| 출장 보고 | 신규: 설비·리포트·일자 시트·Case·요약·승인 |
| PMS 이슈 상태 | 기존 |

사이드바: 공통 컷오프/PMS 정보 + 출장용 `field_report_root` 표시.

## 출장 보고 플로우

**원칙:** 일자 시트 생성·작성은 사람이 Excel에서 한다. Tool은 **작성된 시트를 불러와** SF만 자동화한다.

```text
(사람) Excel에서 일자 시트 작성·저장 · OneDrive 동기화
  → Tool: 설비 폴더·리포트 종류 선택
  → 기존 일자 시트 목록에서 선택 → 「시트 불러오기」
  → CRM Case ID·출장자·Start/End·본문 요약 읽기
  → Case 복수 선택 · WO 필드 확인(Status 기본 Completed 등)
  → Human Gate
  → Case.Activities__c 이어쓰기
  → Technical Service WO 생성 + 해당 일자 시트 xlsx 첨부
```

v1 WO 정책: **선택한 Case마다** Technical Service WO 1개 + 동일 일자 시트 파일 첨부.

## 설정

```yaml
field_report_root: "C:\\Users\\shp09\\OneDrive - Park Systems\\DFS2 - General\\DFS2"
field_report:
  case_activities_field: Activities__c
  technical_service_record_type_id: "0120o000001lQJ5AAM"
  fsr_case_id_cell: T9
  fsr_fse_name_cell: V5
  fsr_report_date_cell: V4
```

## 안전

옵트인(실행 시 Case select), 컷오프(Case CreatedDate), Human Gate, Activity 이어쓰기만, dry-run 미리보기.
