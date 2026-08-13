# Tool-first VOC 작성 — 설계 스펙

**날짜:** 2026-08-13  
**상태:** 설계 승인됨 (대화 합의)  
**대상:** Streamlit 로컬 앱 — 신규 「VOC 작성」 흐름  
**관련:** 기존 VOC→PMS 파이프라인, `draft_template.build_pms_comment`, Human Gate, SF CLI 인증

## 1. 목표

Salesforce에서 Case/WO를 먼저 만든 뒤 Tool에서 다시 찾아 등록하는 왕복을 줄인다.  
**Tool에서 작성·승인하면** SF Case/WO 생성(또는 기존 Case에 WO 추가)과 PMS 이슈/댓글까지 이어서 처리한다.

성공 기준:

1. **신규 Case** 모드에서 장비·제목·본문(이미지 포함) 작성 → 승인 → SF Case + VOC WO + PMS 이슈(+ Activities 링크) 완료  
2. **기존 Case** 모드에서 Case 선택 → VOC WO 추가 → 기존 PMS 연동 있으면 **댓글**, 없으면 **이슈 생성** (현행 Tool과 동일 규칙)  
3. 본문 편집기는 PMS용 HTML로 붙여넣기·크롭·첨부 등 자율성이 큼  
4. 기존 VOC→PMS 스캔 탭·출장보고는 회귀 없음

## 2. 비목표 (1차)

- Salesforce LWC/퀵액션에서 PMS 등록 버튼
- SF Case/WO **인라인** 이미지 본문 (SF 한계) — 필요 시 ContentDocument 첨부만
- SF용 / PMS용 **이중 본문 편집기** (본문은 PMS 중심, 옵션 A)
- 전 부서·전 라우트 확대 (1차는 현행 SW→PMS와 동일 전제)
- 완전 무인 자동 게시 (승인/Human Gate 유지)

## 3. 접근 (확정)

**Streamlit 「VOC 작성」탭(또는 동등 진입점)** + 기존 PMS 커넥터·초안/댓글 빌더·SF HTTP 어댑터 확장.

인증은 기존과 같이 SF CLI(`sf_org_alias`) + `.env` PMS 키.

## 4. 본문 정책 (옵션 A)

| 대상 | 내용 |
|------|------|
| **편집기** | 자율 HTML — 붙여넣기, 이미지 삽입/크롭, 첨부. **PMS 이슈 설명 또는 댓글**에 사용 |
| **SF Case/WO** | 제목·짧은 요약·Relevant Department·Asset/SID 등 구조화 필드. 이미지는 가능하면 **파일 첨부**로 업로드 |
| **동일 규칙** | Case(또는 기존 VOC)에 PMS URL이 이미 있으면 **신규 이슈 금지 → 기존 이슈 댓글** |

## 5. 사용 흐름

### 5.1 신규 Case

1. 「VOC 작성」→ 모드 **신규 Case**  
2. 고객/장비/SID·제목(예: 정전기 센서 불량)·부서(SW)·본문 편집  
3. 미리보기: SF에 쓰일 요약 + PMS HTML  
4. 승인 → Case 생성 → VOC WO 생성(Asset/SID 매핑) → PMS 이슈 생성 → WO Activities에 `PMS – {url}`  
5. 결과 링크: Case / WO / PMS

### 5.2 기존 Case에 VOC 추가

1. 모드 **기존 Case** → Case 번호 검색/선택  
2. Case에서 Asset/SID 등 프리필 (가능하면)  
3. 본문 편집 (추가 설명·이미지)  
4. 승인 → 해당 Case에 VOC WO 생성 →  
   - 이미 PMS 연동됨 → **댓글** (`build_pms_comment` 계열)  
   - 미연동 → **이슈 생성**  
5. WO Activities 갱신(링크 또는 댓글 메모 정책은 현행 파이프라인에 맞춤)

## 6. UI 구성 (1차)

| 영역 | 역할 |
|------|------|
| 모드 토글 | 신규 Case / 기존 Case |
| Case 선택 | 기존 모드: 검색(번호) + 선택 결과 |
| 메타 필드 | 제목, 부서, 장비/SID (기존 Case면 읽기·수정 가능 범위는 구현 시 확정) |
| 리치 편집기 | 기존 Streamlit Quill 등 확장 — 이미지 붙여넣기·크롭·첨부 |
| 미리보기 / 승인 | dry_run 시 생성 생략·페이로드만 표시 가능 |
| 결과 | 링크·오류 메시지 |

기존 「VOC→PMS」스캔 탭은 유지 (후처리·일괄용).

## 7. 구성 요소

| 구성 | 역할 |
|------|------|
| UI (`webui`) | VOC 작성 탭, 편집기, 미리보기, 승인 |
| SF 어댑터 확장 | Case create, WO create(기존 CaseId), ContentDocument 링크(선택) |
| PMS | 기존 `create issue` / `add_comment` |
| 초안 | 기존 draft_template + comment 빌더 재사용·확장 |
| 연동 판별 | Activities 등에서 기존 PMS URL/이슈 ID 파싱 (현행 `_issue_ids_in` 등과 동일 계열) |

### 7.1 오류·안전

- 컷오프·dry_run·Human Gate 정신 유지 (쓰기 전 승인)  
- SF/PMS 일부 성공·일부 실패 시: 어디까지 됐는지 링크/ID를 보여 주고, 재시도 가이드  
- 시크릿·토큰 UI 저장 금지 (기존 정책)

## 8. 테스트

- 단위: 연동 있음→comment / 없음→create 분기; 초안 HTML  
- 수동: 신규 1건(이미지 포함), 기존 Case+댓글 1건, dry_run 1건  
- 회귀: 스캔 탭 미연동 등록

## 9. 구현 순서 (참고)

1. SF Case/WO 생성 API 래퍼 + 테스트  
2. VOC 작성 UI(모드·메타·편집기·미리보기)  
3. 승인 오케스트레이션 (신규 / 기존+comment|create)  
4. 첨부·크롭 UX 다듬기  
5. 문서·가이드 한 절

## 10. 열린 구현 디테일 (스펙에서 방향만 고정)

- 메타 필드 중 Case vs WO에 무엇이 필수인지는 SF 실필드에 맞춰 구현 시 확정  
- 이미지 크롭 라이브러리/위젯은 구현 계획에서 선정 (1차 범위에 포함)  
- 「기존 Case」검색은 CaseNumber 우선; 전문 검색은 후순위
