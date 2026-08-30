# 统一支付网关 - 接口规格与业务侧代码片段

2026-08-07 实测（官网 www.openai2000.cn 接入 ttdazi 支付网关，Node 后端 /data/web/huizhiyunma/backend）

## 网关侧（/opt/ttdazi/payment_service/）关键实现

- `wxpay.py`：APIv3 全封装（_build_token 签名、jsapi/native/h5/query/close/refund、verify_notify）
- `api.py` `/wxpay/notify`：验签 → AES-256-GCM 解密 resource（tag=密文尾16字节）→ 取 out_trade_no → UPDATE pay_order → 按前缀路由业务回调
- 回调路由代码（if/elif 链 + else 兜底，2026-08-28 最新版——新增前缀 = 在 elif 链纯追加分支，勿动现有分支，备份 api.py 后改）：
```python
if out_trade_no[:3] in ('TMP',) or out_trade_no[:2] in ('SO', 'HY'):
    # 官网订单：www.openai2000.cn
    _notify_merchant(out_trade_no, {'callback_url': 'https://www.openai2000.cn/api/payment/notify'}, amount_yuan)
elif out_trade_no[:2] in ('AE',):
    # AI电商站：ai.openai2000.cn
    _notify_merchant(out_trade_no, {'callback_url': 'https://ai.openai2000.cn/api/pay/notify'}, amount_yuan)
elif out_trade_no[:2] in ('SA',):
    # 软件授权充值站：softapi.openai2000.cn（FastAPI, /opt/software_auth, 端口5006）
    _notify_merchant(out_trade_no, {'callback_url': 'https://softapi.openai2000.cn/api/recharge/callback'}, amount_yuan)
if callback_url:
    _notify_merchant(...)
elif updated > 0:
    # ttdazi 订单（无前缀兜底，原逻辑 rowcount>0 才通知）
    _notify_merchant(out_trade_no, {'callback_url': 'https://dazi.openai2000.cn/api/pay/notify/recharge'}, amount_yuan)
```
- 回调路由表（完整）：PAY/RCH→dazi、TMP/SO/HY→www.openai2000.cn、AE→ai.openai2000.cn、SA→softapi.openai2000.cn；**无前缀订单被 else 兜底发到 dazi**——新业务订单号必须带专属前缀（如 SA+timestamp+随机），否则钱付了 VIP 不开
- `_notify_merchant` 回调请求带 `X-Pay-Token: huizhiyun_gateway_2026`（2026-08 新增防伪造；接收方必须校验该头）
- 网关是 systemd `ttdazi-pay.service`（gunicorn -w 2），改代码后 `sudo systemctl restart ttdazi-pay`

## 业务侧（Node/Express）核心片段

### OAuth 静默授权
```js
// GET /oauth/url?order_no= → 前端跳这个 URL
const url = `https://open.weixin.qq.com/connect/oauth2/authorize?appid=${WX_APPID}&redirect_uri=${encodeURIComponent(OAUTH_REDIRECT)}&response_type=code&scope=snsapi_base&state=${encodeURIComponent(order_no)}#wechat_redirect`;
// GET /oauth/callback?code&state=order_no
const d = await (await fetch(`https://api.weixin.qq.com/sns/oauth2/access_token?appid=${WX_APPID}&secret=${WX_SECRET}&code=${code}&grant_type=authorization_code`)).json();
res.setHeader('Set-Cookie', `hz_openid=${d.openid}; Path=/; HttpOnly; Max-Age=7200; SameSite=Lax`);
res.redirect(302, `https://www.openai2000.cn/${page}?pay=${order_no}`);
```

### jsapi 下单（幂等 + 防重复拉起）
```js
// 1. 先查微信侧状态
const qd = await (await fetch(`${PAY_GATEWAY}/api/v1/wxpay/query?out_trade_no=${order_no}`)).json();
const tradeState = (qd && qd.data && qd.data.trade_state) || '';
// 2. 已支付 → 本地同步，返回 already_paid（前端不拉起支付直接成功）
if (tradeState === 'SUCCESS') { /* UPDATE 本地订单已支付 */ return res.json({ code:0, data:{ already_paid:true } }); }
// 3. 未支付旧单 → 先关单（微信 out_trade_no 唯一）
if (['NOTPAY','USERPAYING','PAYERROR'].includes(tradeState)) {
  await fetch(`${PAY_GATEWAY}/api/v1/wxpay/close`, { method:'POST', body: JSON.stringify({out_trade_no: order_no}), headers:{'Content-Type':'application/json'} });
}
// 4. 调网关下单（amount 传元，网关内部转分）
const gd = await (await fetch(`${PAY_GATEWAY}/api/v1/wxpay/jsapi`, { method:'POST', headers:{'Content-Type':'application/json'},
  body: JSON.stringify({ openid, out_trade_no: order_no, amount: amountFen/100, subject }) })).json();
res.json({ code:0, data: gd.data }); // {appId,timeStamp,nonceStr,package,paySign}
```

### 网关回调（必须校验 token + 幂等）
```js
if (req.headers['x-pay-token'] !== PAY_NOTIFY_TOKEN) return res.status(403).json({code:-1,message:'未授权'});
// 按订单前缀选表（TMP→template_orders / SO→package_orders / HY→payment_orders）
// 幂等更新：UPDATE 表 SET status=已支付, pay_method='wechat', paid_at=NOW() WHERE order_no=? AND status=0
// 成功才发邮件通知（sendNotify），重复通知不重复发
res.json({ code: 0 });
```

### 前端（Vue3）startPay 防重复拉起
```js
async function startPay(orderNo) {
  if (!/MicroMessenger/i.test(navigator.userAgent)) { payState.value = 'needWechat'; return; }
  try { sessionStorage.setItem('pay_started_' + orderNo, '1'); } catch(e) {}   // 防重复拉起标记
  const r = await axios.post('/api/payment/jsapi', { order_no: orderNo });
  if (r.data.code === -1 && r.data.oauth) { window.location.href = (await axios.get('/api/payment/oauth/url', {params:{order_no: orderNo}})).data.data.url; return; }
  if (r.data.data.already_paid) { startPoll(orderNo); return; }                 // 已支付：只轮询
  window.wx.chooseWXPay({ appId, timeStamp, nonceStr, package, signType:'RSA', paySign,
    success: () => startPoll(orderNo),
    fail: (err) => { if (/cancel/i.test(err.errMsg||'')) payState.value='closed'; else startPoll(orderNo); } });
}
// onMounted ?pay= 回跳：status>=1→success；sessionStorage 有标记→只轮询；否则 startPay
```

## 环境变量（官网 .env 新增）
```
WX_APPID=wxd274e174ddadd4cb
WX_SECRET=<公众号Secret>
PAY_GATEWAY=https://pay.openai2000.cn
```
CSP：index.html 引入微信 JS-SDK 后，server.js 的 CSP `script-src 'self' 'unsafe-inline'` 需加 `https://res.wx.qq.com`。

## 订单表 status 语义（官网）
- template_orders（pay_system_db）：0待支付 → 1已付待确认 → 2已确认（可下载）
- package_orders（huizhiyunma_db）：0新单 → 1已支付（无 paid_at 列，状态查询 SQL 勿 select paid_at）
- payment_orders：0待支付 → 2已确认（JSAPI 到账直接置 2）

## 验证清单（端到端）
1. 无 openid 调 jsapi → `NEED_OAUTH`；伪造 token 调 notify → 403
2. 正确 token + 真实订单 → 订单 status 更新 + 邮件；重复 notify → 幂等不重复处理
3. TMP/SO/HY 三表链路各自测一遍（建测试订单→notify→状态→清理测试数据）
4. 全站回归 200 + 百度 UA SEO 版 200；测试后清 .well-known 探测文件与测试订单
