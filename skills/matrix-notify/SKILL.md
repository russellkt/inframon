---
name: matrix-notify
description: Send messages to specific Matrix rooms. Used by triage and patrol agents to post to #inframon-alerts and #inframon-patrol rooms.
trigger_words:
  - notify
  - matrix
  - send message
  - post to room
  - alert room
  - patrol room
---

# Matrix Notify

Send messages to specific Matrix rooms via the Client-Server API. Bypasses OpenFang's `channel_send` which can't target specific rooms.

## Usage

```bash
python3 /data/skills/matrix-notify/scripts/matrix_notify.py --room <room> --message "text"
```

## Room Aliases

Built-in aliases for convenience (or use full room IDs):

| Alias | Room | Room ID |
|-------|------|---------|
| `inframon` | #inframon (interactive) | `!PwgTYHCRXkvXzbgqpQ:matrix.org` |
| `alerts` | #inframon-alerts (triage) | `!wnxZoiPfVQuSlgJVvy:matrix.org` |
| `patrol` | #inframon-patrol (patrol) | `!GNBDVQhyXYYugtroNR:matrix.org` |

## Examples

**Post alert investigation result:**
```bash
python3 /data/skills/matrix-notify/scripts/matrix_notify.py \
    --room alerts \
    --message "[WARNING] pve-r720 storage at 89% — recommend cleanup within 48h"
```

**Post patrol report:**
```bash
python3 /data/skills/matrix-notify/scripts/matrix_notify.py \
    --room patrol \
    --message "Nightly patrol complete. All systems nominal."
```

**Cross-post critical finding to alerts room:**
```bash
python3 /data/skills/matrix-notify/scripts/matrix_notify.py \
    --room alerts \
    --message "[CRITICAL] PBS offsite sync has not completed in 36 hours"
```

## Environment Variables

- `MATRIX_ACCESS_TOKEN` — Bot access token (required)
- `MATRIX_HOMESERVER_URL` — Homeserver URL (default: `https://matrix.org`)
