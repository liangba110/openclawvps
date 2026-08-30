# Hermes QQ Bot User Whitelist

Restrict QQ bot responses to specific users — useful for group chats where
only the owner/admin should trigger the agent.

## Env Var

```
QQ_ALLOWED_USERS=<comma-separated user IDs>
```

Set in `~/.hermes/.env`. Leave empty or unset to allow all users.

## User ID Discovery

The user's QQ ID appears in the session context as `sender_id`. For the
current DM session, the sender is identified by a hash like `EBF3C598...`.

## Applying Changes

1. Edit `~/.hermes/.env`: set `QQ_ALLOWED_USERS=<your_id>`.
2. Restart the gateway:
   ```bash
   hermes gateway restart
   ```
   Or from within a DM: use `/restart` slash command.
   (Note: gateway restart is blocked from within gateway sessions — use a separate SSH shell.)

## Behavior

| Config | Group behavior | DM behavior |
|--------|---------------|-------------|
| `QQ_ALLOWED_USERS=` (empty) | Everyone can @bot | Everyone can DM |
| `QQ_ALLOWED_USERS=ID1,ID2` | Only ID1/ID2 can @bot | Only ID1/ID2 can DM |

## Platform Env Var Pattern

Other messaging platforms follow the same pattern:
- Telegram: `TELEGRAM_ALLOWED_USERS`
- Discord: `DISCORD_ALLOWED_USERS`
- Slack: `SLACK_ALLOWED_USERS`
- WeChat: `WEIXIN_ALLOWED_USERS`
- QQ: `QQ_ALLOWED_USERS`

Source: `gateway/pairing.py` in the Hermes codebase.
