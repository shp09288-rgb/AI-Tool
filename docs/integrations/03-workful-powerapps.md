# Workful (PowerApps / Dataverse)

## 역할

현재 “Work Pool” 성격의 등록 UI는 **Power Apps** 앱이다(Teams 채널만이 아님). SRD 성향 등록 Work Order에 쓰이며, 회수는 보통 **등록번호**.

## 진입 URL

테넌트 `7634c4dc-9a4e-4615-932e-99f681471d92` 아래 Power Apps play URL(사용자가 제공한 링크). 경로의 앱 id(`a/10ada818-…`)가 보인다.

구 PPT는 “Work Pool(Teams)”로 표기 — Teams는 알림/부가 UI일 수 있고, **데이터가 Dataverse에 있으면 API 경로는 Dataverse**다.

## API 유무

| 기능 | 가능 여부 | 비고 |
|------|-----------|------|
| Dataverse Web API | 앱이 Dataverse를 쓰면 가능 | OData v4 |
| 인증 | Microsoft Entra ID | 앱 등록 + 애플리케이션 사용자 |
| 행 생성 | `POST /api/data/v9.2/{entityset}` | 논리 이름 필요 |
| SharePoint만 쓰는 앱 | 가능 | 그러면 Graph/SharePoint API |

문서: [Dataverse Web API](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/overview)

## 인증

1. Entra 앱 등록.
2. 대상 테이블 보안 역할이 있는 Dataverse 애플리케이션 사용자.
3. Client credentials → 조직 URL용 Bearer (`https://{org}.crm.dynamics.com`).

## 연결 방식

```text
1. 데이터 저장소 확인: Dataverse 테이블 vs SharePoint 리스트 vs SQL.
2. 컬럼 파악(등록번호, site, tool, subject, 요청자).
3. POST 생성 → 자동번호/id 회수.
4. SF Activities: "Work Pool – {등록번호}" (현재 표기명에 맞춤).
```

### 조사 체크리스트

- [ ] 앱을 열어 어떤 테이블을 쓰는지(네트워크 또는 Power Apps Studio)
- [ ] 환경 URL + entity set 이름
- [ ] “등록번호” 필드와 필수 필드
- [ ] Teams가 등록 UI인지, 링크만인지

## 활용 시나리오

1. 라우터가 SRD / Work Pool형 WO에 `workful` 선택.
2. AI가 Case/WO로 행 필드 초안.
3. Human Gate → 생성 → 번호 회수.
4. (선택) Teams 커넥터로 신규 행 딥링크 알림.

## 위험

- 스키마를 알기 전까지 조사 비용이 큼(릴리즈 노트 다음으로 큼).
- Power Automate가 생성 시 반드시 돌아야 하면, Dataverse 직접 insert가 검증을 우회할 수 있음 — 가능하면 동일 플로 트리거.
- 앱 권한에 테넌트 관리자 승인 필요할 수 있음.
