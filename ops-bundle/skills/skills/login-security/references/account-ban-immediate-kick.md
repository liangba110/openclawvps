# Account Ban — Immediate Session Revocation

## Problem
Setting `user.status=0` (ban) only prevents new logins. Existing tokens stay valid.

## Solution
Check `user.status` in `login_required` decorator on every API request.

## Files Modified
- `/opt/ttdazi/backend/app/utils.py` — Add `_check_user_active()` + status check in `login_required`
- `/opt/ttdazi/frontend/src/api/index.js` — Add `errMsg.includes('封禁')` check in 401 handler

## SQL
```sql
UPDATE `user` SET status=0 WHERE id=XX;  -- ban
UPDATE `user` SET status=1 WHERE id=XX;  -- unban
```

## Verification
```bash
# Admin bans user → user's next request returns 401 "账号被封禁"
curl -s http://82.157.202.24/api/message/count -H "Authorization: Bearer $BANNED_USER_TOKEN"
# Response: {"code":401,"msg":"账号已被封禁"}
# Frontend: clears localStorage → redirects to login → toast "账号已被封禁"
```
