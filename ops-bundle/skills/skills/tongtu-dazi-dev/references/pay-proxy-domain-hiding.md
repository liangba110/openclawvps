# 支付页域名隐藏（反代 /pay → 5005，用户不见 pay.openai2000.cn）— 2026-08

## 需求
支付页在 `pay.openai2000.cn`，用户点支付时地址栏显示该域名（品牌不统一）。
目标：支付全程只显示自有域名（`www.ttdazi.xyz/pay` 或 `dazi.openai2000.cn/pay`）。

## 架构（3 层改动）

### 1. 支付页模板 pay.html — 硬编码域名改动态
原 pay.html 把 `https://dazi.openai2000.cn` 硬编码在 7 处（goBack、轮询 order-status、
JSAPI/Native 下单、confirm 跳转）。改为动态：

```javascript
var API_BASE = location.origin;   // 跟随反代域名，绝不写死
// 替换：'https://dazi.openai2000.cn' → API_BASE
// 替换：'https://dazi.openai2000.cn/api/...' → API_BASE + '/api/...'
```

### 2. Nginx 反代（主站 + 国际站都要加）
⚠️ **坑：5005 的 `/pay`（无斜杠）返回 200，`/pay/`（带斜杠）返回 404**。
不能用 `location /pay/ { proxy_pass .../pay/; }`（会 404），也不能加 `return 302 /pay/`（死循环）。

正确写法（正则匹配，斜杠可有无）：
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
- Server B（主站）：加在 `/etc/nginx/sites-enabled/huizhiyunma` 的 dazi 块
- 服务器D（国际站）：加在 `/etc/nginx/sites-available/ttdazi-xyz` 的 `location /` 前
- 直连 Server A 的 5005（不要反代到 `pay.openai2000.cn` 域名——该域名 443 无 HTTPS 服务，SSL 握手失败 502）

### 3. 前端跳转 URL 全部改同域
前端所有 `https://pay.openai2000.cn/pay?token=...` 跳转改为：
```javascript
window.location.href = location.origin + '/pay?token=' + ...
```
涉及文件：CreateOrder.vue（2处）、MyDemands.vue（2处）、Recharge.vue（1处）。
验证：`grep -c 'pay.openai2000.cn/pay' dist/assets/*.js` → 0。

## ⚠️ 大坑：redirect 参数需 #/ 前缀（SPA hash 路由）

支付页 `goBack()` / 支付成功跳转用 `API_BASE + redirect`，但前端是 hash 路由：
- 前端传来的 redirect 是 `/companion/register?activated=1`、`/orders`（无 #）
- 直接拼 → `www.ttdazi.xyz/orders`（无 #）→ SPA 路由不匹配 → **页面错误/白屏**

### 修复（pay.html 加规范化函数）
```javascript
function normalizeRedirect(r) {
  if (!r) return '/#/';
  if (r.indexOf('#') === 0) return r;            // 已是 #/xxx
  if (r.indexOf('http') === 0) return r;         // 完整 URL
  return '/#' + (r.indexOf('/') === 0 ? r : '/' + r);  // /xxx → /#/xxx
}
// goBack 与支付成功跳转都用 normalizeRedirect(myRedirect)
```

### 服务端 confirm 接口同样要规范化
`pay_api.py wxpay_confirm()` 的 redirect_url 也需补 `#/` + 补全域名：
```python
if redirect_url and not redirect_url.startswith('http') and not redirect_url.startswith('#'):
    redirect_url = '/#' + (redirect_url if redirect_url.startswith('/') else '/' + redirect_url)
if not redirect_url.startswith('http'):
    redirect_url = request.host_url.rstrip('/') + redirect_url
```

## 验证清单
- `curl https://dazi.openai2000.cn/pay?token=test...` → 200（无 302/404）
- `curl ... | grep -c API_BASE` → 8（7 处替换 + 1 定义）
- `curl ... | grep 'pay.openai2000.cn'` → 仅注释残留（无实际跳转）
- 浏览器实测：地址栏显示自有域名，点「取消」跳转 `/#/...` 正常

## 附：支付页其他定制（同模板生效双站）
- 「🏠 返回首页」链接：`goHome() → location.href = API_BASE + '/#/'`，绝对定位左上角
- 取消按钮：紫色渐变 `linear-gradient(135deg,#667eea,#764ba2)` 白字（用户指定配色）
- 页面 logo：官方 App 图标（base64 内联，因支付服务无静态文件路由）
