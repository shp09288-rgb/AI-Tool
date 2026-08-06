# PMS (pms.parksystems.com)

## 역할

SW 관련 VOC Work Order(버그, 없는 기능, 문의)의 주 게시 대상. 이슈 URL을 Salesforce WO Activities에 회수한다.

## API 유무

UI·URL(` /issues/{id}`, `/my/page`)이 **Redmine 계열** 트래커와 유사하다. 조직 확정 전까지 Redmine REST를 작업 가정으로 둔다.

| 기능 | 가능성 | 엔드포인트 패턴 |
|------|--------|-----------------|
| REST 활성화 | 관리자 설정 | 관리 → 설정 → API |
| 인증 | API 키 헤더 | `X-Redmine-API-Key` |
| 이슈 생성 | 가능(가정) | `POST /issues.json` |
| 이슈 조회 | 가능 | `GET /issues/{id}.json` |
| 갱신/노트 | 가능 | `PUT /issues/{id}.json` |
| 첨부 | Redmine이면 가능 | 업로드 후 연결 |

문서: [Redmine REST API](https://www.redmine.org/projects/redmine/wiki/Rest_Api)

**반드시 확인:** REST 켜짐 여부, 커스텀 필드(SW ver., Site/Tool), DFS/SW용 project·tracker ID.

## 인증

- My Account(또는 서비스 계정)의 **API 키**.
- 쿼리 `?key=`보다 헤더 권장(로그 노출 감소).
- HTTPS만 사용.

## 연결 방식

```text
라우터 (VOC + Dept SW)
  → SF Subject/Description/Priority/SW ver. 매핑
  → POST /issues.json
  → URL https://pms.parksystems.com/issues/{id} 구성
  → SF Activities: "PMS – {url}"
```

### 필드 매핑 (초안)

| SF / 지침 | PMS |
|-----------|-----|
| Site / Tool / Subject (SF와 동일 제목) | `subject` |
| 상세 문제 + 작업 내용 | `description` |
| Priority (SF와 맞춤) | `priority_id` |
| SW version | 커스텀 필드(있으면) |
| 로그/첨부 | API가 허용하면 Redmine 첨부 |

CRM 지침: 제목은 Salesforce와 동일, 내용은 상세, 해당 시 SW ver. 필수.

## 활용 시나리오

1. 선택 Case → VOC WO → Dept SW → Human Gate 후 PMS 이슈 생성.
2. (후속, v1 아님) SF Activities 변경 시 PMS 노트 갱신.
3. 멱등 재실행: 이 WO Activities에 이미 PMS URL이 있으면 생성 생략.

## 확인 사항

- [ ] 제품이 Redmine(또는 포크)인지, REST가 켜져 있는지
- [ ] SW VOC용 project_id / tracker_id
- [ ] 커스텀 필드 ID
- [ ] 서비스 계정 권한(이슈 추가, 프로젝트 조회)
- [ ] 첨부 용량·필수 필드 검증

## 위험

- Redmine이 아닌 커스텀이면 페이로드가 달라짐.
- 네트워크/VPN: Tool 호스트가 `pms.parksystems.com`에 도달해야 함.
- Activities 텍스트 파싱만으로 중복 방지하면 실패할 수 있음 — 멱등 저장소도 사용.
