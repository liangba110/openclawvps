# 资金安全审计指南

## 审计范围

每次重大版本上线或用户反映资金问题时，执行以下审计。

## 数据库表审计

```sql
-- 检查所有财务相关表结构
DESC recharge;
DESC money_log;
DESC orders;
DESC withdraw;
DESC user;  -- 关注 balance 字段
DESC companion;  -- 关注 total_income, total_orders

-- 检查各表的状态分布
SELECT status, COUNT(*) as cnt, ROUND(SUM(amount),2) as total FROM recharge GROUP BY status;
SELECT type, COUNT(*) as cnt, ROUND(SUM(amount),2) as total FROM money_log GROUP BY type ORDER BY total DESC;
SELECT status, COUNT(*) as cnt, ROUND(SUM(amount),2) as total FROM orders GROUP BY status;
SELECT status, COUNT(*) as cnt, ROUND(SUM(amount),2) as total FROM withdraw GROUP BY status;
```

## 资金流向检查

### 充值到账
```
前端 POST /pay/wxpay/jsapi → 后端创建 recharge 记录(status=0)
  → 支付成功回调 → 后端 UPDATE recharge SET status=1
    → UPDATE user SET balance += amount
      → INSERT INTO money_log (type='recharge')
```

**检查点**：
- ✅ 每次充值到账必须有对应的 `money_log` 记录
- ✅ `user.balance` 增量 = `money_log` 中 `type='recharge'` 的总额
- ✅ 回调失败时有重试机制（Image beacon 3次 + 微信服务器通知）

### 订单支付
```
用户下单 → INSERT INTO orders (status=0)
  → 支付 → UPDATE orders SET status=1
    → INSERT INTO money_log (type='order_income', fee=平台佣金)
      → UPDATE companion.total_income += 收入
```

**检查点**：
- ✅ 平台佣金 = `commission_rate` (site_config，默认20%)
- ✅ 陪玩师收入 = `amount * (1 - commission_rate/100)`
- ✅ 每笔支付都有 `money_log` 记录
- ✅ 支付后通知用户和陪玩师

### 订单结算（3天冻结）
```
订单完成 → SET settle_at = DATE_ADD(NOW(), INTERVAL 3 DAY)
  → 结算脚本每5分钟执行 → SET settled=1
    → INSERT INTO money_log (type='order_settle')
```

**检查点**：
- ✅ 结算脚本存在并运行：`/opt/ttdazi/scripts/settle_orders.py`
- ✅ crontab 或 cronjob 配置每5分钟执行
- ✅ `order_settle` 记录金额 = 陪玩师实际可提现金额

### 提现
```
申请 → INSERT INTO withdraw (status=0, fee=手续费)
  → 管理员审核通过 → UPDATE withdraw SET status=1
    → INSERT INTO money_log (type='withdraw_approve', fee=手续费)
```

**检查点**：
- ✅ 手续费率 = `withdraw_fee_rate` (site_config，默认3%)
- ✅ 扣除后余额更新正确
- ✅ 提现审批有 `money_log` 记录
- ✅ 拒绝时有退回余额的 `money_log`

## site_config 财务配置

```sql
SELECT * FROM site_config WHERE `key` IN ('commission_rate','withdraw_fee_rate','withdraw_min');
```

| key | 默认值 | 说明 |
|-----|--------|------|
| commission_rate | 20 | 平台抽成比例(%) |
| withdraw_fee_rate | 3 | 提现手续费率(%) |
| withdraw_min | 100 | 最低提现金额(元) |

## 常见问题

### 充值到账失败

1. **order_no 为空**：pay.html 中 `var orderNo = getQuery('order_no')` 未从 API 响应提取
2. **跨域 XHR 被拦截**：pay.openai2000.cn → dazi.openai2000.cn 的 XHR 回调在微信浏览器中可能被拦截
3. **缺少 notify handler**：pay.openai2000.cn 未实现 `/wxpay/notify` 端点，微信服务器通知无处理

**修复**：
- order_no 从 API 响应 `res.data.order_no` 提取
- 用 Image beacon (`new Image().src`) 代替 XHR
- 添加 `/wxpay/notify` handler + `_notify_merchant` 回调

### trade_state 字段路径错误

微信支付查询结果可能被 `success()` 函数包裹，导致 `trade_state` 在 `data` 对象内：
```python
# 需要兼容两种格式
trade_state = result.get('trade_state', '') or (result.get('data') or {}).get('trade_state', '')
```

### 余额不匹配

```sql
-- 比较总充值 vs 总余额变化
SELECT ROUND(SUM(amount),2) as total_recharge FROM recharge WHERE status=1;
SELECT ROUND(SUM(balance),2) as total_balance FROM user WHERE status=1;
SELECT ROUND(SUM(amount),2) as total_order_income FROM money_log WHERE type='order_income';
SELECT ROUND(SUM(amount),2) as total_withdraw FROM withdraw WHERE status=1;
```

## 财务日志类型

| type | 含义 |
|------|------|
| recharge | 充值到账 |
| order_income | 订单收入（支付时） |
| order_settle | 订单结算（3天后释放） |
| withdraw_request | 提现申请（冻结） |
| withdraw_approve | 提现通过（扣减） |
| withdraw_reject | 提现拒绝（退回） |
| admin_adjust | 管理员手动调账 |
