# Outlook

## 역할

**Technical Support** Work Order(출장/현장 대응 등)에서, 엔지니어가 손으로 쓰던 메일을 **자동으로 초안**으로 만들고 Work Order 맥락을 첨부 또는 Salesforce 링크로 넣는다. 발송은 사용자가 검토 후 한다.

## 흐름

```text
Case (출장 / 현장 대응)
  → Work Order Record Type: Technical Support
  → 사용자가 Case 옵트인
  → AI가 To / Cc / Subject / Body 초안
  → Graph: Outlook 초안 생성 (+ 첨부)
  → 사용자가 Outlook에서 수정 → 발송
  → (선택) Activities에 초안 생성 / Message-ID 메모
```

## API 유무

| 기능 | 가능 여부 | 비고 |
|------|-----------|------|
| 초안 생성 | 가능 | `POST /me/messages` 또는 `/users/{id}/messages` |
| sendMail | 가능 | **v1 기본에서는 사용하지 않음** |
| 첨부 &lt; 3MB | 가능 | 초안에 `fileAttachment` |
| 대용량 첨부 | 가능 | upload session (대략 ≤ 150MB) |
| 인증 | Entra OAuth | `Mail.ReadWrite` (+ 나중에만 `Mail.Send`) |

문서: [메시지 만들기·보내기](https://learn.microsoft.com/en-us/graph/outlook-create-send-messages)

## 인증

- **위임(사용자가 로그인)** — 초안이 **본인 사서함**에 생겨 실무 UX에 맞음.
- 또는 애플리케이션 + 사서함 접근 정책(Exchange 관리자 필요, 더 어려움).

**권장:** 담당 엔지니어 사서함에 대한 위임 Graph.

## 연결 방식

```text
1. 수신자 수집(Case의 Contact/Account, 또는 사용자가 수정).
2. 본문 템플릿: site, tool, 증상, WO 번호, SF 딥링크.
3. 첨부 옵션:
   a) Tool이 만든 PDF/HTML 요약
   b) Salesforce WO 링크만 (가장 단순)
   c) SF에서 공식 export(후속)
4. POST 초안 → Tool UI에 webLink / draft id 표시.
5. 사용자가 “자동 발송”을 켜기 전에는 send를 호출하지 않음.
```

### 초안 내용 제안

- 제목: `[Technical Support] {Site} / {Tool} / {짧은 증상}`
- 본문: Case Subject, WO 번호, 핵심 사실, 요청 사항, SF URL
- 첨부 파일명(선택): `WO-{number}-summary.pdf`

## 활용 시나리오

1. Technical Support WO가 있는 선택 Case → “메일 초안 만들기” 한 번.
2. 여러 Case 선택 → 여러 초안(속도 제한 주의).
3. Graph 거부 시: 복사해 넣을 로컬 초안 텍스트 표시.

## 확인 사항

- [ ] Technical Support Record Type의 API 이름
- [ ] 기본 To/Cc 규칙(고객 vs 내부)
- [ ] SF에 WO “공식” PDF 첨부/내보내기가 있는지
- [ ] 사서함: 개인 vs 공유 서비스 사서함

관련: Teams 채널 Field Service / Installation Excel과 메일·SF를 묶는 검토는 [09-teams-excel-outlook-feasibility.md](./09-teams-excel-outlook-feasibility.md).

## 위험

- 고객에게 자동 발송은 위험 — 초안만 유지.
- Account/Contact 매핑 오류로 수신자 잘못 — To/Cc도 Human Gate.
- 공유 사서함은 `/me`와 권한이 다름.
