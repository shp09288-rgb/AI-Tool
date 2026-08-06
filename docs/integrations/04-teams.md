# Microsoft Teams

## Role

Channels and related artifacts for:

- Work Pool-related visibility (if still used alongside Workful)
- OBQ / QI (MC requests) — share link writeback
- Issue & VOC tracking (guideline mentioned DISPLAY sheet / aging)

## API availability

| Capability | Available | API |
|------------|-----------|-----|
| Post channel message | Yes | Graph `POST /teams/{id}/channels/{id}/messages` |
| Chat message | Yes | `/chats/{id}/messages` |
| SharePoint list item | Yes | `/sites/{id}/lists/{id}/items` |
| Excel on SharePoint | Yes | Graph Excel APIs (fragile for complex sheets) |
| Adaptive Card notify | Yes | Via message or Power Automate |

Docs: [Send chatMessage](https://learn.microsoft.com/en-us/graph/api/chatmessage-post)

## Auth

- Entra app: delegated or application permissions (`ChannelMessage.Send`, `Sites.ReadWrite.All`, etc. — least privilege).
- Admin consent typically required for application permissions.
- Prefer posting as a dedicated bot/service identity.

## How we connect

```text
Router target = teams_obq | teams_voc | teams_notify
  → resolve teamId + channelId (config)
  → post message or create list item
  → return share link / message deep link
  → SF Activities: "OBQ, QI – {link}" etc.
```

### Issue & VOC sheet caveat

CRM guideline: only edit `DISPLAY_Issue and VOC list`; aging auto-calculated. If that is a protected Excel sheet:

- Prefer **SharePoint list** mirror for API writes, or
- Power Automate curated flow, or
- Human Gate produces clipboard/draft for manual paste (fallback).

Hyperlink columns via Graph have known limitations — verify column types before relying on Graph list create.

## Usage scenarios

1. MC / OBQ·QI requests → channel post or list row + link writeback.
2. Human Gate notifications (“Approve PMS post for Case X”).
3. Optional notify after Workful/PMS success.

## Confirm

- [ ] Team/channel IDs for OBQ, QI, Issue&VOC, Work Pool
- [ ] Artifact type per channel (message vs list vs Excel)
- [ ] Permission model (delegated user vs app-only)
- [ ] Whether Workful replaced Teams Work Pool registration

## Risks

- Wrong channel spam — Human Gate mandatory for posts.
- Excel sheet automation is brittle; avoid as primary path.
- Application permission to send as app may need Teams policy allowlisting.
