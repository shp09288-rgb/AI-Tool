# 연동 검토 개요

Salesforce를 중심으로 한 AI 업무 자동화. 접근 방식 **C(하이브리드)**: 설정 가능한 라우팅 표 + AI 초안 + 사람 승인 게이트.

## 허브 모델

```text
Case (사용자 옵트인, 배포 이후만)
  → Work Order
  → 라우터 (Record Type + Relevant Department + 업무 종류)
  → 커넥터(들)
  → Work Order Activities에 결과 회수
```

## 안전 규칙 (모든 커넥터 공통)

- 배포 컷오프 **이전**에 생성된 Case/Work Order는 **수정하지 않는다**.
- 사용자가 **명시적으로 선택한** Case만 자동화한다.
- 외부 생성·메일 발송은 Human Gate 이후만 (메일은 기본 초안만).

## 현재 도구 URL (PPT보다 현재 링크·실무 우선)

| 도구 | 현재 진입점 | 비고 |
|------|-------------|------|
| Salesforce | `parksystems.lightning.force.com` | 허브 |
| Workful | PowerApps play URL (테넌트 `7634c4dc-…`) | PPT는 “Work Pool(Teams)” — 현재 UI는 PowerApps |
| 릴리즈 노트 | `release-note-web-db-tool.vercel.app/dashboard` | VOC 루프와 별도 |
| PMS | `pms.parksystems.com` | Redmine계 이슈 트래커로 추정 |
| Teams | 조직 채널 (Work Pool / OBQ·QI / Issue&VOC) | Graph |
| Outlook | Exchange Online 사서함 | Technical Support WO → 메일 초안 |

구버전 참고: `reference/2025-08-27 [DFS 2] CRM 작성 지침_v1.pptx` — 필드·습관 참고용, 라우팅 확정 근거는 아님.

## 연결 방식 옵션: 직접 API vs MCP

커넥터를 만들 때 두 가지 경로가 있으며, 도구별로 선택한다.

| 방식 | 설명 | 적합한 경우 |
|------|------|-------------|
| **직접 API 커넥터** (현재 MVP 방식) | Python 코드가 REST API를 직접 호출 (`httpx`) | 무인 실행, 예약 실행, CLI/서버 배포. 재현성·테스트 용이 |
| **MCP 서버 경유** | Cursor 등 AI 에이전트가 MCP 서버를 통해 도구를 호출 | 에이전트 대화 중 수동 실행, 초안 검토·수정을 대화로 진행, 빠른 프로토타입 |

### 도구별 MCP 지원 현황 (검토 필요 항목 포함)

| 도구 | MCP 서버 | 비고 |
|------|----------|------|
| Salesforce | 공식/커뮤니티 MCP 서버 존재 (SOQL, sObject CRUD) | 직접 API와 동일한 Connected App 인증 필요. 안전 가드(컷오프·옵트인)는 MCP를 쓰더라도 우리 쪽 파이프라인에서 강제해야 함 |
| Teams / Outlook | Microsoft 365 계열 MCP 서버 존재 (Graph 기반) | 메일 초안·채널 게시에 활용 가능. Graph 권한 동의는 동일하게 필요 |
| PMS (Redmine계) | 커뮤니티 Redmine MCP 서버 존재 | REST API 활성화 전제는 동일 |
| Workful (PowerApps/Dataverse) | Dataverse MCP 서버 (Microsoft 제공) 존재 | 테이블 스키마 조사에 특히 유용 |
| 릴리즈 노트 (자체 앱) | 없음 — 필요 시 자체 MCP 서버 제작 가능 | 앱에 API를 추가한 뒤 MCP 래핑하는 순서가 자연스러움 |

### 권장 조합

- **정기·반복 실행 경로(파이프라인)**: 직접 API 커넥터 유지 — Human Gate, 멱등성, 컷오프를 코드로 강제할 수 있음.
- **탐색·스키마 조사·수동 개입**: MCP 활용 — 예: Workful Dataverse 테이블 구조 파악, Salesforce 필드 API 이름(Describe) 확인, 초안을 대화로 다듬은 뒤 파이프라인에 넘기기.
- MCP를 실행 경로에 넣는 경우에도 **옵트인·컷오프·승인 게이트는 생략 불가** — MCP는 연결 수단일 뿐 안전 규칙의 예외가 아니다.

## 문서 목록

| 문서 | 목적 |
|------|------|
| [01-salesforce.md](./01-salesforce.md) | 허브 API, Case/WO, Activities, 옵트인 |
| [02-pms.md](./02-pms.md) | 이슈 생성 + URL 회수 |
| [03-workful-powerapps.md](./03-workful-powerapps.md) | Dataverse 등록 |
| [04-teams.md](./04-teams.md) | 채널 / 리스트 |
| [05-outlook.md](./05-outlook.md) | Technical Support → 메일 초안 |
| [06-release-notes.md](./06-release-notes.md) | 버전 메일 → RN 업데이트 |
| [07-routing-matrix.md](./07-routing-matrix.md) | 수정 가능한 라우팅 표 |
| [08-priority-recommendation.md](./08-priority-recommendation.md) | 구현 우선순위 제안 |

통합 설계: `docs/superpowers/specs/2026-08-06-ai-work-automation-design.md`
