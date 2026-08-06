# Workful (PowerApps / Dataverse)

## Role

Current “Work Pool” style registration UI is a **Power Apps** canvas/model-driven app (not only a Teams channel). Used when Work Order / request is SRD-oriented registration; writeback is typically a **registration number**.

## Entry URL

Power Apps play URL under tenant `7634c4dc-9a4e-4615-932e-99f681471d92` (see user-provided link). App id appears in the play URL path (`a/10ada818-…`).

Legacy PPT labeled this “Work Pool (Teams)” — treat Teams as notification/UI sibling if still used; **API path is Dataverse** behind Power Apps when data is stored there.

## API availability

| Capability | Available | Notes |
|------------|-----------|-------|
| Dataverse Web API | Yes (if app uses Dataverse) | OData v4 |
| Auth | Microsoft Entra ID | App registration + application user |
| Create row | `POST /api/data/v9.2/{entityset}` | Need logical names |
| SharePoint-only app | Possible | Then Graph/SharePoint API instead |

Docs: [Dataverse Web API](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/overview)

## Auth

1. Entra app registration.
2. Application user in Dataverse with security role on target tables.
3. Client credentials → Bearer token for org URL (`https://{org}.crm.dynamics.com`).

## How we connect

```text
1. Confirm data store: Dataverse table vs SharePoint list vs SQL.
2. Describe columns (registration number, site, tool, subject, requester).
3. POST create → read back auto-number / id.
4. SF Activities: "Work Pool – {등록번호}" (or current label).
```

### Discovery checklist

- [ ] Open app → which tables (monitor network or Power Apps Studio)
- [ ] Environment URL + entity set names
- [ ] Field for “등록번호” and required fields
- [ ] Whether Teams is only a link surface

## Usage scenarios

1. Router selects `workful` for SRD / Work Pool-type WO.
2. AI drafts row fields from Case/WO.
3. Human Gate → create → writeback number.
4. Optional: post Teams message with deep link to the new row (Teams connector).

## Risks

- Schema unknown until inspected — highest discovery cost after Release Notes.
- If app logic (Power Automate) must run on create, direct Dataverse insert may bypass validations — prefer triggering the same flow if required.
- Tenant admin approval for app permissions.
