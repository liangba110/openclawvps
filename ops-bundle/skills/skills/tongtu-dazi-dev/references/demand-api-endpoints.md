# 需求功能 (Demand) API 端点

## 用户端

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/demand/list` | 无 | 需求大厅列表（**只显示已支付 status=1 的需求**） |
| GET | `/api/demand/my` | 无 | 当前用户的需求列表（含待支付） |
| POST | `/api/demand/create` | `{title, game_id, description, service_duration, price}` | **付费发布**：创建需求（status=0 待支付），返回 `{order_no(DMD前缀), demand_id, amount}` |
| POST | `/api/demand/accept` | `{id}` | 接单（陪玩师操作） |
| POST | `/api/demand/cancel` | `{id}` | 取消需求（发布者操作） |
| POST | `/api/demand/complete` | `{id}` | 确认完成（发布者操作） |

## 管理端

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/demand/admin/list` | `?status=` | 需求管理列表（status 可选过滤） |
| POST | `/api/demand/admin/delete` | `{id}` | 删除指定需求 |

## ⚠️ 2026-08 改造：付费发布（原"免费发布+付费解锁"已废弃）

### 发布流程
```
用户填需求(标题/描述/服务时长) + 自设每小时价格 → POST /demand/create
→ 发布费 = price × service_duration（price 校验 30≤x≤200，前后端双重）
→ 订单号 DMD 前缀，status=0 待支付
→ 前端跳 location.origin + '/pay' 支付（redirect 需 #/ 前缀！）
→ 支付服务回调 /api/pay/notify/recharge 识别 DMD 前缀 → UPDATE status=0→1 → 需求上架
```

### 状态机（2026-08 重排）
| 值 | 含义 | 可操作 |
|----|------|--------|
| 0 | 待支付（刚创建未付款） | 发布者：去支付 / 取消 |
| 1 | 已发布（大厅可见，待响应） | 所有人：💬 私聊；发布者：确认完成 |
| 2 | 已响应 | 发布者：确认完成 |
| 3 | 已完成 | 只读 |
| 4 | 已取消 | 只读 |

### 关键实现点
- **DMD 前缀回调**：`pay_api.py notify_recharge` 开头加 `if order_no.startswith('DMD'): UPDATE demand_order SET status=1 WHERE order_no=%s AND status=0`，返回 `demand_paid`
- **价格校验**：`service_duration` 1-24 小时；`price` ¥30-200，`<30` 报"不得低于¥30"、`>200` 报"不得高于¥200"
- **前端 MyDemands.vue**：发布弹窗（标题/描述/价格输入30-200/时长选择1-8）+ 提交后跳支付 + 待支付单显示「去支付」按钮
- **已取消**：需求大厅「🔓 付费解锁 ¥10」按钮已删除 → 直接「💬 私聊沟通」（信息匹配服务费整体取消）
- **site_config**：`demand_publish_price` 已废弃（改用户自设价），实际控制为硬编码校验

