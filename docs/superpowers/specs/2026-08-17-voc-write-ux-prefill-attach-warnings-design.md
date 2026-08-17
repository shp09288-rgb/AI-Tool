# VOC 작성 UX — SID/장비 프리필 + SF 첨부 경고

**날짜:** 2026-08-17  
**상태:** 설계 승인됨 (스펙 리뷰 완료; 구현 계획 있음)  
**대상:** Streamlit 「VOC 작성」탭 + `tool_first_voc` 오케스트레이터  
**관련:** `docs/superpowers/specs/2026-08-13-tool-first-voc-design.md`, AssetId Case→WO 복사(`595c374`)

## 1. 목표

기존 Case에 VOC를 붙일 때 **장비/SID 빈칸**과 **SF 첨부 실패를 모름** 때문에 SF를 다시 열어보는 왕복을 줄인다.

성공 기준:

1. Case 조회 후, Case 또는 형제 Work Order에 있는 `AssetId` / `Asset_SID__c`가 **비어 있는 입력란에만** 프리필된다.
2. 파일 첨부가 SF에서 실패해도 Case/WO/PMS 흐름은 성공으로 끝나고, UI에 **경고 목록**이 보인다.
3. 사용자가 이미 입력한 Asset/SID 값은 덮어쓰지 않는다.
4. 기존 AssetId 자동 복사·PMS 이슈/댓글 규칙은 회귀 없음.

## 2. 비목표 (이번 범위 밖)

- Quill 붙여넣기 이미지를 크롭·SF 첨부 파이프라인에 포함 (차기 C)
- 크롭 UI를 슬라이더 → 드래그 영역 선택으로 교체 (차기 D)
- Case 객체에 `Asset_SID__c` 스키마를 상시 모델링해 저장
- 첨부 실패 시 전체 트랜잭션 롤백/실패 처리
- 스캔 탭 케이스 묶기·필터 프리셋

## 3. 접근 (확정)

| 항목 | 방식 |
|------|------|
| **A. 프리필** | Case 조회 시 형제 WO에서 Asset/SID 힌트 수집 → UI 빈 칸만 채움 + 오케스트레이터에서 WO create 시 SID 방어 복사 |
| **B. 첨부 경고** | 첨부는 계속 best-effort. 실패·미지원을 `warnings`로 수집해 결과 UI에 표시. `ok`는 본 흐름 성공 시 True 유지 |

## 4. A — SID/장비 프리필

### 4.1 힌트 소스·우선순위

조회된 Case와 그 Case의 WorkOrder 목록에서 후보를 모은다.

| 필드 | 우선순위 |
|------|----------|
| `AssetId` | ① Case.AssetId → ② 형제 WO의 AssetId (값이 있는 것 중 최신 CreatedDate 우선, 동률이면 조회 순서) |
| `Asset_SID__c` | ① 형제 WO의 Asset_SID__c (동일 최신 우선). Case에는 SID 필드가 없으므로 Case만으로는 불가 |

UI 프리필과 오케스트레이터 방어 복사는 **같은 우선순위**를 쓴다.

### 4.2 UI (기존 Case 조회)

1. 「조회」성공 후 WorkOrder 힌트를 조회한다.
2. `voc_write_asset` / `voc_write_sid` 세션 값이 **비어 있을 때만** 힌트로 채운다.
3. caption에 Asset·SID를 표시할 때, 프리필된 세션 값을 반영한다.
4. 사용자가 칸을 지우고 다시 조회하면 다시 채울 수 있다(빈 칸 = 프리필 허용).

### 4.3 오케스트레이터

이미 `AssetId`는 payload 우선 → Case.AssetId 폴백이 있다. 이번에:

- **단일 규칙:** create(및 dry_run 해석) 직전에 Case + 형제 WO로 힌트를 다시 계산한다. UI 프리필만 믿지 않는다(테스트·비UI 경로 방어).
- 최종 필드: `payload` 값이 있으면 그대로; 없으면 힌트(`AssetId` / `Asset_SID__c`)로 채운다.

구현 시 순수 함수로 분리:  
`resolve_asset_hints(case, work_orders) -> {asset_id, asset_sid}`  

형제 WO의 AssetId/SID는 **힌트 전용 경량 SOQL**(또는 조회 헬퍼)로 가져온다. 전역 `WorkOrderRecord` 스키마 확장은 필수가 아니다(필요하면 선택).

## 5. B — SF 첨부 경고

### 5.1 동작

`_best_effort_attach`는 예외를 삼키되, 삼킨 내용을 문자열로 남긴다.

경고를 만드는 경우(예시):

- `create_content_version_from_bytes` 미존재 → 첨부 스킵 경고 1건
- 개별 파일·대상(Case/WO) 업로드 예외 → `SF 첨부 실패: {filename} → {Case|WO} — {짧은 사유}`

첨부가 없으면 경고 없음.

### 5.2 결과 모델

`ToolFirstVocResult`에 `warnings: list[str] = []` 추가.

- 본 흐름(Case/WO/PMS, Activities 정책)이 성공하면 `ok=True` 유지
- Activities 부분 실패 메시지와 별개로, `warnings`에 첨부 이슈를 담는다

### 5.3 UI

`_render_voc_result`에서 `result.warnings`가 있으면 `st.warning`으로 각 항목(또는 합친 목록) 표시.

## 6. 구성 요소

| 구성 | 변경 |
|------|------|
| `sf` 어댑터 또는 힌트 헬퍼 | Case WO에서 AssetId / Asset_SID__c 조회 가능 |
| `tool_first_voc` | hints 해석, SID 폴백, attach → warnings |
| `webui` VOC 작성 | 조회 시 프리필; 결과 warnings 표시 |
| 테스트 | 힌트 우선순위, 빈 칸만 채움, 첨부 실패 시 warnings·ok |

## 7. 완료 조건 (검증)

1. Case.AssetId만 있고 SID는 형제 WO에만 있는 fixture → 조회/실행 시 SID가 WO create 필드에 들어감
2. payload에 SID를 넣으면 형제 WO SID보다 payload 우선
3. attach mock이 예외를 던지면 result.warnings 비지 않음, ok는 True(본 흐름 성공 시)
4. `tests/test_tool_first_voc.py` 기존 케이스 + 신규 통과

## 8. 열린 결정 (확정)

- 첨부 실패로 **전체를 실패 처리하지 않음** (경고만)
- Quill/드래그 크롭은 이번 스펙 밖
