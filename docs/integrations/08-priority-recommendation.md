# 우선순위 제안

방식 C 기준 구현 순서. 설계 스펙 승인 및 구현 계획 작성 **전에는 코드를 시작하지 않는다**.

## 권장 순서

| 우선순위 | 항목 | 이유 |
|----------|------|------|
| P0 | 옵트인 Case 선택기 + 컷오프 가드 + 작업 로그 | 안전. 과거 이력을 건드리지 않고 이후 기능을 가능하게 함 |
| P0 | Salesforce 어댑터 (Case/WO 읽기, Activities 이어쓰기) | 허브 |
| P1 | PMS 커넥터 + VOC/SW 라우트 | 가치가 가장 명확한 E2E, API 가능성 높음 |
| P1 | Human Gate (최소 UI) | 외부 생성 전 필수 |
| P2 | Technical Support용 Outlook 초안 | 일상 시간 절감, Graph 문서화 양호 |
| P3 | Workful / Dataverse | 스키마 조사 필요 |
| P3 | Teams OBQ/QI 알림 또는 리스트 | 산출물 종류 확인 후 |
| P4 | 릴리즈 노트 | API 소유/추가에 막힘, 별도 메일 루프 |
| P5 | 백그라운드 트리거(CDC/폴링) | 수동 실행이 안정된 뒤에만 |

## 초기 마일스톤에서 하지 않을 것

- 예전 Case/WO 이전·재작성
- Outlook 자동 발송
- Human Gate 없는 무인 게시
- 매트릭스 매칭 없는 완전 AI 자동 라우팅

## 의존 관계

```text
P0 가드 + SF 읽기/회수
    ├── P1 PMS + Gate
    ├── P2 Outlook 초안
    ├── P3 Workful / Teams (스키마 확인 후 병렬 가능)
    └── P4 릴리즈 노트 (API 생기면 병렬 가능)
```

## 첫 마일스톤 성공 기준

사용자가 **새로 만든** 테스트 Case를 선택 → 승인 → PMS 이슈 생성 → WO Activities에 URL → 컷오프 **이전** Case에는 **쓰기 0건**.
