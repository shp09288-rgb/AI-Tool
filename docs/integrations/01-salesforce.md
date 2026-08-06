# Salesforce (허브)

## 역할

Case·Work Order의 시스템 오브 레코드. 자동화는 **선택한 배포 이후 레코드만 읽고**, 허용된 범위에서 Activities를 **이어 붙이거나** 관련 WO를 만들 수 있다. 과거 Case를 일괄 수정하지 않는다.

## API 유무

| 기능 | 가능 여부 | 비고 |
|------|-----------|------|
| REST sObject CRUD | 가능 | `/services/data/vXX.X/sobjects/{Object}/{Id}` |
| SOQL 조회 | 가능 | `/query?q=` |
| OAuth | 가능 | Connected App 또는 External Client App; 서버용 Client Credentials / JWT |
| CDC / Platform Events | 가능(조직 설정에 따름) | 폴링 대신 트리거로 사용 가능 |
| Composite / Tree | 가능 | 관련 레코드 일괄 생성 시 |

공식: [Salesforce REST API](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_what_is_rest_api.htm)

## 인증 (권장)

1. API 스코프가 있는 Connected App / External Client App 생성.
2. 최소 권한 통합 사용자(Case/WO 읽기, 회수용 Activities 필드만 갱신, 필요 시 WO 생성).
3. 무인 Tool에는 **Client Credentials** 또는 **JWT Bearer** 선호.
4. client id/secret은 저장소 밖에 보관.

## 객체·필드 (화면·지침에서 관찰)

| 영역 | 예시 | 용도 |
|------|------|------|
| Case | Type, Priority, Origin, Status, Subject, Description, Asset | 초안 맥락 |
| Case 분류 | Issue Classified as SW, OBJ Type 등 | 라우팅 힌트 |
| Case Activities (긴 텍스트) | 시간순 메모 | 보조 로그(선택) |
| Work Order | Record Type(VOC, Technical Support 등), Status, Priority | 주 라우팅 키 |
| Relevant Department | QI, SW, HW, Manual, P/L Spec, Sales, TS | 대상 시스템 키 |
| VOC 필드 | VOC Title, 배경/문제/영향, 제안 등 | PMS/Teams 본문 |
| [VOC] Activities | 외부 참조용 자유 텍스트 | **주 회수 위치** |

정확한 API 이름(`__c`)은 조직 Describe API로 확인한다.

## 연결 방식

```text
Tool ──OAuth──► Salesforce
  GET Case + WorkOrders (+ Asset)
  PATCH WorkOrder Activities (이어쓰기만, 선택·컷오프 이후만)
  POST WorkOrder (사용자 주도 흐름에서 생성이 필요할 때만)
```

### 트리거 옵션

| 옵션 | 장점 | 단점 |
|------|------|------|
| 선택한 Case에서 “실행” 클릭 | 가장 안전, 옵트인과 맞음 | 완전 백그라운드는 아님 |
| 선택 플래그 SOQL 폴링 | 단순 | 지연·API 사용량 |
| CDC / Flow → 웹훅 | 거의 실시간 | SF 관리자 작업 필요 |

**v1 권장:** 선택 Case에 대한 명시적 실행. 이후 가벼운 폴링은 선택.

## 안전 제약

- `CreatedDate >= automation_enabled_after`(또는 Id 워터마크) 필수.
- Case가 Tool 선택 목록(또는 SF 옵트인 필드)에 있어야 함.
- 선택 밖 Case/WO 갱신 금지.
- Activities는 **이어 붙이기만**: 기존 텍스트 삭제·덮어쓰기 금지.

## 활용 시나리오

1. 모든 커넥터 초안을 위한 **허브 읽기**.
2. **VOC 경로:** WO 확보/생성 → 외부 게시 후 Activities에 `PMS – url` 등.
3. **Technical Support 경로:** WO 준비 → Outlook 초안 → (선택) Activities 메모.
4. **옵트인 플래그**(SF 필드 방식 선택 시): 팀원이 SF에서 자동화 상태를 볼 수 있음.

## IT/조직 확인 사항

- [ ] Connected App / External Client App 허용 여부
- [ ] 통합 사용자 + 필요 객체/필드 CRUD·FLS
- [ ] 커스텀 필드 API 이름 Describe
- [ ] 사용 Record Type에 대한 API WO 생성 허용 여부
- [ ] 이후 백그라운드 동기화 시 CDC 사용 가능 여부

## 위험

- 커스텀 Record Type·검증 규칙이 API 생성을 막을 수 있음.
- 긴 텍스트 Activities는 용량 제한 — 이어 붙일 때 주의.
- 컷오프 로직 오류 시 운영 이력을 건드릴 수 있음 — 자동 테스트로 가드.
