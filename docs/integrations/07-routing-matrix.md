# 라우팅 매트릭스 (초안)

라우터의 수정 가능한 기준표. PPT 지침은 **구버전**이므로, 실무가 바뀌면 이 파일(과 런타임 YAML)을 갱신한다.

## 모든 라우트 공통 전제

1. Case `CreatedDate` ≥ `automation_enabled_after`
2. Case가 **사용자 선택(옵트인)** 됨
3. Human Gate 승인(드라이런 제외)

## 매트릭스

| when.recordType | when.department | when.other | targets[] | 회수 형식 |
|-----------------|-----------------|------------|-----------|-----------|
| VOC | SW | 버그 / 기능 / 문의 | `pms` | `PMS – {url}` |
| VOC | (미정) | SRD 성격 요청 | `workful` | `Work Pool – {등록번호}` |
| VOC / 관련 | QI 또는 MC 요청 | OBQ/QI | `teams_obq` | `OBQ, QI – {link}` |
| (추적) | — | Issue & VOC 목록 | `teams_voc` | 접수번호 / 링크 |
| Technical Support | — | 출장/현장 대응 | `outlook` | Message-ID / 초안 메모(선택) |
| — | — | SW 버전 안내 메일 | `release_notes` | RN URL (SF 메모는 선택) |
| VOC | HW | 미정 | _(비움 — 제안만)_ | — |
| VOC | Manual | 미정 | _(비움)_ | — |
| VOC | Sales | 미정 | _(비움)_ | — |
| VOC | TS | 미정 | _(비움)_ | — |
| VOC | P/L Spec 등 | 미정 | _(비움)_ | — |

## Relevant Department 선택지 (관찰)

`--None--`, `QI`, `SW`, `HW`, `Manual`, `P/L, Spec 등`, `Sales`, `TS`

## 런타임 설정 예시

```yaml
automation_enabled_after: "2026-12-01T00:00:00+09:00"  # 배포 시점에 설정
opt_in: tool_side  # 또는 salesforce_field

routes:
  - id: voc-sw-pms
    when:
      recordType: VOC
      department: SW
    targets: [pms]
    require_human_gate: true

  - id: technical-support-mail
    when:
      recordType: Technical_Support
    targets: [outlook]
    outlook:
      mode: draft_only
      attach: wo_summary
    require_human_gate: true

  - id: release-notes-from-mail
    when:
      source: inbound_mail
      category: sw_version
    targets: [release_notes]
    require_human_gate: true
```

## 애매한 경우

Record Type / Department가 어떤 라우트에도 안 맞으면:

- **자동 게시하지 않는다.**
- Draft AI가 대상을 **제안**할 수 있고, 사용자가 Human Gate에서 확정하거나 이 매트릭스를 고친다.

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-08-06 | 브레인스토밍 + CRM PPT + 현재 URL 기준 초안 |
| 2026-08-06 | 문서 언어를 한국어로 통일 |
