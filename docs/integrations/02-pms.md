# PMS (pms.parksystems.com)

## Role

Primary target for SW-related VOC Work Orders (bugs, missing features, inquiries). Issue URL is written back to Salesforce WO Activities.

## API availability

PMS UI and URLs (`/issues/{id}`, `/my/page`) match a **Redmine-family** tracker. Standard Redmine REST is the working assumption until org confirms otherwise.

| Capability | Likely | Endpoint pattern |
|------------|--------|------------------|
| Enable REST | Admin setting | Administration → Settings → API |
| Auth | API key header | `X-Redmine-API-Key` |
| Create issue | Yes | `POST /issues.json` |
| Get issue | Yes | `GET /issues/{id}.json` |
| Update / notes | Yes | `PUT /issues/{id}.json` |
| Attachments | Yes (Redmine) | upload then link |

Docs: [Redmine REST API](https://www.redmine.org/projects/redmine/wiki/Rest_Api)

**Must verify:** REST enabled; custom fields (SW ver., Site/Tool); project/tracker IDs for DFS/SW.

## Auth

- Personal or service **API key** from My Account (or service account).
- Prefer header over `?key=` query (avoids logs).
- HTTPS only.

## How we connect

```text
Router (VOC + Dept SW)
  → map SF Subject/Description/Priority/SW ver.
  → POST /issues.json
  → build URL https://pms.parksystems.com/issues/{id}
  → SF Activities: "PMS – {url}"
```

### Field mapping (draft)

| SF / guideline | PMS |
|----------------|-----|
| Site / Tool / Subject (same as SF title) | `subject` |
| Detailed problem + work notes | `description` |
| Priority (align with SF) | `priority_id` |
| SW version | custom field if present |
| Logs/attachments | Redmine attachments when API allows |

CRM guideline: title must match Salesforce; content detailed; SW ver. required when applicable.

## Usage scenarios

1. Selected Case → VOC WO → Dept SW → create PMS issue after Human Gate.
2. Later: update PMS notes when SF Activities change (optional, not v1).
3. Idempotent re-run: if Activities already contain PMS URL for this WO, skip create.

## Confirm

- [ ] Product is Redmine (or fork) and REST is on
- [ ] project_id / tracker_id for SW VOC
- [ ] Custom field IDs
- [ ] Service account permissions (add issues, view projects)
- [ ] Attachment size limits / required fields validation

## Risks

- If PMS is customized beyond Redmine, payload shapes differ.
- Network/VPN: Tool host must reach `pms.parksystems.com`.
- Duplicate issues if Activities parse fails — rely on idempotency store, not only text parse.
