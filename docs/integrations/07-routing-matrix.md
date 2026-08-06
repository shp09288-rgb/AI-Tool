# Routing Matrix (draft)

Editable source of truth for the Router. PPT guideline is **legacy**; update this file (and runtime YAML) when practice changes.

## Safety preconditions (all routes)

1. Case `CreatedDate` ≥ `automation_enabled_after`
2. Case is **user-selected** (opt-in)
3. Human Gate approved (except dry-run)

## Matrix

| when.recordType | when.department | when.other | targets[] | writeback format |
|-----------------|-----------------|------------|-----------|------------------|
| VOC | SW | bug / feature / inquiry | `pms` | `PMS – {url}` |
| VOC | (TBD) | SRD-style request | `workful` | `Work Pool – {등록번호}` |
| VOC / related | QI or MC request | OBQ/QI | `teams_obq` | `OBQ, QI – {link}` |
| (tracking) | — | Issue & VOC list | `teams_voc` | 접수번호 / link |
| Technical Support | — | 출장/현장 대응 | `outlook` | optional Message-ID / draft note |
| — | — | SW version announcement mail | `release_notes` | RN URL (optional SF note) |
| VOC | HW | TBD | _(empty — suggest only)_ | — |
| VOC | Manual | TBD | _(empty)_ | — |
| VOC | Sales | TBD | _(empty)_ | — |
| VOC | TS | TBD | _(empty)_ | — |
| VOC | P/L Spec 등 | TBD | _(empty)_ | — |

## Relevant Department picklist (observed)

`--None--`, `QI`, `SW`, `HW`, `Manual`, `P/L, Spec 등`, `Sales`, `TS`

## Example runtime config

```yaml
automation_enabled_after: "2026-12-01T00:00:00+09:00"  # set at deploy
opt_in: tool_side  # or salesforce_field

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

## Ambiguous cases

If Record Type / Department do not match any route:

- Do **not** auto-post.
- Draft AI may **propose** a target; user confirms in Human Gate or updates this matrix.

## Change log

| Date | Change |
|------|--------|
| 2026-08-06 | Initial draft from brainstorming + CRM PPT + current URLs |
