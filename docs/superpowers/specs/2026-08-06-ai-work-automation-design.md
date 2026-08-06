# AI 업무 자동화 Tool — 설계 스펙

**날짜:** 2026-08-06  
**상태:** 사용자 검토용 초안  
**접근 방식:** C — 하이브리드 (설정 기반 라우팅 + AI 초안 + 사람 승인)

## 1. 목표

Salesforce를 허브로 두고, Case / Work Order 내용을 용도에 맞게 외부 도구에 게시하거나 메일 초안을 만든 뒤, 결과(링크·등록번호)를 Work Order Activities에 다시 적는다. 손으로 반복하던 CRM 연계 업무를 대체하되, **기존 접수분에는 쓰지 않고**, **사용자가 선택한 Case만** 자동화한다.

## 2. 이번 스펙 범위 (포함)

- Salesforce Case → Work Order 흐름을 기준으로 한 연동 설계
- 플러그인형 커넥터: PMS, Workful(PowerApps), Teams, Outlook, 릴리즈 노트
- 설정 기반 라우팅 + AI 본문/메일 초안 + 게시·발송 전 사람 승인(Human Gate)
- 옵트인(선택) UI/플래그, 배포 컷오프(기존 레코드 불변)
- 도구별 API·연동 검토 문서 (`docs/integrations/`)

## 3. 범위 밖

- 배포 이전 Case/WO 일괄 이전·일괄 수정
- Outlook 자동 발송(기본은 초안만)
- 릴리즈 노트 앱 소스 대규모 개편(필요 시 후속)
- IT 권한 발급·Connected App 생성 자체(전제 조건으로만 기록)

## 4. 아키텍처

```text
사용자가 Case 선택 (옵트인)
        │
        ▼
컷오프 검사 (배포 이후 생성분만) ──실패──► 건너뜀 (쓰기 없음)
        │
        ▼
SF 어댑터가 Case + 관련 Work Order 읽기
        │
        ▼
라우터 (YAML/JSON: Record Type + Relevant Department + 업무 종류)
        │
        ├─ Draft AI (제목/본문/메일 초안, 애매할 때만 분류 제안)
        ├─ Human Gate (미리보기 / 수정 / 승인)  [기본 ON]
        └─ 커넥터들 → { ref, url }
                │
                ▼
        회수(Writeback) → Work Order Activities
        (선택한 레코드에만, 기존 텍스트에 이어 붙이기)
```

### 원칙

- Salesforce가 단일 진실 공급원이다. 외부 게시는 파생이고, 결과는 WO Activities로 돌아온다.
- 라우팅은 설정으로 바꿔, PPT(구 지침)와 현재 실무가 달라도 된다.
- 새 시스템은 공통 인터페이스를 구현한 커넥터만 추가하면 된다.
- 기본 안전장치: 과거 레코드 쓰기 금지, 메일 자동 발송 금지, 게시 전 사람 승인.

## 5. 구성 요소

| 단위 | 역할 | 의존 |
|------|------|------|
| Case 선택기 | 자동화에 넣을 Case를 사용자가 고름 | 로컬 저장 및/또는 SF 플래그 |
| 컷오프 가드 | `automation_enabled_after` 이전 Case/WO 차단 | 설정 시각 |
| SF 어댑터 | Case/WO 읽기, Activities 이어쓰기, 과거 일괄 수정 금지 | Salesforce REST + OAuth |
| 라우터 | 신호 → 커넥터 목록 매핑 | 라우팅 설정 |
| Draft AI | 본문 초안, 선택적 분류 보조 | LLM + Case/WO 필드 |
| Human Gate | 외부 부작용 전 미리보기·승인 | UI 또는 Teams 카드 |
| 커넥터 | `create` / `draft` → `{ ref, url }` | 도구별 API |
| Writeback | 외부 ref를 Activities에 이어 붙임 | SF 어댑터 |
| 작업 로그 | Case별 실행 상태, skip 사유, 재시도 | 로컬 DB/파일 |

### 커넥터 인터페이스 (개념)

```text
입력:  { case, workOrder, draftContent, options }
출력:  { ok, ref, url, raw? } | { ok: false, error, retryable }
```

## 6. 주요 워크플로

### 6.1 VOC → 외부 게시 (예: SW → PMS)

1. 사용자가 VOC Work Order가 있는(또는 만들) Case를 옵트인 선택한다.
2. 가드: Case는 컷오프 이후여야 한다.
3. 라우터가 Record Type `VOC` + Relevant Department(예: `SW`) → `pms`.
4. AI가 제목/설명 초안 (SF와 동일 제목 규칙).
5. Human Gate 승인 → PMS 이슈 생성 → URL 반환.
6. WO Activities에 `PMS – {url}` 이어 붙임.

### 6.2 Technical Support → Outlook

1. 출장/현장 대응 Case → Work Order Record Type `Technical Support`.
2. 해당 Case를 사용자가 옵트인.
3. 라우터 → `outlook`.
4. AI가 수신자·제목·본문 초안 (Case + WO 기준).
5. Outlook **초안(Draft)** 생성 (WO 요약 첨부 및/또는 SF 레코드 링크).
6. 사용자가 Outlook에서 확인 후 직접 발송.
7. (선택) Activities에 초안/발송 시각 또는 Message-ID 기록.

### 6.3 릴리즈 노트 (보조 루프)

- VOC 라우팅이 아니라, 개선 SW 버전 **메일**이 주 트리거.
- 변경점 요약 → 릴리즈 노트 앱 업데이트 초안.
- 앱 API 확인 전까지 우선순위는 낮게 둔다.

## 7. 라우팅 매트릭스 (초안 — 설정으로 변경)

| 대략적인 신호 | 대상 | 산출물 | Activities 회수 |
|----------------|------|--------|----------------|
| VOC + Dept SW (버그/기능/문의) | PMS | Issue | `PMS – URL` |
| SRD / Work Pool 성격 | Workful (Dataverse) | 등록 | `Work Pool – 등록번호` |
| MC / OBQ·QI | Teams | 메시지 또는 리스트 항목 | `OBQ/QI – 공유 링크` |
| Issue & VOC 추적 | Teams (+ Sheet/SharePoint) | 행/메시지 | 접수번호 등 |
| Technical Support (출장대응; SF API Record Type 이름 확인 필요) | Outlook | 메일 **초안** + WO 첨부/링크 | Message-ID(선택) |
| SW 버전 안내 메일 | 릴리즈 노트 | 업데이트 카드/항목 | (RN URL, SF 연동은 후속) |
| HW / Manual / Sales / TS / QI … | 설정 TBD | — | 매핑 확정 전 AI 제안만 |

참고: `reference/2025-08-27 [DFS 2] CRM 작성 지침_v1.pptx`는 **구버전**. 현재 URL·실무가 우선이며, 매트릭스는 설정(`07-routing-matrix.md`)에 둔다.

## 8. 안전 규칙 (필수)

1. **배포 이전 Case/WO는 수정하지 않는다.** `CreatedDate`(또는 배포 워터마크)로 컷오프. 과거 Activities 쓰기도 금지.
2. **옵트인만.** 선택하지 않은 Case는 파이프라인에 넣지 않는다(트리거가 와도 no-op, skip 로그만).
3. **쓰기 범위:** 선택된 Case와, 그 Case의 컷오프 이후 허용된 WO / Activities 이어쓰기 / 외부 생성 / Outlook 초안만.
4. **Outlook:** 기본은 초안만. 자동 발송 OFF.
5. **멱등성:** `(workOrderId, targetSystem)` 키로 중복 게시 방지.
6. **실패 격리:** 한 커넥터 실패가 다른 Case에 쓰기를 일으키지 않음.

### 옵트인 방식 (구현 시 택1)

- **A:** Tool 쪽 선택 목록 (`selected_case_ids`) — SF 스키마 변경 없음.
- **B:** SF 체크박스/커스텀 필드 — Salesforce UI에서 보임.

설계상 둘 다 가능. MVP는 SF 관리자 의존이 적은 **A**를 기본으로 기울인다.

## 9. 에러 처리

| 상황 | 동작 |
|------|------|
| 컷오프 이전 / 미선택 | Skip, 사유 로그, **쓰기 API 호출 0건** |
| 인증·권한 실패 | 해당 커넥터 저하 표시, 수동 초안만 제공 |
| 외부 생성 실패 | 재시도 큐; (정책에 따라) 선택 WO에 실패 메모만 |
| 다중 대상 중 일부 성공 | 성공분만 회수, 실패분은 독립 재시도 |
| 중복 감지 | 두 번째 생성 없이 기존 ref 반환 |

## 10. 테스트

- 샌드박스/테스트 Case만으로 E2E: 선택 → 라우팅 → mock 커넥터 → 회수.
- 음성 테스트: 컷오프 이전 Id·미선택 Case → **SF 쓰기 0건**, 외부 생성 0건.
- Outlook: Draft 생성까지, Send 미호출 확인.
- 멱등성: 동일 WO/대상 재실행 → 외부 산출물 1개.

## 11. 연동 인벤토리

도구별 상세는 `docs/integrations/`:

| 파일 | 도구 |
|------|------|
| `00-overview.md` | 허브 모델, 안전, PPT vs 현재 |
| `01-salesforce.md` | 허브 API |
| `02-pms.md` | Redmine계 REST |
| `03-workful-powerapps.md` | Dataverse |
| `04-teams.md` | Graph |
| `05-outlook.md` | Graph 메일 초안 |
| `06-release-notes.md` | Vercel 앱, API 미확정 |
| `07-routing-matrix.md` | 수정 가능한 매트릭스 |
| `08-priority-recommendation.md` | 구현 우선순위 제안 |

## 12. 우선순위 요약

1. Salesforce 읽기 + 옵트인/컷오프 가드 + Activities 회수  
2. PMS 커넥터 (VOC→SW 경로가 가장 명확)  
3. Technical Support용 Outlook 초안  
4. Workful (스키마 조사)  
5. Teams 채널/리스트  
6. 릴리즈 노트 (API 또는 UI 자동화)

## 13. 미결 사항

이 설계 단계에서 확정한 것:

- 아키텍처: **C (하이브리드)**.
- 기존 레코드: **절대 수정하지 않음**; 컷오프 + 옵트인 필수.
- Outlook: 기본 **초안만**.

구현 계획에서 기본값을 고를 것:

- 옵트인 저장: Tool 쪽 vs SF 필드 (§8) — MVP는 **Tool 쪽** 우선.
- Workful Dataverse 테이블·필드 정확한 이름 (조직 조사 필요).
- Issue&VOC 산출물이 SharePoint 리스트인지, Excel인지, 채널만인지.
- 릴리즈 노트: 자체 API 추가 vs UI 자동화.
- MVP 이후 SF 트리거: 폴링 vs CDC / Flow.
- Technical Support Record Type의 SF API 이름.

## 14. 성공 기준

- 사용자가 배포 이후 Case만 골라 자동화할 수 있고, 예전 접수분에는 손대지 않는다.
- 선택한 VOC/SW Case에서 (승인 후) PMS 이슈가 생기고 WO Activities에 URL이 남는다.
- Technical Support WO에 대해 Outlook 초안이 WO 맥락과 함께 생기고, 메일은 자동 발송되지 않는다.
- 새 대상 추가는 허브 재설계 없이 설정 + 커넥터로 가능하다.

## 문서 언어

이후 이 프로젝트의 스펙·검토·계획 문서는 **한국어**로 작성한다.
