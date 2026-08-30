# 私聊系统 (Private Chat)

## 数据库
```sql
CREATE TABLE chat_message (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    from_id INT NOT NULL COMMENT '发送者',
    to_id INT NOT NULL COMMENT '接收者',
    content TEXT NOT NULL,
    is_read TINYINT DEFAULT 0 COMMENT '0未读 1已读',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_from_to (from_id, to_id),
    KEY idx_to_read (to_id, is_read)
);
```

## 后端 API
文件: `/opt/ttdazi/backend/app/chat.py` (Blueprint: chat_bp, prefix: /api/chat)

| 端点 | 方法 | 功能 | 认证 |
|------|------|------|------|
| /api/chat/send | POST | 发送私聊消息 | @login_required |
| /api/chat/messages | GET | 获取与某用户的聊天记录 | @login_required |
| /api/chat/conversations | GET | 获取私聊会话列表 | @login_required |
| /api/chat/unread | GET | 获取私聊未读数 | @login_required |

send: {to_id, content} content <= 1000字符
messages: ?user_id=X&page=1 自动标记对方消息已读。ESM正序返回
conversations: 子查询获取最新消息+未读+对方昵称头像

## 前端页面
ChatConversation.vue 路由 /chat?user_id=X&name=Y
布局: flex column 占满全屏, 消息气泡(渐变紫mine/白色other), 5秒轮询

## 私聊入口（全平台互通）
- 需求大厅 status=1 → d.user_id
- 我的订单 status=1/2 → order.companion_user_id
- 陪玩师订单 status=1 → order.user_id
- 我的需求 status=1 → d.companion_id
统一: router.push(`/chat?user_id=${uid}&name=${encodeURIComponent(name)}`)
