# 微信支付最终方案（2026-07-14 确定版）

## 架构图

```
dazi.openai2000.cn 信息服务页
  → 跳转 pay.openai2000.cn/pay
    → WeixinJSBridge.invoke('getBrandWCPayRequest')
      → 支付成功
        → 跳回 dazi.openai2000.cn/api/pay/wxpay/confirm
          → 服务器查询微信 → 更新余额 + money_log
            → 跳回信息服务页
```

## 关键教训

### 1. 不要在前端跨域 XHR 回调
**失败路径：** pay.html 收到支付成功 → XHR POST 到 dazi.openai2000.cn → 被微信浏览器 CORS 拦截
**成功路径：** pay.html 收到支付成功 → location.href 跳转到 confirm 端点 → 服务端查询 WeChat API

### 2. 不要重复创建订单
**失败路径：** 前端先创建订单(api.post('/pay/wxpay/jsapi')) → 然后跳转 pay 页 → pay 页又创建一次 → 双订单
**成功路径：** 前端只跳转(不创建) → pay 页创建订单 → 创建充值记录 + JSAPI → 一次创建

### 3. 微信支付回调通知
`pay.openai2000.cn/api/v1/wxpay/notify` 处理 WeChat 异步通知 → `_notify_merchant` → `dazi.openai2000.cn/api/pay/notify/recharge`

### 4. JSAPI 参数组装
支付服务返回 JSAPI 参数必须包含：
- `appId` | `timeStamp`(字符串) | `nonceStr` | `package`(`prepay_id=xxx`) | `signType`(`RSA`) | `paySign`

### 5. 回调通知后端处理
`/api/pay/notify/recharge` 支持 GET 和 POST。流程：
1. 查询 recharge 表找到 order_no
2. UPDATE status=1, paid_at=NOW()
3. UPDATE user SET balance=balance+amount
4. INSERT INTO money_log (type='recharge')

### 6. JS接口安全域名
必须同时添加：`dazi.openai2000.cn` + `pay.openai2000.cn`

### 7. 信息服务套餐模式
Recharge.vue 展示套餐卡片而非简单金额输入：
- `{ name: '单次匹配', price: 10 }` | `{ name: '包月无限', price: 199, popular: true }`
