# Integrations Overview

Salesforce-centric AI work automation. Approach **C (hybrid)**: configurable routing table + AI drafts + human approval gate.

## Hub model

```text
Case (user opt-in, post-deploy only)
  → Work Order
  → Router (Record Type + Relevant Department + work kind)
  → Connector(s)
  → Writeback to Work Order Activities
```

## Safety (applies to all connectors)

- Do **not** mutate Cases/Work Orders created before deployment cutoff.
- Automation runs only on Cases the user **explicitly selects**.
- External create / mail send only after Human Gate (mail: draft-only by default).

## Current tool URLs (source of truth vs PPT)

| Tool | Current entry | Notes |
|------|---------------|-------|
| Salesforce | `parksystems.lightning.force.com` | Hub |
| Workful | PowerApps play URL (tenant `7634c4dc-…`) | PPT said “Work Pool (Teams)” — current UI is PowerApps |
| Release Notes | `release-note-web-db-tool.vercel.app/dashboard` | Separate from VOC loop |
| PMS | `pms.parksystems.com` | Redmine-like issue tracker |
| Teams | Org channels (Work Pool / OBQ·QI / Issue&VOC) | Graph |
| Outlook | Exchange Online mailbox | Technical Support WO → draft mail |

Legacy reference: `reference/2025-08-27 [DFS 2] CRM 작성 지침_v1.pptx` — useful for field naming habits; **not** binding for routing.

## Document index

| Doc | Purpose |
|-----|---------|
| [01-salesforce.md](./01-salesforce.md) | Hub API, Case/WO, Activities, opt-in |
| [02-pms.md](./02-pms.md) | Issue create + URL writeback |
| [03-workful-powerapps.md](./03-workful-powerapps.md) | Dataverse registration |
| [04-teams.md](./04-teams.md) | Channels / lists |
| [05-outlook.md](./05-outlook.md) | Technical Support → mail draft |
| [06-release-notes.md](./06-release-notes.md) | Version mail → RN updates |
| [07-routing-matrix.md](./07-routing-matrix.md) | Editable route table |
| [08-priority-recommendation.md](./08-priority-recommendation.md) | Suggested build order |

Master design: `docs/superpowers/specs/2026-08-06-ai-work-automation-design.md`
