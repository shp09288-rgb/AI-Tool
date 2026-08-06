# Microsoft Teams

## 역할

다음을 위한 채널·관련 산출물:

- Workful과 병행되는 Work Pool 가시성(아직 쓰는 경우)
- OBQ / QI (MC 요청) — 공유 링크 회수
- Issue & VOC 추적(지침상 DISPLAY 시트·에이징 언급)

## API 유무

| 기능 | 가능 여부 | API |
|------|-----------|-----|
| 채널 메시지 게시 | 가능 | Graph `POST /teams/{id}/channels/{id}/messages` |
| 채팅 메시지 | 가능 | `/chats/{id}/messages` |
| SharePoint 리스트 항목 | 가능 | `/sites/{id}/lists/{id}/items` |
| SharePoint Excel | 가능 | Graph Excel API (복잡한 시트는 취약) |
| Adaptive Card 알림 | 가능 | 메시지 또는 Power Automate |

문서: [chatMessage 보내기](https://learn.microsoft.com/en-us/graph/api/chatmessage-post)

## 인증

- Entra 앱: 위임 또는 애플리케이션 권한(`ChannelMessage.Send`, `Sites.ReadWrite.All` 등 — 최소 권한).
- 애플리케이션 권한은 보통 관리자 동의 필요.
- 전용 봇/서비스 신원으로 게시하는 편을 권장.

## 연결 방식

```text
라우터 대상 = teams_obq | teams_voc | teams_notify
  → teamId + channelId (설정)
  → 메시지 게시 또는 리스트 항목 생성
  → 공유 링크 / 메시지 딥링크 반환
  → SF Activities: "OBQ, QI – {link}" 등
```

### Issue & VOC 시트 주의

CRM 지침: `DISPLAY_Issue and VOC list`만 수정, 에이징 자동 계산. 보호된 Excel이면:

- API 쓰기용 **SharePoint 리스트** 미러를 두거나,
- Power Automate로 정해진 플로만 쓰거나,
- Human Gate가 수동 붙여넣기용 초안만 제공(폴백).

Graph로 하이퍼링크 컬럼 생성은 제약이 있을 수 있어, 컬럼 타입을 먼저 확인한다.

## 활용 시나리오

1. MC / OBQ·QI 요청 → 채널 게시 또는 리스트 행 + 링크 회수.
2. Human Gate 알림(“Case X PMS 게시 승인”).
3. Workful/PMS 성공 후 선택 알림.

## 확인 사항

- [ ] OBQ, QI, Issue&VOC, Work Pool용 team/channel ID
- [ ] 채널별 산출물 종류(메시지 vs 리스트 vs Excel)
- [ ] 권한 모델(사용자 위임 vs 앱 전용)
- [ ] Workful이 Teams Work Pool 등록을 대체했는지

## 위험

- 잘못된 채널 스팸 — 게시는 Human Gate 필수.
- Excel 자동화는 깨지기 쉬움 — 주 경로로 쓰지 말 것.
- 앱으로 메시지 보내기는 Teams 정책 허용이 필요할 수 있음.
