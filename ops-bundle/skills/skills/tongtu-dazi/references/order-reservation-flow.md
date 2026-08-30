# 预约制服务闭环（咨询→下单→接单→服务→确认→评价）

## 业务闭环（用户确认版）
用户预约服务 → 支付服务全款(进平台) → 站内通知达人 → 达人接受预约
→ 双方约定服务信息(私聊) → 达人【开始服务】⏱倒计时(按预约时长)
→ **不可提前结束**（自然走完倒计时）→ 倒计时结束自动转待确认
→ 用户确认 / 3天自动确认 → 结算(佣金归平台+服务费归达人) → 达人提现
→ 用户评价 👍好评/😐一般/👎差评（无需审核自动展示）→ 达人可回复

## 订单状态机
```
0 待支付 → 1 待接单(已支付) → 2 已接受(达人接单) → 3 服务中(⏱倒计时)
→ 4 待确认(倒计时结束) → 5 已完成(已结算)
→ 6 已取消/退款
```

## 数据库改动
`orders` 表新增 6 字段：
- `service_date DATETIME` 预约服务时间
- `service_duration INT` 预约时长(小时)
- `service_started_at DATETIME` 开始服务时间
- `service_ended_at DATETIME` 倒计时结束时间
- `confirm_deadline DATETIME` 确认截止时间
- `auto_confirmed TINYINT` 是否自动确认

`site_config`：
- `commission_rate=15` 平台抽成%(管理端可改)
- `auto_confirm_days=3` 自动确认天数
- `service_durations=1,2,3,4,6,8` 可选时长

## 后端 API
- `POST /api/order/create` — 加 service_date/service_duration 参数（预约下单）
- `PUT /api/playmate/accept-order/:id` — 接受预约 1→2（原接单，语义复用）
- `PUT /api/playmate/complete-order/:id` — **改造为「开始服务」** 2→3，写 started_at + ended_at=started+时长
- `PUT /api/playmate/reject-order/:id` — 拒绝预约 1→6（原 1→4 需改）
- `POST /api/order/confirm-service` — 用户确认完成 4→5，佣金结算
- `GET /api/order/detail?id=` — 订单详情（倒计时/评价状态）
- `POST /api/order/refund` — status=1 自动退为 6；status=2/3 记录申请等管理端
- `GET /api/cron/order-tasks` — 定时任务（crontab 每分钟）

## 定时任务逻辑（order_cron.py）
1. `status=3 AND service_ended_at <= NOW()` → status=4，写 confirm_deadline=now+auto_confirm_days，通知用户
2. `status=4 AND confirm_deadline <= NOW()` → status=5 自动确认，结算（佣金计算 + companion.total_income + log_money + 通知达人）

注册：main.py `from app.order_cron import cron_bp` + `app.register_blueprint(cron_bp)`；crontab：`* * * * * curl -s -m 20 http://127.0.0.1:5002/api/cron/order-tasks`

## 结算公式
```
达人收入 = 金额 × (1 - commission_rate%)
平台佣金 = 金额 × commission_rate%
写 orders.companion_income + settled=1 + settle_at=NOW()
```

## ⚠️ 关键陷阱（本次踩坑）

### 1. 后端文件重复追加导致 Flask 端点冲突
症状：`AssertionError: View function mapping is overwriting an existing endpoint function: order.confirm_service`
原因：用 `cat file >> app/order.py` 追加新 API 时，同一段代码被追加了两次（scp 到 /tmp 被拒后改用 stdin 传输，命令重复执行）
排查：`grep -n '@order_bp.route' app/order.py` 看到路由重复
修复：Python 脚本定位分隔注释第二次出现的位置，`lines[:second_start]` 截断删除重复段
预防：追加后必须 `grep -c '@order_bp.route'` 核对路由数量；导入测试 `python3.12 -c 'from main import app'` 必须通过才能重启

### 2. 远程文件传输 scp 到 /tmp 被拒
症状：`scp: failed to upload file ... to /tmp/`（Permission denied）
原因：服务器 /tmp 权限受限（sticky bit + 属主限制）
修复：改用 stdin 管道 `cat file | ssh root@host "cat > /root/file"`（传用户目录而非 /tmp）

### 3. 服务重启方式
- gunicorn 以 ubuntu 用户跑（systemd ttdazi.service, User=ubuntu）
- 根用户直接 `python3.12 -c 'from main import app'` 会 `ModuleNotFoundError: No module named 'flask'`（flask 在 ubuntu 的 ~/.local site-packages）
- 正确：`sudo -u ubuntu bash -c 'cd /opt/ttdazi/backend && /usr/bin/python3.12 -m py_compile ...'` 或 `sudo systemctl restart ttdazi`
- 导入测试也必须以 ubuntu 身份：`sudo -u ubuntu bash -c '... python3.12 -c "from main import app"'`

### 4. 现有状态映射需同步
- admin.py 的 status_map 原 `{0:pending,1:paid,2:active,3:completed,4:cancelled}` 需改为 `{0,1:paid,2:accepted,3:active,4:confirming,5:completed,6:cancelled}`
- playmate active-orders 查询 status=2 需改为 `IN (2,3,4)`
- 前端 Orders.vue tabs 和 statusText 映射同步更新

### 5. 评价三档（好评/一般/差评）
- review 表已有 order_id 绑定 + 达人回复（/reply 接口）
- 确认服务后才解锁评价入口（后端校验 status=5 + reviewed 标志）

## ✅ 全链路验证方法（无 UI 也能测通整条状态机）

后端接口 401 拦截需要有效 token，用代码直接生成（免登录）：

```bash
# 生成用户/达人 token（Server A 上，必须以 ubuntu 身份跑）
UTOKEN=$(cd /opt/ttdazi/backend && sudo -u ubuntu /usr/bin/python3.12 -c 'from app.token_auth import gen_token; print(gen_token(10001, "user"))' 2>/dev/null)
DTOKEN=$(cd /opt/ttdazi/backend && sudo -u ubuntu /usr/bin/python3.12 -c 'from app.token_auth import gen_token; print(gen_token(10002, "dazi"))' 2>/dev/null)
```

**状态机逐段驱动 + 数据库模拟时间**：
```bash
# 1. 预约下单（真实 API，验证预约字段写入）
curl -X POST -H "Authorization: Bearer $UTOKEN" -H 'Content-Type: application/json' \
  http://127.0.0.1:5002/api/order/create \
  -d '{"companion_id":2,"game_id":8,"amount":60,"type":"visitor_chat","service_date":"2026-08-05 14:00","service_duration":2}'
# 2. 模拟支付（直改库，绕开真实微信支付）
mysql -e "UPDATE orders SET status=1, paid_at=NOW(), companion_income=51.00 WHERE id=206"
# 3. 达人接受预约 → 开始服务（真实 API）
curl -X PUT -H "Authorization: Bearer $DTOKEN" http://127.0.0.1:5002/api/playmate/accept-order/206
curl -X PUT -H "Authorization: Bearer $DTOKEN" http://127.0.0.1:5002/api/playmate/complete-order/206
# 4. 模拟倒计时结束（改库把 ended_at 改为过去）→ 跑 cron → 应转 status=4
mysql -e "UPDATE orders SET service_ended_at=DATE_SUB(NOW(), INTERVAL 1 MINUTE) WHERE id=206"
curl http://127.0.0.1:5002/api/cron/order-tasks   # {"countdown_ended":1}
# 5. 用户确认 → 应 status=5 结算
curl -X POST -H "Authorization: Bearer $UTOKEN" -H 'Content-Type: application/json' \
  http://127.0.0.1:5002/api/order/confirm-service -d '{"order_id":206}'
# 6. 自动确认路径：改库 confirm_deadline 为过去 → cron → auto_confirmed=1
# 7. 退款路径：status=1 直接 refund → status=6

# ⚠️ 验证完必须清理测试数据（否则污染统计/达人累计收入）
mysql -e "DELETE FROM money_log WHERE order_id IN (206,207,208); DELETE FROM orders WHERE id IN (206,207,208)"
```

关键点：**支付、时间流逝用直改库模拟**，其余状态流转走真实 API——既验证了业务逻辑又不用真付钱；测试单会累加 companion.total_income/total_orders，测完必清。

## ⚠️ 前端改造要点（本次实现）
- Detail.vue：访客底部栏「💬 聊一聊」→「💬 咨询」+「📅 预约服务」按钮，goReserve() 跳 `/order/create?companion_id=X&owner=0&reserve=1`
- CreateOrder.vue：`isReserve` 模式显示时长选项（读 site_config service_durations）+ datetime-local 预约时间选择器 + `reserveAmount = hourlyPrice × duration`；提交走 order/create 带 service_date/service_duration 后跳 pay.openai2000.cn
- OrderDetail.vue 新页：状态卡片 + ⏱ 倒计时（setInterval 1s 本地计算，读 service_ended_at）+ 确认服务按钮 + 三档评价弹窗（good=5/normal=3/bad=1 映射 rating）
- Orders.vue：tabs 改 待支付/待接单/服务中/待确认/已完成/已取消，新增 confirmService/refundOrder/goDetail 按钮
- PlaymateOrders.vue：status=2 显示「▶️ 开始服务」、status=3 显示倒计时文案、status=4 显示「等待用户确认」；loadOrders 分区改 `[2,3,4]` 为进行中、`>=5` 为历史
- 路由：恢复被注释的 `/orders`，新增 `/order/detail`
- companion.py `my/orders` 的 SELECT 需补 service_date/service_duration/service_started_at/service_ended_at/confirm_deadline 字段
