# 财务审计日志完整参考

## money_log 表结构

```sql
CREATE TABLE money_log (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL COMMENT '用户ID',
    companion_id INT UNSIGNED DEFAULT 0 COMMENT '陪玩师ID',
    type VARCHAR(30) NOT NULL COMMENT '类型',
    amount DECIMAL(12,2) NOT NULL COMMENT '金额',
    fee DECIMAL(12,2) DEFAULT 0.00 COMMENT '手续费',
    relate_id INT UNSIGNED DEFAULT 0 COMMENT '关联ID',
    `desc` VARCHAR(255) DEFAULT '' COMMENT '描述',
    operator INT UNSIGNED DEFAULT 0 COMMENT '操作人(0=系统)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user (user_id), KEY idx_type (type), KEY idx_relate (relate_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财务日志';
```

## 完整日志类型

| type | 触发点 | amount含义 | fee含义 | 描述示例 |
|------|--------|-----------|---------|---------|
| `recharge` | 用户充值到账 | 充值金额 | 0 | 用户充值¥100.00（wechat） |
| `order_income` | 用户支付订单 | 订单总额 | 平台抽成 | 订单#168支付¥30.00，平台抽成¥6.00，陪玩师收入¥24.00 |
| `order_settle` | 3天结算到期 | 陪玩师收入 | 0 | 订单#168已结算¥24.00释放到可提现余额 |
| `withdraw_request` | 提交提现申请 | 提现总额 | 手续费 | 申请提现¥100.00，手续费¥3.00，到账¥97.00 |
| `withdraw_approve` | 管理员审核通过 | 到账净额 | 0 | 提现#7审核通过¥97.00 |
| `withdraw_reject` | 管理员审核拒绝 | 拒绝金额 | 0 | 提现#7审核拒绝¥100.00 |
| `admin_adjust` | 后台手动调整 | 调整后金额 | 0 | 测试订单#165 收入调整为¥1800 |

## 文件导入检查清单

| 文件 | log_money导入 | 状态 |
|------|--------------|------|
| order.py | ✅ | 支付时记录 |
| playmate_api.py | ✅ | 提现申请时记录 |
| admin.py | ✅ | 审核通过/拒绝时记录 |
| payment.py | ✅ | 备用支付路径 |
| wallet_api.py | ✅ | 充值时记录 |
| companion.py | ❌ 无需 | 无资金操作 |

## log_money 作用域陷阱

```python
# ❌ 错误 — w 和 amount 可能未定义
log_money(0, 0, 'withdraw_approve', amount, 0, wid, ...)

# ✅ 正确 — 安全取值
wd_amount = float(w['amount']) if w and w.get('amount') else 0
log_money(u['user_id'] if u else 0, w['companion_id'] if w else 0, 
         'withdraw_approve', wd_amount, 0, wid, ...)
```
