# Priority Recommendation

Build order for Approach C. Does **not** start coding until the design spec is approved and an implementation plan is written.

## Recommended order

| Priority | Item | Why |
|----------|------|-----|
| P0 | Opt-in Case selector + cutoff guard + job log | Safety; enables everything else without touching history |
| P0 | Salesforce adapter (read Case/WO, append Activities) | Hub |
| P1 | PMS connector + VOC/SW route | Clearest end-to-end value; API likely ready |
| P1 | Human Gate (minimal UI) | Required before any external create |
| P2 | Outlook draft for Technical Support | High daily time save; Graph well documented |
| P3 | Workful / Dataverse | Needs schema discovery |
| P3 | Teams OBQ/QI notify or list | Depends on artifact type confirmation |
| P4 | Release Notes | Blocked on API ownership; separate mail loop |
| P5 | Background triggers (CDC/poll) | Only after manual Run is solid |

## Explicit non-goals for early milestones

- Migrating or rewriting old Cases/WOs
- Outlook auto-send
- Unattended posts without Human Gate
- Full AI auto-routing without matrix match

## Dependency sketch

```text
P0 guards + SF read/writeback
    ├── P1 PMS + Gate
    ├── P2 Outlook drafts
    ├── P3 Workful / Teams (parallel after schema known)
    └── P4 Release Notes (parallel once API exists)
```

## Success for first milestone

User selects a **new** test Case → approves → PMS issue created → URL on WO Activities → **zero** writes to pre-cutoff Cases.
