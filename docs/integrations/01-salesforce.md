# Salesforce (Hub)

## Role

System of record for Case and Work Order. Automation **reads** selected post-cutoff records, may **append** Activities / create related WO only in allowed flows, and never bulk-edits historical Cases.

## API availability

| Capability | Available | Notes |
|------------|-----------|-------|
| REST sObject CRUD | Yes | `/services/data/vXX.X/sobjects/{Object}/{Id}` |
| SOQL query | Yes | `/query?q=` |
| OAuth | Yes | Connected App or External Client App; Client Credentials or JWT for server |
| Change Data Capture / Platform Events | Yes (org-dependent) | Optional trigger instead of polling |
| Composite / Tree | Yes | Batch related creates if needed |

Official: [Salesforce REST API](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_what_is_rest_api.htm)

## Auth (recommended)

1. Create Connected App / External Client App with API scopes.
2. Integration user with least privilege (read Case/WO; update only Activities fields used for writeback; create WO if product requires it).
3. Prefer **Client Credentials** or **JWT Bearer** for unattended Tool.
4. Store client id/secret outside repo.

## Objects & fields (observed / guideline)

| Area | Examples | Use |
|------|----------|-----|
| Case | Type, Priority, Origin, Status, Subject, Description, Asset | Context for drafts |
| Case classification | Issue Classified as SW, OBJ Type, etc. | Routing hints |
| Case Activities (long text) | Chronological notes | Optional secondary log |
| Work Order | Record Type (VOC, Technical Support, …), Status, Priority | Primary routing key |
| Relevant Department | QI, SW, HW, Manual, P/L Spec, Sales, TS | Target system key |
| VOC fields | VOC Title, Background/Problem/Impact, Remedies, … | PMS/Teams body |
| [VOC] Activities | Free text for external refs | **Primary writeback** |

Exact API names (`__c`) must be confirmed via Describe API in the org.

## How we connect

```text
Tool ──OAuth──► Salesforce
  GET Case + WorkOrders (+ Asset)
  PATCH WorkOrder Activities (append only, selected + post-cutoff)
  POST WorkOrder (only if user-driven flow requires create)
```

### Trigger options

| Option | Pros | Cons |
|--------|------|------|
| User clicks “Run” on selected Case | Safest; matches opt-in | Not fully background |
| Poll SOQL for selected flag | Simple | Latency, API usage |
| CDC / Flow → webhook | Near real-time | Needs SF admin |

**v1 recommendation:** explicit Run on selected Cases; optional light poll later.

## Safety constraints

- `CreatedDate >= automation_enabled_after` (or Id watermark) required.
- Case must be in Tool selection list (or SF opt-in field).
- No update to Cases/WOs outside selection.
- Append-only Activities: preserve existing text; never wipe history.

## Usage scenarios

1. **Hub read** for any connector draft.
2. **VOC path:** ensure/create WO → after external post → Activities `PMS – url` / `Work Pool – no` / etc.
3. **Technical Support path:** WO ready → Outlook draft → optional Activities note.
4. **Opt-in flag** (if SF field chosen): user or Tool sets checkbox so teammates see automation status.

## Confirm with IT / org

- [ ] Connected App / External Client App allowed
- [ ] Integration user + FLS/CRUD on needed objects/fields
- [ ] Describe API for custom field API names
- [ ] Whether WO create from API is permitted for Record Types used
- [ ] CDC available if background sync desired later

## Risks

- Custom Record Types / validation rules may block API creates.
- Long-text Activities have size limits — append carefully.
- Wrong cutoff logic could touch production history — guard with automated tests.
