# 私聊系统

## 数据库

```sql
chat_message 表：
  id         BIGINT AUTO_INCREMENT PRIMARY KEY
  from_id    INT NOT NULL           -- 发送者 user_id
  to_id      INT NOT NULL           -- 接收者 user_id
  content    TEXT NOT NULL          -- 消息内容
  is_read    TINYINT DEFAULT 0      -- 0未读 1已读
  created_at DATETIME
  KEY idx_from_to (from_id, to_id)
  KEY idx_to_read (to_id, is_read)
```

## API（`/api/chat/`）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/chat/send` | @login_required | 发送私聊消息 |
| GET | `/api/chat/messages?user_id=X` | @login_required | 获取聊天记录（自动标记已读） |
| GET | `/api/chat/conversations` | @login_required | 会话列表（最后消息+未读数+对方昵称） |
| GET | `/api/chat/unread` | @login_required | 私聊未读数 |

## 前端页面

| 文件 | 路由 | 说明 |
|------|------|------|
| `ChatConversation.vue` | `/chat?user_id=X&name=Y` | 私聊对话页 |
| `ChatList.vue` | `/chat-list` | 私聊会话列表 |

### 对话页气泡样式

```
mine  = 紫色渐变右对齐 (gradient 135deg #667eea #764ba2, #fff, brb 4px)
other = 白底左对齐 (#fff, #333, blb 4px, shadow)
时间  = 10px #aaa
```

每 5 秒轮询 `/chat/messages?user_id=X` 获取新消息。`onUnmounted` 清理定时器。

## 入口集成

| 页面 | 触发条件 | 跳转目标 |
|------|---------|---------|
| DemandHall.vue | status=1（已接单） | `/chat?user_id=d.user_id&name=d.nickname` |
| Orders.vue | status=1 或 2（进行中/待确认） | `/chat?user_id=order.companion_user_id&name=order.nickname` |
| PlaymateOrders.vue | status=1（进行中） | `/chat?user_id=order.user_id&name=order.customer_nickname` |
| MyDemands.vue | status=1（已接单） | `/chat?user_id=d.companion_id&name=d.companion_name` |
| Profile.vue | 菜单入口 | `/chat-list`（会话列表） |

## ⚠️ 常见陷阱

### 1. `companion_user_id` vs `companion_id`

**订单表的 `companion_id` 是 companion 表的主键，不是 user_id！** 要获取陪玩师对应的用户 ID，必须在订单查询中 JOIN companion 表：

```python
# order.py SELECT 查询中
SELECT c.id as companion_id, c.user_id as companion_user_id, ...
FROM orders o
JOIN companion c ON c.id = o.companion_id
```

前端用 `order.companion_user_id` 作为 `/chat` 的 `user_id` 参数，不要用 `order.companion_id`。

### 2. `encodeURIComponent` + Vue Router = 双重编码

```javascript
// ❌ 错误 — encodeURIComponent + router.push(query) 双重编码
const name = encodeURIComponent(order.nickname)
router.push({ path: '/chat', query: { user_id: uid, name: name } })
// 结果: /chat?user_id=10011&name=%25E5%25B7%2585... (乱码)

// ✅ 正确 — 传明文，Vue Router 自动编码一次
router.push({ path: '/chat', query: { user_id: uid, name: order.nickname } })
```

Vue Router 的 `query` 参数在构建 URL 时已经会进行 URL 编码。如果再用 `encodeURIComponent` 预编码，就会得到双重编码。

**所有页面（Orders/DemandHall/MyDemands/PlaymateOrders/ChatList）都需检查并移除 `encodeURIComponent` 调用。**

### 3. `@click` 函数在模板中引用但未在 `<script setup>` 中定义

**症状：** 点击无反应，浏览器 Console 无报错。

**根因：** Vue 3 模板编译器不会检查函数是否存在。如果函数在 `<script setup>` 中不存在，Vue 静默不渲染 click 事件。

```vue
<template>
  <div @click="chatWithCompanion(order)">私聊</div>
</template>
<script setup>
// ❌ chatWithCompanion 未定义 — Vue 静默忽略 click
</script>
```

**检查方法：**
```bash
grep -oP '@click="\w+' page.vue | sort -u > /tmp/tpl.txt
grep -oP 'function \w+' page.vue | sort -u > /tmp/scr.txt
diff /tmp/tpl.txt /tmp/scr.txt | grep '^<'
```

### 4. `v-if` 条件

进行中/待确认订单才显示私聊：

```html
<div class="order-chat" v-if="order.status === 1 || order.status === 2" @click="chatWithCompanion(order)">
```

### 5. 订单私聊只应在进行中和待确认订单显示

```javascript
v-if="order.status === 1 || order.status === 2"
```
其他状态（0=待支付, 3=已完成, 4=已取消）不显示私聊。

## 后端蓝图注册（三处检查）

详见 `SKILL.md` 的「新模块接入 main.py 三处检查」。
