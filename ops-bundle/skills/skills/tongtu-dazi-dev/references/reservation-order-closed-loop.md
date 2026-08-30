# 预约制服务闭环（2026-08 上线，替代信息匹配服务费）

## 业务模型（用户确认的最终规则）

```
用户预约服务 → 支付服务全款(进平台账户) → status=1 待接单 → 站内通知达人
→ 达人接受预约 status=2 → 双方约定服务信息(私聊)
→ 达人【开始服务】status=3 ⏱倒计时(按预约时长, 仅展示) → 倒计时自然结束 status=4 待确认
→ 用户确认 / 3天自动确认 status=5 → 佣金结算(平台) + 服务费(达人) → 达人可提现
→ 用户评价 👍好评/😐一般/👎差评(自动展示, 无需审核) → 达人可回复
```

**固定规则**（用户拍板，勿再问）：
- 预约金额 = 服务全款（非定金+尾款）
- **不可提前结束**（达人不能提前结束、用户不能申请提前结束；倒计时自然走完；纠纷走管理端手动结束）
- 自动确认 = 3 天（site_config `auto_confirm_days` 后台可配）
- 佣金 = site_config `commission_rate`（默认 15%，后台可配）
- 通知 = 仅站内通知（notifications 表，不用公众号）
- 退款 = 达人未接受自动退；已接受 → 协商/管理端介入
- 双站共用一套流程与数据库（国际站+主站）

## 订单状态机（2026-08 新，注意与旧状态冲突）

| status | 含义 | 触发 |
|--------|------|------|
| 0 | 待支付 | 创建 |
| 1 | 待接单（已付全款） | 支付回调 |
| 2 | 已接受（约定中） | 达人 accept-order |
| 3 | 服务中（倒计时） | 达人 complete-order(改造为开始服务) |
| 4 | 待确认 | cron 倒计时结束 3→4 |
| 5 | 已完成（已结算） | 用户 confirm-service / cron 3天自动确认 |
| 6 | 已取消/已退款 | reject-order / refund |

**⚠️ 与旧状态机差异**（旧：0待支付/1待接单/2服务中/3完成/4取消）：
- 旧 `complete-order`(2→3) 语义被改为「开始服务」（写 service_started_at + service_ended_at=started+duration）
- 旧 `reject-order`(1→4) 改为「拒绝预约→6 取消+退款」
- 旧 `accept-order`(1→2) 语义正好匹配「接受预约」，保留

## 数据库改动

```sql
ALTER TABLE orders
  ADD service_date DATETIME COMMENT '预约时间',
  ADD service_duration INT DEFAULT 1 COMMENT '时长(小时)',
  ADD service_started_at DATETIME,
  ADD service_ended_at DATETIME COMMENT '倒计时终点=started+duration',
  ADD confirm_deadline DATETIME COMMENT '确认截止=ended+3天',
  ADD auto_confirmed TINYINT DEFAULT 0;
-- site_config: commission_rate=15, auto_confirm_days=3, service_durations=1,2,3,4,6,8
```

## 后端 API

| 类型 | API | 说明 |
|---|---|---|
| 新增 | `POST /api/order/confirm-service` | 用户确认完成 4→5，佣金结算(达人=金额×(1-rate)，写 companion_income + settled + money_log) |
| 新增 | `GET /api/order/detail/:id` | 订单详情（倒计时/确认截止/评价状态） |
| 新增 | `POST /api/order/refund` | 退款（status=1 自动退；已接受进管理端） |
| 改造 | `complete-order` | 2→3 开始服务，写 started_at + ended_at |
| 改造 | `reject-order` | 1→6 拒绝预约 |
| 改造 | `companion.py my_orders` | SELECT 补 service_date/duration 字段 |

## 定时任务 order_cron.py（crontab 每分钟）

```bash
* * * * * curl -s -m 20 http://127.0.0.1:5002/api/cron/order-tasks > /dev/null 2>&1
```
两个任务：
1. **倒计时结束**：`UPDATE orders SET status=4 WHERE status=3 AND service_ended_at <= NOW()` + 通知用户确认
2. **3天自动确认**：`UPDATE orders SET status=5, auto_confirmed=1, settled=1 ... WHERE status=4 AND confirm_deadline <= NOW()` + 佣金结算 + 通知达人

注册：`main.py` 加 `from app.order_cron import cron_bp` + `app.register_blueprint(cron_bp)`。

## 前端页面

| 端 | 页面 | 改动 |
|---|---|---|
| 用户端 | Detail.vue | 「预约服务」入口（owner 显示展示费、非 owner 预约） |
| 用户端 | CreateOrder.vue | 预约模式：选时长/日期/金额=用户自设价×时长 |
| 用户端 | 新增 OrderDetail.vue | ⏱倒计时实时显示 + 确认服务按钮 + 三档评价弹窗 |
| 用户端 | Orders.vue | tab：待接单/服务中/待确认/已完成 |
| 达人端 | PlaymateOrders.vue | 接受预约/开始服务/等待确认/倒计时展示 |
| 管理端 | admin.py | status 映射 0-6（pending/paid/accepted/active/confirming/completed/cancelled） |

## ⚠️ 开发踩坑

1. **flask 路由重名崩溃**：新 API 追加到 order.py 时若重复执行了追加脚本，会生成**两份相同路由** → gunicorn worker boot 失败（`Worker failed to boot`）。症状：HUP 重启后健康检查不通。排查：`grep -c '@order_bp.route' order.py` 应为 N，`grep -n` 看重复行，删掉第二次追加块（含分隔注释）。
2. **service 端 python 环境**：gunicorn 以 ubuntu 用户运行，语法检查必须 `sudo -u ubuntu /usr/bin/python3.12 -m py_compile`（root 的 python3 没有 flask）。
3. **测试 token**：`sudo -u ubuntu /usr/bin/python3.12 -c 'from app.token_auth import gen_token; print(gen_token(10001,"test"))'` 生成有效 v2 token 测接口。
4. **清理测试数据**：全链路测试会写 money_log/orders/companion 累计，测完要 DELETE + 恢复 companion.total_income。

## 旧模式废弃

- 信息匹配服务费 ¥10（visitor_chat 非预约）已取消：CreateOrder 访客模式、DemandHall「🔓付费解锁¥10」、Profile「信息服务」菜单、Agreement 协议条款全部移除
- 现行收费仅两笔：达人置顶展示费（¥79/199/599 包月/季/年）+ 预约服务费（¥30-200/小时）
- 详见 📖 `references/info-matching-order-flow.md`（旧流程，仅存档）
