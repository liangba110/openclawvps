# Message Notification System — Full Architecture

## Table Schema

```sql
-- Base columns (original):
id INT AUTO_INCREMENT, from_id INT, to_id INT, companion_id INT DEFAULT 0,
content TEXT, is_read TINYINT DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP

-- Added for structured notifications:
ALTER TABLE message 
  ADD COLUMN type VARCHAR(20) NOT NULL DEFAULT 'system' COMMENT '通知类型: order/system',
  ADD COLUMN title VARCHAR(200) NOT NULL DEFAULT '' COMMENT '通知标题',
  ADD COLUMN icon VARCHAR(10) NOT NULL DEFAULT '' COMMENT '通知图标emoji',
  ADD COLUMN data_id INT DEFAULT 0 COMMENT '关联数据ID(如订单ID)';
```

## Backend: send_notification (upgraded)

In `utils.py`:

```python
def send_notification(to_id, content, companion_id=0, from_id=0, 
                       ntype='system', title='', icon='', data_id=0):
    if not title:
        title = content[:100]
    if not icon:
        icon = '🔔' if ntype == 'system' else '📋'
    # INSERT with all structured fields
```

## Order Event Notifications (in order.py + payment.py)

| Event | To | type | icon | title | data_id |
|-------|----|------|------|-------|---------|
| Order created | Companion | order | 📋 | 新待付订单 | order_id |
| Payment success | User | order | 💚 | 支付成功 | order_id |
| User confirms service | Companion | order | ▶️ | 服务已开始 | order_id |
| Companion completes | User | order | ✅ | 订单已完成 | order_id |

## Frontend: /api/message/list Response Shape

```json
{
  "code": 0,
  "data": [
    {
      "id": 1,
      "type": "order",        // "order" or "system"
      "icon": "📋",
      "title": "新订单通知",
      "content": "您有一个新订单...",
      "time": "2026-07-05 14:30:00",
      "unread": true,
      "data_id": 42
    }
  ]
}
```

## Frontend Messages.vue Data Fields

The template accesses these properties:

| Template field | Backend response field | Example |
|----------------|----------------------|---------|
| `item.type` | `type` | `'order'` |
| `item.icon` | `icon` | `'📋'` |
| `item.title` | `title` | `'新订单通知'` |
| `item.content` | `content` | `'您有一个新订单...'` |
| `item.time` | `time` (formatted) | `'2026-07-05 14:30'` |
| `item.unread` | `unread` (bool) | `true` |

## Message Detail Page

Route: `/message/:id` → `MessageDetail.vue`

- Shows full content with icon + title + time
- Auto-marks as read when opened
- Order-type messages show "查看相关订单" button
- Delete button with confirmation dialog

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/message/list` | GET | login | List user's 50 most recent messages |
| `/api/message/read-all` | POST | login | Mark all as read |
| `/api/message/count` | GET | login | Get unread count |
| `/api/message/delete` | POST | login | Delete single message (`{id}`) |

## Pattern for Adding New Notification Types

1. Call `send_notification()` with structured params
2. Frontend automatically shows it with correct icon/type/title
3. The existing Messages.vue tabs (全部/订单/系统) correctly categorize by `type` field
