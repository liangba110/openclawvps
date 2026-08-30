# Session 2026-07-15: Chat Routing & UI Naming Fixes

## Fix: CustomerService.vue — Companion Chat Goes to Wrong API

### Bug
"聊一聊" on Detail.vue went to `/service?companion_id=X&name=XX`.  
CustomerService.vue showed the companion's name but sent messages to `/cs/send` (customer service) instead of `/chat/send` (companion chat).

### Root Cause
Original code assumed ALL messages from `/service` page go to customer service. The companion_id was passed only for display purposes, not for routing.

### Fix Applied
Added conditional logic in `sendMsg()` and `loadHistory()`:

```javascript
// Send
if (chatCompanion.value.id) {
  await api.post('/chat/send', { to_id: Number(chatCompanion.value.id), content: text })
  messages.value.push({ content: text, is_admin: false, ... })
} else {
  await api.post('/cs/send', { content: text })
}

// Load history
if (chatCompanion.value.id) {
  const res = await api.get('/chat/messages', { params: { user_id: chatCompanion.value.id } })
  const msgList = Array.isArray(res) ? res : (res?.messages || [])
  // Transform: is_admin = (from_id !== currentUserId)
  const userId = JSON.parse(localStorage.getItem('user') || '{}').id || 0
  messages.value = msgList.map(m => ({ ...m, is_admin: Number(m.from_id) !== Number(userId) }))
} else {
  const res = await api.get('/cs/history')
}
```

### Companion Chat API Format
Backend `/api/chat/messages` returns:
```json
[{"id":1,"from_id":5,"to_id":3,"content":"hello","created_at":"..."}, ...]
```
NOT wrapped in `{messages: [...]}` — so `Array.isArray(res)` check is needed.

### Key Files
- `/opt/ttdazi/frontend/src/views/CustomerService.vue`
- `/opt/ttdazi/backend/app/chat.py`

## Fix: Bottom Navigation Naming

See `game-platform-compliance/session-2026-07-15-chat-ui-naming.md` for full detail.

TL;DR: "消息" tab shows message center; companion chat is via "聊一聊" button on detail page → `/service`. Don't mix them.
