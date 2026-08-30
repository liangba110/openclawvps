# 管理端财务明细 API

## GET /api/admin/finance

**参数：** `page`(默认1), `page_size`(默认20), `type`(all/payment/withdraw), `keyword`

**返回：**
```json
{
  "items": [
    {
      "id": 1,
      "tx_type": "payment",      // payment=消费, withdraw=提现
      "tx_no": "PAY20260701...",
      "amount": 26.00,
      "user_name": "小甜心",
      "user_phone": "138****0000",
      "method": "wechat",
      "order_id": 93,
      "remark": "订单#93支付",
      "created_at": "2026-07-01 12:54:41"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "stats": {
    "pay_total": 2600.00,   // 总收入
    "wd_total": 500.00,     // 总提现
    "net": 2100.00          // 净收入
  }
}
```

## POST /api/admin/user/\<uid\>/bind-phone

```json
// body: {"phone": "13800138000"}
// success: {"code": 0, "msg": "绑定成功"}
// error: {"code": 1, "msg": "该手机号已被其他用户绑定"}
// error: {"code": 1, "msg": "该用户手机号已绑定，不可修改"}
```

## 邮箱注册修复

```sql
-- register-by-email INSERT 必须包含 email 列
INSERT INTO user (username, phone, email, password, nickname, role, status) VALUES (%s, %s, %s, %s, %s, 'user', 1)
```

admin 用户列表：`SELECT id, phone, phone_bound, email, username, ... FROM user`
前端展示：`u.email || '无邮箱'`
