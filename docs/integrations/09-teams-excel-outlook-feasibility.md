# Teams / SharePoint Excel ↔ Salesforce WO ↔ Outlook 초안 — 실현 가능성

DFS2 채널 Files의 Field Service / Installation Excel을 Salesforce Technical Support Work Order와 Outlook 업무보고 메일 초안에 연결할 수 있는지, Microsoft Graph 공식 문서 기준 검토.

**결론(요약):** Graph로 **경로 기반 파일 찾기·목록**, **Excel(.xlsx) 셀/테이블 읽기·행 추가**, **HTML 본문 Outlook 초안 + .xlsx/PDF 첨부**는 모두 가능. 다만 Excel 쓰기·동시편집·복잡한 시트는 취약하므로 **v1은 링크+요약 초안 중심**, Excel 행 추가는 Human Gate 뒤에 선택적으로. 안전 규칙(옵트인·컷오프·초안만·자동 발송 금지)은 [00-overview](./00-overview.md)·[05-outlook](./05-outlook.md)와 동일.

---

## 제품 맥락

| 항목 | 내용 |
|------|------|
| Teams | 팀 DFS2 → 채널 Files (SharePoint) |
| 경로 예 | `Documents/General/DFS2/SDC/A6_NX-TSH2326 #1/` |
| Field Service Report | `[DFS2] 2024 Field Service Report_SDC A6_NX-TSH2326_rev01.xlsx` — 설치 후 유지보수 출장용, 이력 누적 |
| Installation Report | `[Installation Report] SDC A6 TSH2326 #1.xlsx` — `Installation 레포트_백업용/` 하위 |
| SF 연동 | Case / Work Order (Technical Support) |
| Outlook | 기존 업무보고 메일 형식에 맞는 **초안만** (발송은 사람) |
| Entra 앱 | Client ID `70d0a9a1-419e-4ea2-a06c-9a4e4a322cd7` (스파이크 `_onedrive_spike.py`: `Files.ReadWrite`, 테넌트 `7634c4dc-…`) |
| 동의 이슈 | 과거 `Files.ReadWrite` 관리자 동의 대기 — SharePoint/Teams 범위면 `Sites.*` / `Files.*.All` 추가 검토 필요 |

엔지니어는 Excel을 **계속 수동으로** 채우며 이력을 쌓는다. Tool은 대체하지 않고 **연결·초안·회수**에 집중한다.

---

## Graph 능력 점검 (질문별)

### 1. Teams 채널 SharePoint 폴더를 경로로 찾고 목록할 수 있는가?

**가능.**

| 단계 | API | 근거 |
|------|-----|------|
| 채널 Files 루트 | `GET /teams/{team-id}/channels/{channel-id}/filesFolder` → `driveItem` (`driveId`, folder `id`, `webUrl`) | [Get filesFolder](https://learn.microsoft.com/en-us/graph/api/channel-get-filesfolder?view=graph-rest-1.0) |
| 경로로 항목 | `GET /drives/{drive-id}/root:/{item-path}` 또는 `.../items/{folder-id}:/{relative-path}` | [Get driveItem](https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0), [Addressing driveItems](https://learn.microsoft.com/en-us/graph/onedrive-addressing-driveitems) |
| 하위 목록 | `.../root:/{folder-path}:/children` | 동일 addressing 문서 |

권장 패턴: `filesFolder`로 `driveId` + 채널 루트 `itemId`를 캐시한 뒤, 상대 경로 `General/DFS2/SDC/A6_NX-TSH2326 #1`로 접근. 라이브러리명·URL을 하드코딩하지 말 것 ([Teams shared/private channels guidance](https://learn.microsoft.com/en-us/microsoftteams/platform/build-apps-for-shared-private-channels)).

**주의:** 채널명 특수문자로 `filesFolder`가 실패할 수 있음([Known issues](https://learn.microsoft.com/en-us/graph/known-issues) 참조). 폴더명에 `#`·공백·한글이 있으면 **세그먼트별 percent-encoding** 필수(아래 §5).

### 2. Excel 셀/테이블을 읽을 수 있는가? (Excel REST / workbook session)

**가능 (.xlsx / 비즈니스 OneDrive·SharePoint만).**

| 기능 | API | 근거 |
|------|-----|------|
| Workbook 진입 | `/drives/{id}/items/{id}/workbook/...` 또는 path `.../root:/{path}:/workbook/` | [Work with Excel](https://learn.microsoft.com/en-us/graph/api/resources/excel?view=graph-rest-1.0) |
| 세션 | `POST .../workbook/createSession` + `workbook-session-id` 헤더 | [Manage sessions](https://learn.microsoft.com/en-us/graph/excel-manage-sessions), [Excel overview](https://learn.microsoft.com/en-us/graph/api/resources/excel?view=graph-rest-1.0) |
| 시트·범위 | worksheets / `range(address='A1:B2')` / usedRange | [workbookWorksheet](https://learn.microsoft.com/en-us/graph/api/resources/workbookworksheet?view=graph-rest-1.0) |
| 테이블 행 추가 | `POST .../workbook/tables/{id\|name}/rows` | [Create table row](https://learn.microsoft.com/en-us/graph/api/table-post-rows?view=graph-rest-1.0) |

제약:

- **`.xls` 미지원**, OneDrive Consumer 미지원 — 비즈니스 플랫폼만 ([Excel overview](https://learn.microsoft.com/en-us/graph/api/resources/excel?view=graph-rest-1.0)).
- 스코프: 읽기 `Files.Read`, 쓰기 `Files.ReadWrite` ([동일](https://learn.microsoft.com/en-us/graph/api/resources/excel?view=graph-rest-1.0)).
- 복잡한 수식·보호시트·거대 usedRange는 `unsupportedWorkbook` / `accessConflict` 등 ([Error handling](https://learn.microsoft.com/en-us/graph/workbook-error-handling)).
- 동일 워크북에 **병렬 쓰기 비권장** ([Best practices](https://learn.microsoft.com/en-us/graph/workbook-best-practice)).

### 3. Outlook 초안(HTML) + .xlsx 또는 PDF 첨부가 가능한가?

**가능. 발송은 별도 API — v1에서는 호출하지 않음.**

| 기능 | API | 근거 |
|------|-----|------|
| 초안 생성 | `POST /me/messages` (기본 Drafts). `body.contentType = "HTML"` | [Create message](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0), [Create/send messages](https://learn.microsoft.com/en-us/graph/outlook-create-send-messages) |
| 소용량 첨부 (&lt; 3MB) | `POST .../messages/{id}/attachments` (`fileAttachment`) | [Add attachment](https://learn.microsoft.com/en-us/graph/api/message-post-attachments?view=graph-rest-1.0), [Large attachments](https://learn.microsoft.com/en-us/graph/outlook-large-attachments) |
| 대용량 (3–150MB) | `.../attachments/createUploadSession` 후 청크 PUT | [createUploadSession](https://learn.microsoft.com/en-us/graph/api/attachment-createuploadsession?view=graph-rest-1.0) |
| .xlsx 원본 다운로드 | `GET .../items/{id}/content` | [Download content](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0) |
| PDF 변환 다운로드 | `GET .../content?format=pdf` — 소스에 `xlsx`/`xlsm`/`xls` 포함 | [Convert format](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content-format?view=graph-rest-1.0) |
| 발송 | `message-send` / `sendMail` — **제품 안전 규칙상 사용 안 함** | [05-outlook](./05-outlook.md) |

권한(초안): 위임 `Mail.ReadWrite` ([Create message](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0)).

### 4. 권한 (위임 vs 앱)

| 목적 | 최소(위임) | 비고 / 상위 |
|------|------------|-------------|
| 채널 Files 루트 | `Files.Read.All` (문서상 least) | [filesFolder](https://learn.microsoft.com/en-us/graph/api/channel-get-filesfolder?view=graph-rest-1.0) — `Sites.Read.All` 등도 higher |
| 경로로 파일 메타/다운로드 | `Files.Read` / `Sites.Read.All` | [driveItem-get](https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0) |
| Excel 읽기 | `Files.Read` | [Excel overview](https://learn.microsoft.com/en-us/graph/api/resources/excel?view=graph-rest-1.0) |
| Excel 쓰기(행 추가) | `Files.ReadWrite` | [table-post-rows](https://learn.microsoft.com/en-us/graph/api/table-post-rows?view=graph-rest-1.0) |
| 조직 공유 링크 | `Files.ReadWrite` (위임) | [createLink](https://learn.microsoft.com/en-us/graph/api/driveitem-createlink?view=graph-rest-1.0) |
| Outlook 초안 | `Mail.ReadWrite` | [user-post-messages](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0) |
| 앱 전용(무인) | `Files.ReadWrite.All` / `Sites.ReadWrite.All` + `Mail.ReadWrite` | 관리자 동의·사서함 정책 필요. **초안 UX는 위임(`/me`) 권장** ([05-outlook](./05-outlook.md)) |

**권장 권한 세트(위임, v1):**

```text
Files.ReadWrite          # Excel 읽기(+선택 쓰기), createLink (스파이크와 동일)
Sites.Read.All           # 팀 사이트/채널 라이브러리 안정적 읽기 (동의 필요할 수 있음)
Mail.ReadWrite           # Outlook 초안만 (Mail.Send 넣지 않음)
```

테넌트 정책상 채널 사이트에 `Files.ReadWrite`(개인 OneDrive용)만으로는 부족할 수 있음 → 실제 Graph 호출로 확인 후 `Files.Read.All` / `Sites.Read.All` 동의.

사이트 범위를 좁히려면 `Sites.Selected` 패턴도 가능([Selected permissions](https://learn.microsoft.com/en-us/graph/permissions-selected-overview)) — 초기 스파이크보다는 운영 단계에서.

### 5. 실용 한계

| 주제 | 내용 | 근거 |
|------|------|------|
| 경로 인코딩 | `#` → `%23`, 공백 → `%20`, 한글은 UTF-8 percent-encode. **세그먼트별** 인코딩; URL 전체를 한 번에 encode 금지 | [Addressing driveItems](https://learn.microsoft.com/en-us/graph/onedrive-addressing-driveitems) |
| 폴더명 `#1` | OneDrive for Business에서 `#`는 예약 문자이나 **기존 폴더명에 이미 쓰인 경우** 접근 시 반드시 `%23`으로 주소 지정 | 동일 + reserved chars 표 |
| 한글 폴더 | `Installation 레포트_백업용` — RFC 3986 UTF-8 encoding으로 지원 | 동일 |
| 메일 첨부 크기 | &lt;3MB 단일 POST; 3–150MB upload session | [Large attachments](https://learn.microsoft.com/en-us/graph/outlook-large-attachments) |
| Excel 동시편집 | 다른 클라이언트가 잠그면 `accessConflict` / `invalidSessionAccessConflict` — 충돌 해소 전 재시도 비권장 | [Workbook error handling](https://learn.microsoft.com/en-us/graph/workbook-error-handling) |
| Excel 복잡도 | 파일 크기만이 아니라 셀·수식 밀도로 `unsupportedWorkbook` 가능. 세션 + 작은 range 권장 | [Best practices](https://learn.microsoft.com/en-us/graph/workbook-best-practice), [Excel overview](https://learn.microsoft.com/en-us/graph/api/resources/excel?view=graph-rest-1.0) |
| PDF 변환 | `xlsx`→PDF 지원되나 대용량/복잡 파일은 Office 변환 서비스에서 실패할 수 있음 | [format=pdf](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content-format?view=graph-rest-1.0) |
| 채널 프로비저닝 | Files 탭이 한 번도 안 열리면 `filesFolder` 404 가능(실무에서 흔함) | Q&A 다수; 문서상 private channel 동작 주의 ([filesFolder](https://learn.microsoft.com/en-us/graph/api/channel-get-filesfolder?view=graph-rest-1.0)) |

---

## 아키텍처 옵션 비교

| 옵션 | 설명 | 실현성 | 권장 |
|------|------|--------|------|
| **(A)** Excel을 초안에 첨부 | Graph로 `.xlsx` 다운로드 → 초안 `fileAttachment` (또는 `format=pdf`) | 높음 | **v1 선택 첨부** (용량·고객 노출 확인 후) |
| **(B)** 본문 요약 + Teams 파일 링크 | Excel에서 요약 셀 읽기(또는 SF WO 필드) → HTML 본문 + `webUrl` / `createLink` | 높음 | **v1 기본** |
| **(C)** SF WO → Excel 행 append | `POST .../tables/.../rows` (또는 range update) | 중간 — 테이블/보호시트/동시편집에 취약 | **v1.5+**, Human Gate + 엔지니어가 Excel 안 연 상태 |
| **(D)** SF Activities에 SharePoint URL | WO Activities에 파일 `webUrl` 이어쓰기 | 높음 (SF REST) | **v1 필수 회수** |

**권장 조합:** **B + D** (+ 필요 시 A). C는 시트에 Excel Table이 있고 컬럼이 안정적일 때만.

```text
[옵트인 Case + 컷오프 OK]
  → Asset/Site로 폴더 해석 → 리포트 종류 선택
  → Graph: driveItem 조회 (webUrl, size, lastModified)
  → (선택) Excel session: 요약 범위 읽기
  → Human Gate: To/Cc/Subject/Body/첨부 여부 확인
  → Graph: Outlook 초안 (HTML) ± 첨부
  → SF: Activities에 "Excel: {webUrl}" + "Outlook draft: {id/webLink}"
  → 사용자: Outlook에서 수정 후 직접 발송
```

---

## 권장 워크플로

### Installation vs Field Service 선택

| 신호 | 선택 | 파일 패턴 |
|------|------|-----------|
| WO/Case가 **설치** 단계 (설치 완료 전·설치 리포트 작성) | Installation Report | `Installation 레포트_백업용/` 아래 `[Installation Report] ...xlsx` |
| Asset이 이미 가동·**유지보수/출장** Technical Support | Field Service Report | 자산 폴더 루트(또는 합의된 하위) `[DFS2] *Field Service Report*.xlsx` |
| 애매함 | Human Gate에서 라디오 선택 | 둘 다 후보로 나열 |

Tool 규칙(초안):

1. SF Asset / Site / Serial(또는 폴더키 커스텀 필드)로 폴더 후보 생성.
2. Installation이면 백업 폴더 우선 검색; Field Service면 자산 폴더에서 `Field Service Report` 파일명 매칭(최신 `rev` / `lastModifiedDateTime`).
3. 0건·복수 건 → 사용자 선택. 추측으로 덮어쓰지 않음.

### SF Asset / SID / Site → 폴더명 매핑

실무 폴더 예: `A6_NX-TSH2326 #1`

| SF 쪽(가정) | 폴더 토큰 | 비고 |
|-------------|-----------|------|
| Site / Account 코드 | `SDC` (상위 `.../DFS2/SDC/`) | 경로 세그먼트 |
| Tool / Model | `A6` + `NX-TSH2326` | 하이픈·언더스코어 규칙 확인 필요 |
| Unit / # | `#1` | Graph path에서는 `%231` |
| SID / Serial | 파일명·시트 내부와 교차검증 | 폴더명만으로 부족하면 사용자 확인 |

**구현:** 설정 가능한 매핑식(예: `{Model}_{Serial} #{Unit}`) + 실패 시 폴더 검색 UI. 첫 성공 시 `driveItem.id`를 Case/WO 커스텀 필드 또는 Activities에 캐시해 이후 path fragile 문제 완화([ID-based addressing](https://learn.microsoft.com/en-us/graph/onedrive-addressing-driveitems)).

### Tool이 자동화할 것 vs 사람이 할 것

| Tool | 사람 |
|------|------|
| 옵트인·컷오프 검사 | Case 선택 |
| 폴더/파일 후보 조회·링크 생성 | 최종 파일 확정(복수 시) |
| 메일 초안 HTML (기존 형식 템플릿) | To/Cc·본문 톤·고객 노출 문장 |
| (선택) xlsx/PDF 첨부 | 첨부 여부·용량 |
| SF Activities에 URL/draft id 회수 | Outlook에서 발송 |
| (후속) Excel 행 제안 또는 append | Excel 이력의 최종 책임·동시편집 회피 |

### 사용자에게 추가로 필요한 것

- [x] 샘플 메일 2통 (Installation 회신 / Field 작업보고) — 아래 §샘플 분석
- [x] 샘플 xlsx 2종 (Installation / FSR 2026) — 아래 §샘플 분석
- [x] 폴더 규칙 예시: `…/DFS2/SDC/{Area}_{Model} #{Unit}/` (A1…A6)
- [ ] DFS2 site/로컬 동기화 경로 (Azure 없을 때)
- [ ] Entra 관리자 동의 — **현실적으로 어려움 → §Azure 없이** 경로 우선
- [ ] 고객 메일: 기본 **캡처/이미지** (xlsx 붙여넣기 깨짐) vs PDF 변환 정책
- [ ] SF Asset↔폴더키 필드 유무 (없으면 `config` 매핑)

---

## 샘플 분석 (2026-08-07 제출분)

### 메일 형식

**Field 작업보고** (`[작업보고] SDC A6 / NX-TSH2326 / Tip 교체`):

```text
제목: [작업보고] {Site Area} / {Model} / {짧은 작업명}
To: 직속(예: 노승범)  /  Cc: IDB (및 필요 시 배포 리스트)
본문:
  안녕하세요 {이름}입니다.
  {고객} {Area} {Model} 장비 작업 보고드립니다.
  작업날짜 : YYYY-MM-DD
  작업인원 : {이름}
  작업내용
  [이미지: 엑셀 해당 일자 시트 캡처]
  감사합니다 / 서명
```

실무상 **엑셀을 Outlook에 붙여넣으면 양식이 깨져** 캡처(PNG)를 본문에 넣는 패턴. Installation 회신 메일은 캡처가 수십 장·HTML 수 MB 규모.

**Installation 작업보고** 제목 예:
`[SDC A3] NX-TSH 1518 Installation 작업 보고 (SID : D25006-200325)`  
Cc에 IDB, SRDM, ISW, ME4 등 광범위 배포.

### Excel 구조

| 종류 | 고정 시트 | 이력 시트 | 비고 |
|------|-----------|-----------|------|
| Installation Report | HW history, SW Version history, 이슈 List, Gantt | `YYYY.MM.DD` 일자별 **시트 다수**(100+) | ~11MB, 이미지/도형 많음 → Graph Excel API·붙여넣기 모두 취약 |
| Field Service Report | SW Version history, 출장준비 Check 등 | 출장일 `YYYY.MM.DD` 시트 | Installation보다 가벼움, 동일 “일자 시트” 패턴 |

Tool이 엑셀 **전체 자동 작성**을 목표로 하면 실패 확률이 높다.  
**일자 시트 1장 캡처/PNG 생성 + 메일 골격 채우기**가 현재 수작업과 가장 잘 맞음.

### 폴더 규칙 (관찰)

```text
Documents/General/DFS2/{고객코드}/{Area}_{Model} #{Unit}/
  ├── [DFS2] {year} Field Service Report_{고객} {Area}_{Model}_revNN.xlsx
  └── Installation 레포트_백업용/
        └── [Installation Report] {고객} {Area} {Model} #{Unit}.xlsx
```

예: `SDC/A6_NX-TSH2326 #1`. 설비마다 Installation → 이후 FSR로 **전환**하며 동시에 쓰지 않음.

### Installation → Field Service 전환 (제안)

**권장: 설비당 “활성 리포트 모드”를 Tool 설정에 한 번만 기록** (섞어 쓰지 않는 실무와 일치).

```yaml
# config/asset_reports.yaml (개념)
assets:
  "A6_NX-TSH2326 #1":
    customer: SDC
    mode: field_service   # installation | field_service
    switched_on: 2026-01-01   # 선택
```

| 규칙 | 동작 |
|------|------|
| `mode: installation` 또는 FSR 파일 없음 | Installation 엑셀만 대상 |
| `mode: field_service` 또는 FSR 파일 존재 | FSR만 대상 |
| 전환 시점 | UI에서 “이 설비 FSR로 전환” 한 번 → 이후 기본값 FSR (Installation은 백업 폴더 링크로만) |
| 애매 | Human Gate에서 라디오 (기본값은 위 규칙) |

자동 추측만으로 전환하지 않음 — 오탐 시 잘못된 이력 파일에 쌓임.

---

## Azure 관리자 동의가 안 날 때 (권장 경로)

Graph(`Files.*` / `Sites.*` / `Mail.*`) 없이 **노트북 로컬**로 동일 가치를 낼 수 있다.

| 방식 | 내용 | Azure | 비고 |
|------|------|-------|------|
| **L1 로컬 동기화** | Teams Files → “OneDrive에 바로 가기” 또는 동기화 폴더. Tool은 `C:\Users\…\DFS2\SDC\…` 경로만 사용 | 불필요 | **현재 미사용**(업무 OneDrive 브라우저만). 가능하면 DFS2만 선택 동기화 권장 |
| **L2 Outlook COM** | `win32com`으로 로컬 Outlook에 HTML 초안 생성·인라인 이미지 첨부 | 불필요 | 사내 PC에 Outlook 설치 전제 |
| **L3 UI만** | Streamlit에서 본문·제목 미리보기 → `.eml` 저장 또는 클립보드. 사용자는 Outlook에 붙여넣기 | 불필요 | COM 실패 시 폴백 |
| **L4 시트→PNG** | 활성 일자 시트를 Excel/COM 또는 렌더로 PNG → 메일 `작업내용`에 삽입 | 불필요 | **붙여넣기 깨짐 문제의 정석 해결** |
| Graph (보류) | 동의 나면 원격 경로·공유 링크로 업그레이드 | 필요 | 지금은 가정하지 않음 |

**권장 v1 (Azure 없음 + OneDrive 미동기화):** **다운로드 드롭 + L4 + L2/L3**.

브라우저만 쓰는 경우 Graph 없이는 Teams 파일을 Tool이 직접 열 수 없다. 현실 경로:

```text
(사람) Teams 브라우저에서 해당 xlsx 다운로드 또는 캡처 PNG 저장
  → Tool UI에 파일/이미지 드롭
SF Technical Support WO 선택
  → asset_reports.yaml 로 mode·제목 토큰(Site/Model) 채움
  → (선택) 받은 xlsx에서 일자 시트 → PNG (L4)
  → 또는 사용자가 이미 만든 캡처 PNG를 그대로 본문에 사용
  → Tool: 기존 형식 HTML 메일 초안 (Outlook COM 또는 .eml)
  → SF Activities: 파일명 + 작업일 + (선택) 사용자가 붙여넣은 Teams 링크
```

중기 개선(관리자 동의 없이 가능한 쪽): DFS2 폴더만 **OneDrive 바로 가기 + 선택 동기화** → L1로 승격. 전사 Azure 앱 승인과는 별개(개인/동기화 설정).

---

## 구현 우선순위 (이 연동만, Azure 보류 전제)

| 단계 | 내용 | 의존 |
|------|------|------|
| P2-local-0 | `asset_reports` 매핑 + 로컬 DFS2 루트 경로 설정 | 동기화 폴더 |
| P2-local-1 | 메일 HTML 템플릿 (샘플 형식) + PNG 자리 | 샘플 메일 |
| P2-local-2 | 일자 시트 → PNG + Outlook COM/`.eml` 초안 | Outlook 설치 |
| P2-local-3 | SF Activities 회수 (파일명·날짜) | SF 어댑터 |
| P3 | (선택) 빈 일자 시트 복제 / SW history 한 줄 제안 | 양식 통일 논의 |
| 보류 | Graph filesFolder / Mail.ReadWrite | Entra 동의 |

기존 [08](./08-priority-recommendation.md) P2 Outlook을 **로컬 COM·동기화 경로**로 재정의하는 것이 현재 제약에 맞다.

---

## 일자 시트 → Case Activity → WO 첨부 (가능 여부, 2026-08-07)

전제: DFS2 **선택 동기화(L1)** 후 로컬 xlsx 편집. SF는 기존 CLI 토큰(`sf org`) — Azure Graph와 무관.

### 엑셀에서 Case ID

FSR 일자 시트 고정 위치(샘플 `2026.07.09`):

| 셀 | 의미 | 예 |
|----|------|-----|
| `R9` | 라벨 `CRM Case ID` | |
| `T9` | Case Number | `00197302` |
| `V5` | Park FSEs Name (출장자) | `노승범` / `이동현` |
| `V4` | Report Date | 시트 일자 |

Installation 일자 시트도 `CRM Case ID` 라벨이 있음(행 위치는 `R7` 근처 — 템플릿 복사 시 좌표 설정화).

시트당 Case ID 칸은 **하나**. 여러 Case에 동시에 남기려면 Tool UI에서 **복수 선택**(엑셀 값 prefill + SF 검색 추가)이 맞음. 엑셀 `T9`에 쉼표 구분 복수 기입도 파싱 가능하나, UI 선택이 안전.

### Salesforce API (org `parksystems` Describe 확인)

| 동작 | 가능 | 방법 |
|------|------|------|
| Case Activity 한 줄 이어쓰기 | **가능** | `Case.Activities__c` (label: Activities, textarea 32K, updateable). 형식 예: `2026-07-07 [이동현] Tip 교체` |
| Work Order 생성 | **가능** | `WorkOrder` createable. Record Type **`Technical Service`** (`0120o000001lQJ5AAM`) — 화면명 Technical Support와 API명 상이 |
| WO에 파일 첨부 | **가능** | `ContentVersion` createable + `FirstPublishLocationId = WorkOrder.Id` ([Insert blob](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/dome_sobject_insert_update_blob.htm)) |
| “해당 날짜 시트만” 첨부 | **가능(가공 후)** | SF는 워크북 일부 시트를 직접 이해하지 않음 → Tool이 **일자 시트만 들어 있는 임시 xlsx**(또는 PDF/PNG)를 만들어 업로드 |

기존 PMS 경로는 WO `VOC_Activities__c`를 씀. 이번 출장 요약은 요청대로 **Case `Activities__c`**. WO 쪽에는 파일 + (선택) Subject/설명.

### 권장 플로우 (동기화 이후)

```text
1. (최초) Teams DFS2 → OneDrive 바로 가기 + 선택 동기화
2. Tool: 설비 폴더·활성 리포트(FSR/Installation) 선택
3. Tool: 오늘 날짜 시트 없으면 최근 일자 시트 서식 복사해 `YYYY.MM.DD` 생성
4. (사람) 시트에 내용 작성 · CRM Case ID(T9) 기입
5. Tool: T9 및 SF 검색으로 Case 후보 → 사용자 복수 선택 가능
6. Tool: 작업 요약 입력 → 각 Case.Activities__c 에
         "yyyy-mm-dd [출장자] 요약" 이어쓰기 (Human Gate)
7. Tool: Technical Service WO 생성(CaseId 연결) →
         일자 시트만 추출한 xlsx(또는 PDF)를 ContentVersion으로 WO에 첨부
8. (후속) Outlook 초안은 같은 PNG/요약을 재사용
```

### 제약·주의

| 항목 | 내용 |
|------|------|
| 시트 복사 품질 | openpyxl은 도형/차트/일부 서식 누락 가능. 깨지면 **Excel COM**으로 시트 복사 권장 |
| 파일 크기 | 전체 Installation xlsx(~11MB)를 WO에 올리지 말고 **단일 시트 export** |
| Case 필드 | `HQ_Comment__c`도 있으나 요청 형식에는 `Activities__c`가 맞음 — UI에서 필드 확인 후 고정 |
| 권한 | 사용자(또는 통합 유저)에게 Case 편집, WO 생성, Files 업로드 FLS/권한 필요(현재 sf 로그인 사용자로 Describe상 createable) |
| 안전 | 옵트인·컷오프·Human Gate 유지. Case Activity는 **이어쓰기만** |

### DFS2 선택 동기화 (사용자 작업)

1. Teams → DFS2 → 파일 → `DFS2` 폴더(또는 `SDC`)에서 **OneDrive에 바로 가기 추가**  
2. OneDrive 설정 → **계정 → 폴더 선택**에서 해당 바로 가기만 동기화  
3. Tool 설정에 로컬 루트 ( ethan PC 확인값 ):  
   `C:\Users\shp09\OneDrive - Park Systems\DFS2 - General\DFS2`  
   → 그 아래 `SDC\A6_NX-TSH2326 #1\` 등 설비 폴더

---

## 위험

| 위험 | 완화 |
|------|------|
| 잘못된 자산 폴더/리포트 | 후보 나열 + Human Gate |
| Excel 잠금·병합 충돌 | 쓰기 최소화; 충돌 시 중단·안내 ([error handling](https://learn.microsoft.com/en-us/graph/workbook-error-handling)) |
| 고객에게 내부 이력 xlsx 유출 | 기본은 링크(조직 scope) 또는 PDF; 첨부 옵트인 |
| 경로 `#`/한글 깨짐 | 세그먼트 인코딩 유틸 + itemId 캐시 |
| 권한 과다 | 위임 + 최소 스코프; `Mail.Send` 미요청 |
| 과거 Case 오염 | 컷오프·옵트인 ([00-overview](./00-overview.md)) |

---

## 관련 문서

- [00-overview.md](./00-overview.md) — 안전 규칙
- [04-teams.md](./04-teams.md) — Teams/Excel 일반 주의
- [05-outlook.md](./05-outlook.md) — Technical Support → 초안
- [01-salesforce.md](./01-salesforce.md) — Activities 회수
- 스파이크: `_onedrive_spike.py` (동일 Client ID, `Files.ReadWrite`)

## 주요 공식 출처 (Learn)

- https://learn.microsoft.com/en-us/graph/api/channel-get-filesfolder?view=graph-rest-1.0  
- https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0  
- https://learn.microsoft.com/en-us/graph/onedrive-addressing-driveitems  
- https://learn.microsoft.com/en-us/graph/api/resources/excel?view=graph-rest-1.0  
- https://learn.microsoft.com/en-us/graph/excel-manage-sessions  
- https://learn.microsoft.com/en-us/graph/workbook-best-practice  
- https://learn.microsoft.com/en-us/graph/workbook-error-handling  
- https://learn.microsoft.com/en-us/graph/api/table-post-rows?view=graph-rest-1.0  
- https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0  
- https://learn.microsoft.com/en-us/graph/outlook-create-send-messages  
- https://learn.microsoft.com/en-us/graph/outlook-large-attachments  
- https://learn.microsoft.com/en-us/graph/api/driveitem-get-content-format?view=graph-rest-1.0  
- https://learn.microsoft.com/en-us/graph/api/driveitem-createlink?view=graph-rest-1.0  
- https://learn.microsoft.com/en-us/microsoftteams/platform/build-apps-for-shared-private-channels  
