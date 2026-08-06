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
