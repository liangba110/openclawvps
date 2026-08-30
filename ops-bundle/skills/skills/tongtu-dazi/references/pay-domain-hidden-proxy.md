# 支付域名隐藏（/pay 反代，2026-08 实施）

**目标**：用户支付时地址栏不显示 `pay.openai2000.cn`（品牌统一 + 避免微信对第三方域名提示）。

## 三层改动

### 1. 支付页模板 pay.html（支付服务侧）
路径：`/opt/ttdazi/payment_service/templates/pay.html`（Server A）
- 所有硬编码 `'https://dazi.openai2000.cn'` → 动态 `API_BASE = location.origin`（约7处）
- 这样反代到哪个域名，JS 里的 API 请求/跳转就跟随哪个域名
- 改后需重启支付服务：`kill -HUP $(pgrep -f 'gunicorn -b 0.0.0.0:5005')`（systemd 单元 ttdazi-pay.service）

### 2. Nginx 反代（Server B huizhiyunma + 服务器D ttdazi-xyz）
```nginx
location ~ ^/pay(/.*)?$ {
    proxy_pass http://42.193.113.230:5005/pay$1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 60s;
}
```
- 支付服务在 Server A:5005，**直连 5005 而非 pay.openai2000.cn**
- 陷阱1：pay.openai2000.cn 解析到 42.193.113.230:443，但 443 无 HTTPS 服务 → SSL handshake failed → 502。必须 `proxy_pass http://42.193.113.230:5005`
- 陷阱2：`/pay`(无斜杠)=200，`/pay/`(带斜杠)=404（Flask 路由是 `/pay`）
- 陷阱3：不要写 `location = /pay { return 302 /pay/; }` → 302 到 /pay/ 又 404 死循环
- 正确写法：正则 `location ~ ^/pay(/.*)?$` + `proxy_pass .../pay$1`（不带尾部斜杠）

### 3. 前端跳转（5处）
`CreateOrder.vue`(2处)、`MyDemands.vue`(2处)、`Recharge.vue`(1处)：
`window.location.href = 'https://pay.openai2000.cn/pay?token='` → `location.origin + '/pay?token='`

## 验证
```bash
curl -s https://dazi.openai2000.cn/pay?token=t&amount=79&order_no=x&subject=s&redirect=/orders  # 200
curl -s https://www.ttdazi.xyz/pay?...  # 200（国际站同样生效）
# 页面含 8 处 API_BASE；grep -c 'pay.openai2000.cn/pay' 构建产物 = 0
```

## 附带修复
Recharge.vue 充值主题从「信息匹配服务」→「余额充值」（信息匹配服务费已整体取消）。

## ⚠️ SPA hash 路由 redirect 规范化（2026-08-03 取消支付页面错误根因）

**症状**：支付页点「取消」（或支付成功回调）后页面错误/白屏。

**根因**：redirect 参数是**无 `#/` 前缀的 history 路径**（如 `/companion/register?activated=1`、`/orders`），而前端是 **hash 路由 SPA**。跳转 `API_BASE + redirect` 变成 `www.ttdazi.xyz/orders`（无 #）→ SPA 无法匹配 → 错误页。来源：`CreateOrder.vue` 里 `redirect = '/companion/register?activated=1'`、预约支付 `redirect='/orders'`、需求发布 `redirect='/my-demands'`——全是无 hash 路径。

**修复**（两处必须都改，否则取消按钮好了支付成功回调还是坏的）：

1. **pay.html** 加 `normalizeRedirect()`，取消按钮 + 支付成功跳转都用它：
```javascript
function normalizeRedirect(r) {
  if (!r) return '/#/';
  if (r.indexOf('#') === 0) return r;           // 已是 #/xxx
  if (r.indexOf('http') === 0) return r;        // 完整URL
  return '/#' + (r.indexOf('/') === 0 ? r : '/' + r);  // /xxx → /#/xxx
}
```
`goBack()` 和支付成功 `setTimeout` 里的 `location.href = API_BASE + myRedirect` 都改为 `API_BASE + normalizeRedirect(myRedirect)`。

2. **pay_api.py 的 `wxpay_confirm`**（服务端 redirect）：函数开头对 `redirect_url` 规范化——无 http 且无 # 时补 `/#`，再补全当前域名（`request.host_url.rstrip('/') + redirect_url`）。默认值也从硬编码 `'https://dazi.openai2000.cn/#/recharge'` 改为 `'/#/recharge'`（跟随访问域名）。

**验证**：改后浏览器实测 `redirect=/companion/register%3Factivated%3D1` 点取消 → 跳 `/#/companion/register`（实名认证页）；`redirect=/orders` 走 confirm 接口 → 跳 `/#/orders`。pay.html 和 pay_api.py 都要重启对应服务才生效。

**通用教训**：SPA 是 hash 路由时，**任何外部页面/服务端接口构造的跳转地址都必须带 `#/`**——支付页、回调接口、落地页跳转都容易踩。前端代码里 redirect 参数应直接写 `/#/xxx` 格式，或由接收方统一规范化。

## 支付页 UI 定制（2026-08-03）

- **logo 替换**：用 `public/logo/logo-app.svg`（方形 App 图标）。SVG 是纯文本，**可直接内联进 pay.html 模板**（`<div class="logo">{svg内容}</div>`），无需给支付服务加静态文件路由。尺寸样式：`.logo svg{width:80px;height:80px;border-radius:20px;box-shadow:0 8px 24px rgba(102,126,234,.3)}`（SVG 本身 180×180 viewBox，CSS 缩放显示）
- **返回首页链接**：卡片内 `position:relative` + 左上角 `<a onclick="goHome()">🏠 返回首页</a>`，函数体 `location.href = API_BASE + '/#/'`（同域首页）
- **按钮主题**：改 `.btn-default`（取消按钮）可换主题渐变 `background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none`
- 改 pay.html 后必须 `kill -HUP` 支付服务 master 才生效；主站+国际站共用同一模板
