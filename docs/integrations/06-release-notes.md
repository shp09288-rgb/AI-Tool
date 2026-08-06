# 릴리즈 노트 (release-note-web-db-tool)

## 역할

VOC→PMS와 **별도** 루프: **개선 SW 디버그/배포 버전**이 오면(대개 **메일**), 엔지니어가 개선 항목을 확인하고 릴리즈 노트 웹 앱에 직접 입력한다.

URL: `https://release-note-web-db-tool.vercel.app/dashboard`

## API 유무

| 기능 | 상태 | 비고 |
|------|------|------|
| 공개 문서화된 API | **없음(조사 시점)** | 대시보드는 Next.js UI |
| `/api` 프로브 | 404 | 비공개 라우트는 있을 수 있음 |
| 자체 API 추가 | **미정** | 저장소를 소유하면 가장 바람직 |
| 브라우저 자동화 | 폴백 가능 | 깨지기 쉬움 |
| DB 직접 | 백엔드/DB 자격이 있을 때만 | 별도 경로 |

## 연결 후보

### A. 앱에 API 추가 (소유 시 권장)

```text
POST /api/cards 또는 /api/updates
  { site, equipment, version, items[], sourceMailId }
→ 카드 id / URL 반환
```

### B. 기존 백엔드 재사용

UI가 이미 Supabase/Firebase/자체 API를 쓰면, 로그인 상태에서 Network 탭으로 동일 엔드포인트를 호출.

### C. UI 자동화

실험용 최후 수단. 무인 운영용이 아님.

### 메일 수신

```text
Outlook/Graph: SW 버전 메일함/폴더 감시
  → AI가 버전 + 개선 bullet 추출
  → Human Gate
  → 릴리즈 노트 커넥터
```

Technical Support 초안과 Graph 인증을 공유할 수 있으나, 메일 **읽기** 권한은 최소 폴더로 제한한다.

## 활용 시나리오

1. 새 버전 메일 → RN 항목 제안 → 사용자 승인 → 카드 생성/갱신.
2. Case Id를 알면 RN 카드 URL을 SF Activities에 선택 기록.
3. 기본적으로 VOC Relevant Department 라우팅에는 넣지 않음.

## 확인 사항

- [ ] 저장소 위치, API 추가 가능 여부
- [ ] 대시보드 쓰기 권한 모델
- [ ] 데이터 모델: Site / Equipment / 버전 카드
- [ ] 버전 안내 메일함·폴더 규칙

## 위험

- API 없으면 자동화 품질이 낮음.
- 잘못된 RN 게시는 여러 사이트에 영향 — Human Gate 필수.
- API 경로가 생기기 전까지 PMS/Outlook보다 우선순위 낮음.
