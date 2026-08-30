# 服务端支付确认模式

## 问题

前端 `WeixinJSBridge.invoke('getBrandWCPayRequest')` 支付成功后，前端回调 callback 通知后端到账不可靠：
- 跨域 XHR 被微信浏览器拦截
- Image beacon 虽无跨域问题但浏览器可能延迟发送
- pay.openai2000.cn 页面在支付成功后可能被用户关闭

## 解决方案：服务器端确认

### 流程

```
支付成功 → 页面跳转到 /api/pay/wxpay/confirm?order_no=xxx
  → 后端调用 WeChat Pay API 查询订单状态
    → 确认已支付 → UPDATE recharge + UPDATE balance + money_log
      → 302 跳回 /#/recharge?paid=1
```

### 后端端点

```python
@PAY_API.route('/wxpay/confirm', methods=['GET'])
def wxpay_confirm():
    order_no = request.args.get('order_no', '')
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, amount, user_id FROM recharge WHERE order_no=%s", (order_no,))
            row = cur.fetchone()
            if not row:
                return redirect('https://dazi.openai2000.cn/#/recharge')
            if row['status'] == 1:
                return redirect('https://dazi.openai2000.cn/#/recharge?paid=1')
            # 查询微信支付结果
            req = urllib.request.Request(
                f'https://pay.openai2000.cn/api/v1/wxpay/query?out_trade_no={order_no}')
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read().decode())
            # trade_state 可能在 result 顶层或 result['data'] 中
            trade_state = result.get('trade_state', '') or (result.get('data') or {}).get('trade_state', '')
            if trade_state == 'SUCCESS':
                cur.execute("UPDATE recharge SET status=1, paid_at=NOW() WHERE order_no=%s", (order_no,))
                cur.execute("UPDATE `user` SET balance=balance+%s WHERE id=%s", (row['amount'], row['user_id']))
                from app.money_log import log_money
                log_money(row['user_id'], 0, 'recharge', float(row['amount']), 0, order_no,
                         f'微信充值¥{float(row["amount"]):.2f}', row['user_id'])
                conn.commit()
                return redirect('https://dazi.openai2000.cn/#/recharge?paid=1')
    finally:
        conn.close()
    return redirect('https://dazi.openai2000.cn/#/recharge')
```

### 要点

- 端点不要加 `@login_required`（页面跳转会丢失 token 头），用 order_no 查表
- 调用 `pay.openai2000.cn/api/v1/wxpay/query` 查询支付结果
- `trade_state` 可能在 result 顶层或 `result['data']` 中，两种情况都要处理
- 双重保障：服务器端确认 + 微信服务器通知 `/wxpay/notify` → `_notify_merchant`

### 查询 API 返回格式

```json
// 支付服务 wx_query 端点返回
{"code":0,"data":{"trade_state":"SUCCESS","out_trade_no":"..."}}

// 或直接 success(result) 包装
{"code":0,"data":{"code":"FAIL","message":"..."}}  // 订单不存在
```

trade_state 读取必须兼容两种格式：
```python
trade_state = result.get('trade_state', '') or (result.get('data') or {}).get('trade_state', '')
```
