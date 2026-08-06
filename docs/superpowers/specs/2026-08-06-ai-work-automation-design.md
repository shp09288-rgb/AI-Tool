# AI 업무 자동화 Tool — Design Spec

**Date:** 2026-08-06  
**Status:** Draft for user review  
**Approach:** C — Hybrid (configurable routing + AI drafts + human gate)

## 1. Goal

Salesforce를 허브로 두고, Case / Work Order 내용을 용도에 맞게 외부 도구에 게시하거나 메일 초안을 만든 뒤, 결과(링크·등록번호)를 Work Order Activities에 회수한다. 손으로 반복하던 CRM 연계 업무를 대체하되, **기존 접수분에는 쓰지 않고**, **사용자가 선택한 Case만** 자동화한다.

## 2. In scope (v1 design)

- Salesforce Case → Work Order 흐름을 트리거로 한 연동 설계
- 플러그인형 커넥터: PMS, Workful(PowerApps), Teams, Outlook, Release Notes
- 설정 기반 라우팅 + AI 본문/메일 초안 + 게시·발송 전 Human Gate
- 옵트인 선택 UI/플래그, 배포 컷오프(기존 레코드 불변)
- 도구별 API·연동 검토 문서 (`docs/integrations/`)

## 3. Out of scope (for this spec)

- 배포 이전 Case/WO 일괄 마이그레이션·일괄 수정
- Outlook 자동 발송(기본은 Draft만)
- 릴리즈 노트 앱 소스 리팩터(필요 시 후속)
- IT 권한 발급·Connected App 생성 자체(전제 조건으로만 기록)

## 4. Architecture

```text
User selects Case (opt-in)
        │
        ▼
Cutoff check (CreatedDate / Id after deploy) ──fail──► skip (no writes)
        │
        ▼
SF Adapter reads Case + related Work Orders
        │
        ▼
Router (YAML/JSON: RecordType + Relevant Department + work kind)
        │
        ├─ Draft AI (title/body/mail draft; classify only if ambiguous)
        ├─ Human Gate (preview / edit / approve)  [default ON]
        └─ Connectors → { ref, url }
                │
                ▼
        Writeback → Work Order Activities (append only on selected records)
```

### Principles

- Salesforce is the system of record. External posts are derivatives; results write back to WO Activities.
- Routing is data-driven so PPT (legacy guideline) can differ from current practice.
- New systems = new connector implementing a common interface.
- Default safety: no write to historical records; no auto-send mail; human approve before post.

## 5. Components

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| Case Selector | User picks which Cases enter automation | Local store and/or SF flag |
| Cutoff Guard | Block any Case/WO before `automation_enabled_after` | Config timestamp |
| SF Adapter | Read Case/WO; append Activities; never bulk-update history | Salesforce REST + OAuth |
| Router | Map signals → connector list | Routing config |
| Draft AI | Drafts content; optional classification assist | LLM + Case/WO fields |
| Human Gate | Preview/approve before external side effects | UI or Teams adaptive card |
| Connectors | `create` / `draft` → `{ ref, url }` | Per-tool APIs |
| Writeback | Append external refs to Activities | SF Adapter |
| Job Log | Per-Case run status, skip reasons, retries | Local DB/files |

### Connector interface (conceptual)

```text
input:  { case, workOrder, draftContent, options }
output: { ok, ref, url, raw? } | { ok: false, error, retryable }
```

## 6. Primary workflows

### 6.1 VOC → external post (e.g. SW → PMS)

1. User selects Case (opt-in) that has or will have VOC Work Order.
2. Guard: Case must be after cutoff.
3. Router uses Record Type `VOC` + Relevant Department (e.g. `SW`) → `pms`.
4. AI drafts subject/description (align title with Salesforce).
5. Human Gate approve → PMS issue create → URL returned.
6. Append to WO Activities: `PMS – {url}`.

### 6.2 Technical Support → Outlook

1. Case for field/출장 대응 → Work Order Record Type `Technical Support`.
2. User opt-in on that Case.
3. Router → `outlook`.
4. AI drafts To/Subject/Body from Case + WO.
5. Create **Outlook Draft** with WO summary attachment and/or Salesforce record link.
6. User reviews in Outlook and sends manually.
7. Optional writeback: draft/sent timestamp or Message-ID in Activities.

### 6.3 Release notes (secondary loop)

- Triggered by improvement SW version emails, not primarily by VOC routing.
- Summarize changelog → draft updates for Release Notes app.
- Lower priority until app API is confirmed.

## 7. Routing matrix (draft — configurable)

| Signal (approx.) | Target | Artifact | Activities writeback |
|------------------|--------|----------|----------------------|
| VOC + Dept SW (bug/feature/inquiry) | PMS | Issue | `PMS – URL` |
| SRD / Work Pool style | Workful (Dataverse) | Registration | `Work Pool – 등록번호` |
| MC / OBQ·QI | Teams | Message or list item | `OBQ/QI – 공유 링크` |
| Issue & VOC tracking | Teams (+ Sheet/SharePoint if used) | Row/message | 접수번호 등 |
| Technical Support (출장대응; confirm SF API Record Type name) | Outlook | Mail **draft** + WO attach/link | optional Message-ID |
| SW version mail | Release Notes | Update card/item | (SF link later) |
| HW / Manual / Sales / TS / QI … | TBD in config | — | AI suggest only until mapped |

Reference: `reference/2025-08-27 [DFS 2] CRM 작성 지침_v1.pptx` is **legacy**. Current URLs and practice win; matrix lives in config (`07-routing-matrix.md`).

## 8. Safety rules (non-negotiable)

1. **No mutation of pre-deploy Cases/WOs.** Cutoff by `CreatedDate` (or recorded deploy watermark). Writes to historical Activities are forbidden.
2. **Opt-in only.** Unselected Cases never enter the pipeline (triggers become no-op with skip log).
3. **Write scope:** only selected Case and its eligible post-cutoff Work Orders / Activities append / external creates / Outlook drafts.
4. **Outlook:** draft-only by default; auto-send off.
5. **Idempotency:** key `(workOrderId, targetSystem)` to avoid duplicate posts.
6. **Failure isolation:** one connector failure does not write to unrelated Cases.

### Opt-in mechanism (choose at implementation)

- **A:** Tool-side selection list (`selected_case_ids`) — no SF schema change.
- **B:** SF checkbox/custom field (e.g. `AI_Automation__c`) — visible in Salesforce UI.

Design allows either; prefer A for zero SF admin dependency at MVP, B for team-wide visibility later.

## 9. Error handling

| Case | Behavior |
|------|----------|
| Before cutoff / not selected | Skip; log reason; **zero write API calls** |
| Auth/permission failure | Mark connector degraded; offer manual draft only |
| External create fails | Retry queue; append failure note only on the selected WO if user opted into failure logging |
| Partial multi-target | Succeeded targets write back; failed targets retry independently |
| Duplicate detected | No second create; return existing ref |

## 10. Testing

- E2E on sandbox/test Cases only: select → route → mock connectors → writeback.
- Negative tests: pre-cutoff Id and unselected Case → assert **no SF write**, no external create.
- Outlook: assert Draft created, Send not called.
- Idempotency: re-run same WO/target → single external artifact.

## 11. Integration inventory

Detailed per-tool notes live under `docs/integrations/`:

| File | Tool |
|------|------|
| `00-overview.md` | Hub model, safety, PPT vs current |
| `01-salesforce.md` | Hub API |
| `02-pms.md` | Redmine-style REST |
| `03-workful-powerapps.md` | Dataverse |
| `04-teams.md` | Graph |
| `05-outlook.md` | Graph mail drafts |
| `06-release-notes.md` | Vercel app; API TBD |
| `07-routing-matrix.md` | Editable matrix |
| `08-priority-recommendation.md` | Build order suggestion |

## 12. Priority recommendation (summary)

1. Salesforce read + opt-in/cutoff guards + Activities writeback  
2. PMS connector (highest clarity VOC→SW path)  
3. Outlook draft for Technical Support  
4. Workful (schema discovery)  
5. Teams channels/lists  
6. Release Notes (API or UI automation)

## 13. Open decisions

Resolved for this design phase:

- Architecture approach: **C (hybrid)**.
- Existing records: **never mutate**; cutoff + opt-in required.
- Outlook: **draft-only** by default.

Still open (implementation plan will pick defaults):

- Opt-in storage: Tool-side vs SF field (see §8) — default lean **Tool-side** for MVP.
- Exact Workful Dataverse table/field names (needs org inspection).
- Whether Issue&VOC artifact is SharePoint list, Excel, or channel-only.
- Release Notes: first-party API vs UI automation.
- Salesforce trigger after MVP: polling vs Change Data Capture / Flow.
- Exact SF API name for Technical Support Record Type.

## 14. Success criteria

- User can select post-deploy Cases and run automation without touching older records.
- For a selected VOC/SW Case, PMS issue is created (after approval) and URL appears on WO Activities.
- For Technical Support WO, Outlook draft exists with WO context; mail is not auto-sent.
- Adding a new target requires config + connector, not a redesign of the hub.
