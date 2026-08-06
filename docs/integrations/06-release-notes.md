# Release Notes (release-note-web-db-tool)

## Role

Separate loop from VOC→PMS: when an **improved SW debug/release version** arrives (usually by **email**), engineer reviews changelog bullets and types update items into the Release Notes web app.

URL: `https://release-note-web-db-tool.vercel.app/dashboard`

## API availability

| Capability | Status | Notes |
|------------|--------|-------|
| Public documented API | **Not found** | Dashboard is a Next.js (“Create Next App”) UI |
| `/api` probe | 404 at time of review | May still have private routes |
| First-party API | **TBD** | Preferred if you own the repo |
| Browser automation | Possible fallback | Fragile |
| Direct DB | Only if backend/DB credentials known | Out of band |

## How we might connect (options)

### A. Add app API (recommended if you own it)

```text
POST /api/cards or /api/updates
  { site, equipment, version, items[], sourceMailId }
→ return card id / URL
```

### B. Reuse existing backend

If the app already talks to Supabase/Firebase/custom API, call the same endpoints the UI uses (discover via browser Network tab while logged in).

### C. UI automation

Last resort for MVP experiments; not for production unattended runs.

### Mail intake

```text
Outlook/Graph: monitor mailbox or folder for SW version mails
  → AI extract version + improvement bullets
  → Human Gate
  → Release Notes connector
```

This can share the Outlook Graph auth with the Technical Support draft feature, but uses **read** mail permissions carefully (least privilege folder).

## Usage scenarios

1. New version mail → suggested RN items → user approves → create/update card.
2. Link RN card URL into related SF Case Activities when a Case Id is known (optional).
3. Not routed from VOC Relevant Department by default.

## Confirm

- [ ] Repo location and whether API can be added
- [ ] Auth model of the dashboard (who can write)
- [ ] Data model: Site / Equipment / version cards
- [ ] Mailbox/folder rules for version announcements

## Risks

- Without API, automation quality is low.
- Mis-posted release notes affect many sites — Human Gate mandatory.
- Lower priority than PMS/Outlook until API path exists.
