# 출장 보고 → Tool 메일 편집·전송 Design Spec

**Date:** 2026-08-07  
**Status:** Implemented (2026-08-07); existing-WO skip + mail unlock added  
**Depends on:** 출장 보고 SF 등록(Case Activity + Technical Service WO), [09-teams-excel-outlook-feasibility](../../integrations/09-teams-excel-outlook-feasibility.md)

## 1. Goal

출장 보고 등록이 끝난 뒤, Field 작업보고 형식의 **메일 초안을 Tool이 작성**하고, Streamlit **미리보기/편집기**에서 짧게 수정한 다음 **Tool에서 바로 전송**한다.  
발송 계정(From)은 **`ethan.lee@parksystems.com`**.

> 가능 여부: **가능.** Azure Graph 없이도 로컬 Outlook COM으로 `Send()` 호출하면 된다.  
> 전제: 이 PC의 Outlook에 `ethan.lee@parksystems.com` 프로필/계정이 로그인되어 있어야 From이 그 주소로 나간다.

## 2. Trigger / UX

```text
SF 등록 성공(또는 partial)
  → 「메일 초안 만들기」
  → Tool이 제목·본문·PNG 초안 생성
  → 편집 화면:
        To / Cc (비어 있음, 사용자가 입력)
        Bcc (ethan.lee@parksystems.com 고정·읽기전용 또는 항상 재주입)
        Subject (편집 가능)
        Body (텍스트/간단 HTML 편집 + PNG 미리보기)
  → 「전송」확인 다이얼로그
  → Outlook COM으로 발송
  → 성공/실패 메시지
```

- Outlook 창을 열어 수정·발송하는 UX는 **쓰지 않는다** (백엔드로만 COM 사용).
- 전송 전 To가 비어 있으면 차단.
- 전송 버튼은 한 번 더 확인(실수 발송 방지).

## 3. Recipients / From

| 필드 | 정책 |
|------|------|
| **From** | `ethan.lee@parksystems.com` (Outlook `SendUsingAccount`로 해당 계정 지정; 계정이 없으면 명확한 오류) |
| To | 초안 시 비움 → **전송 전 사용자 입력 필수** |
| Cc | 초안 시 비움 → 편집기에서 입력 가능 |
| **Bcc** | **항상** `ethan.lee@parksystems.com` (편집기에서 제거해도 전송 시 다시 넣음) |

## 4. Subject

```text
[작업보고] {Site Area} / {Model} / {YYYY-MM-DD} 작업 보고
```

- `Site Area` / `Model`: 설비 폴더명에서 파싱 (예: `A6_NX-TSH2326 #1` + 고객 `SDC` → `SDC A6` / `NX-TSH2326`).
- 날짜는 엑셀 Report date(작업일).

## 5. Body (초안 순서 고정, 편집기에서 수정 가능)

```text
안녕하세요
{출장자}입니다.

{고객사표시명} {캠퍼스/Area} {Model} 작업 보고 드립니다.

작업날짜 : YYYY-MM-DD
인원 : {출장자}
Case number : {CaseNumber, …}
Work order number : {WO번호, …}

작업내용
[인라인 PNG]
(서명 블록 — 파란 10pt)
감사합니다
이동현 드림
Service Engineer I 대리 / DFS2 / 국내사업부
Park Systems Corp. + 주소·Tel·Web
```

규칙:

- 본문: 맑은 고딕 11pt. 서명: `#002060` 10pt.
- 고객사 표시: `SDC`→삼성디스플레이 + Area(예: A6). 슬래시 없이 공백 구분.
- Case / WO 번호는 Salesforce Lightning 링크(쉼표 구분).
- 편집기: Quill(볼드·글자색). PNG는 `작업내용` 아래 전송 시 인라인.

## 6. Attachments / inline

| 항목 | 필수 | 내용 |
|------|------|------|
| 인라인 PNG | 예 | `render_sheet_preview_png` crop 범위, 전송 시 HTML에 임베드 |
| 일자 시트 xlsx | 선택(기본 ON) | crop xlsx 파일 첨부 |

## 7. Technical approach

- **Outlook COM** (`win32com`): MailItem 생성 → From 계정 지정 → To/Cc/Bcc/Subject/HTMLBody/첨부 → **`Send()`**.
- Graph/`Mail.Send` 앱 권한 **불필요** (로컬 Outlook이 이미 로그인된 사서함으로 보냄).
- 모듈:
  - `field_report/mail_template.py` — 제목·본문 초안(순수 함수).
  - `field_report/outlook_com.py` — 계정 선택 + 인라인 PNG + `Send()` (단위 테스트는 mock).
  - `webui` — 초안 세션 상태, 편집 폼, 전송 버튼.
- Outlook이 꺼져 있으면 COM이 기동. 계정 없/프로필 불일치 시 전송 중단 + 안내.

## 8. Data inputs

- 고객 / Area / Model / Unit
- 작업일, 출장자(FSE)
- Case Number·Work Order Number 목록
- 일자 시트 PNG·crop xlsx 경로

## 9. Out of scope (v1)

- Graph Mail API
- Outlook 창을 띄워 수정·발송
- 풍부한 WYSIWYG(표/글꼴 팔레트)
- Installation 전용 자동 Cc 배포 리스트
- 예약 발송 / 대량 일괄 발송

## 10. Tests

- 템플릿: 메타 한 줄 Case/WO 쉼표 표기.
- 전송 페이로드 조립: Bcc 강제 주입, To 없으면 거부, From 주소 상수.
- COM `Send`는 mock.

## 11. Success criteria

1. 등록 후 Tool에서 초안이 편집 화면에 뜬다.
2. To/Cc는 비어 있고, Bcc·From은 `ethan.lee@parksystems.com`.
3. 본문·PNG 미리보기를 고친 뒤 「전송」하면 실제 메일이 나간다.
4. Outlook을 따로 열어 수정할 필요 없다.

## 12. Risks

- PC Outlook에 Ethan 계정이 없으면 From 지정 실패 → 명확한 오류 메시지.
- Streamlit 새로고침 시 편집 중 초안 유실 → `st.session_state`에 보관, 전송 전 경고.
- 실수 발송 → 확인 다이얼로그 + To 필수.
