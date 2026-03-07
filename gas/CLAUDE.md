# GAS Bridge — Deployment & Gotchas

## Deployment Checklist

Every time `Code.gs` changes:
1. script.google.com → Scout Bridge → Code.gs → edit + save
2. Deploy → Manage deployments → pencil icon → Version: New version → Deploy
3. Copy new URL
4. Railway dashboard → Variables → update `GAS_WEBHOOK_URL`
5. Railway redeploys automatically
6. Run `/ping_gas` to verify

## Gotchas

- `SECRET_TOKEN` placeholder in Code.gs must be replaced with actual token before deploying
- `Session.getActiveUser().getEmail()` returns `""` for anonymous callers — hardcode `"steven@codecombat.com"` in ping handler
- Never use `Session.getEffectiveUser()` — throws permission error
- Bumping version on an existing deployment keeps the same URL — no Railway update needed
- DriveApp `getFolderById` throws "Unexpected error" if not authorized OR during a deployment that hasn't re-authed. Wrap in try/catch so doc creation never fails due to folder move.
- `SEQUENCES_FOLDER_ID` (and any Drive folder ID env var) may be pasted as full browser URL with `?ths=true`. Strip with `.split("?")[0]` before use.

## Gmail Intelligence Hub Pattern

PandaDoc and Dialpad both email Steven when events occur. Use `gas.search_inbox()` with targeted queries to parse notifications for activity logging — no API permissions needed. Dialpad call summary emails must be enabled by Steven in Dialpad → Settings → Notifications → Call Summary.
