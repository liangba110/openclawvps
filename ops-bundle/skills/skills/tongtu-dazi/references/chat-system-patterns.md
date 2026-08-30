# 同途搭子聊天系统

## 架构

两套聊天系统：
1. **私聊** (`chat_message`表) — 用户↔搭子之间的私密对话，通过 `/api/chat/*` 路由
2. **客服** (`cs_message`表?) — 用户↔平台客服对话，通过 `/api/cs/*` 路由

## 私聊 API

| 端点 | 方法 | 说明 |
|:----|:----:|:------|
| `/api/chat/send` | POST | 发送消息，需 `{to_id, content}`，`to_id` 是用户的user_id |
| `/api/chat/messages?user_id=X` | GET | 获取与某用户的聊天记录，`user_id` 是对方的user_id |
| `/api/chat/conversations` | GET | 获取会话列表，返回 `[{other_id, nickname, last_msg, last_time, unread}]` |
| `/api/chat/unread` | GET | 获取私聊未读总数，返回 `{unread: N}` |

## ⚠️ 关键陷阱：companion_id 与 user_id

**🚨 这是最常见的bug来源。**

- `companion` 表的 `id` 是**达人记录ID**（如 24）
- `companion` 表的 `user_id` 是**用户账号ID**（如 10047）
- 聊天系统 `/api/chat/send` 和 `/api/chat/messages` 需要的 `to_id` / `user_id` 都必须是 **user_id**，不是 companion_id

**出bug的路径**：
1. `Detail.vue` 中 `goChat()`：`router.push('/service?companion_id=' + id)` — 这里的 id 是 companion.id
2. `CustomerService.vue` 接收 `chatCompanion.value.id = route.query.companion_id` — 拿到的是 companion_id
3. 发消息时传 `to_id = chatCompanion.value.id` → 消息存入 `chat_message` 表但 `to_id` 是 companion_id
4. 搭子查聊天列表时查不到这条消息 → "收不到"

**正确做法**：
```javascript
// CustomerService.vue - onMounted时获取真实user_id
const detail = await api.get('/companion/detail', { params: { id: companion_id } })
const user_id = detail.user_id  // 这才是对的人
// 然后 user_id 用于 chat APIs
```

## 未读消息系统

全局未读数 = 系统通知(`/api/message/count`) + 私聊未读(`/api/chat/unread`)

**App.vue 需要同时轮询两个端点**：
```javascript
async function fetchUnread() {
  const sys = await api.get('/message/count')
  const chat = await api.get('/chat/unread')
  // sys.unread_count + chat.unread
}
```

**Profile.vue 中的「我的私聊」菜单项**：
- 需单独轮询 `/api/chat/unread`（每10秒）
- 用红色气泡 `mi-badge` 显示未读数

## 时间格式规范

| 时间 | 格式 | 示例 |
|:---|:-----|:-----|
| 今天 | HH:mm | 14:35 |
| 今年内 | MM-DD HH:mm | 07-28 09:12 |
| 跨年 | YYYY-MM-DD HH:mm | 2025-12-01 20:30 |

```javascript
function formatTime(t) {
  if (!t) return ''
  const d = new Date(t), now = new Date(), pad = n => String(n).padStart(2, '0')
  const today = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`
  const dateStr = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`
  const timeStr = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (dateStr === today) return timeStr
  if (d.getFullYear() === now.getFullYear()) return `${pad(d.getMonth()+1)}-${pad(d.getDate())} ${timeStr}`
  return `${dateStr} ${timeStr}`
}
```
