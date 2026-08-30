# 消息通知系统 API 文档

## message 表结构

```sql
CREATE TABLE `message` (
  `id` int NOT NULL AUTO_INCREMENT,
  `from_id` int NOT NULL DEFAULT '0',
  `to_id` int NOT NULL DEFAULT '0',
  `companion_id` int DEFAULT '0',
  `content` text,
  `is_read` tinyint DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `type` varchar(20) NOT NULL DEFAULT 'system' COMMENT 'order/system',
  `title` varchar(200) NOT NULL DEFAULT '',
  `icon` varchar(10) NOT NULL DEFAULT '',
  `data_id` int DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `to_id` (`to_id`),
  KEY `to_id_is_read` (`to_id`, `is_read`)
);
```

## API 端点

### GET /api/message/list
认证：登录
返回：`{code:0, data: [{id, type, icon, title, content, time, unread, data_id}]}`

```json
{
  "code": 0,
  "data": [
    {
      "id": 5,
      "type": "order",
      "icon": "📋",
      "title": "新待付订单",
      "content": "您有一个新订单(#152 ¥25.0)待支付",
      "time": "2026-07-05 13:41:49",
      "unread": true,
      "data_id": 152
    }
  ]
}
```

### POST /api/message/read-all
认证：登录
Body：无
返回：`{code:0, msg: '已全部标记已读'}`

### GET /api/message/count
认证：登录
返回：`{code:0, data: {unread_count: 3}}`

### POST /api/message/delete
认证：登录
Body：`{id: 5}`
返回：`{code:0, msg: '已删除'}`

## send_notification 调用示例

```python
# 1. 下单 → 通知陪玩师
send_notification(
    companion_user_id,
    f'您有一个新订单(#{str(order_id).zfill(3)} ¥{amount})待支付',
    from_id=user_id,
    ntype='order',
    title='新待付订单',
    icon='📋',
    data_id=order_id
)

# 2. 下单 → 通知下单用户
send_notification(
    user_id,
    f'订单(#{str(order_id).zfill(3)})已创建，金额¥{amount}，请尽快付款',
    companion_id=companion_id,
    ntype='order',
    title='订单已创建',
    icon='📝',
    data_id=order_id
)

# 3. 支付成功 → 通知用户
send_notification(
    user_id,
    f'订单(#{str(order_id).zfill(3)})支付成功，等待陪玩师接单',
    ntype='order',
    title='支付成功',
    icon='💚',
    data_id=order_id
)
```

## 前端组件

### Messages.vue
- 路径：`/messages`
- 数据：`api.get('/message/list')`
- Tab：全部/订单/系统
- 左滑删除（80px → 露出删除按钮 → 弹窗确认）
- 点击消息 → `router.push(/message/${item.id})`

### MessageDetail.vue
- 路径：`/message/:id`
- 自动标记已读：进入详情时调用 `api.post('/message/read-all')`
- "查看相关订单" 按钮 → `router.push('/orders')`
