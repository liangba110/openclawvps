# 微信引流落地页方案（备案域名中转）

## 背景
公众号主站 `dazi.openai2000.cn`（已备案）引流客户到国际站 `www.ttdazi.xyz`（境外 .xyz 未备案）。微信对境外未备案域名的跳转有风控拦截，直接跳转会提示「该网页包含不安全内容」或被拦截。

## 铁律：微信内任何到境外未备案域名的跳转都会触发风控
- JS 跳转（location.href / location.replace / window.open）❌ 全部触发
- 按钮点击跳转 ❌ 同样触发（v1 版「直接打开国际站」按钮被否决）
- **唯一安全做法：微信内页面永远停留在备案域名，零跳转**

## 落地页最终方案（v3，已验证）

入口：`https://dazi.openai2000.cn/landing`（备案域名，微信零提示）

| 环境 | 显示内容 | 行为 |
|---|---|---|
| 微信/QQ/钉钉内 | 3步引导（右上角···在浏览器打开）+ 「复制链接」按钮 | 零跳转，只复制链接 |
| 系统浏览器 | 「🚀 进入国际站」按钮（纯 `<a>` 链接） | 不自动跳转，点击才进入 |

关键代码：
```javascript
var isWechat = /MicroMessenger|WeChat/i.test(navigator.userAgent);
var inOtherApp = /DingTalk|QQ\/|Alipay/i.test(navigator.userAgent);
// 不做任何自动跳转！
if (isWechat || inOtherApp) {
  // 显示复制链接按钮，隐藏「进入国际站」（避免微信风控）
} else {
  // 系统浏览器：显示 <a href="https://www.ttdazi.xyz/"> 链接按钮
}
```

- 「进入国际站」必须是普通 `<a>` 链接（非 JS 跳转），微信内自动隐藏它
- 微信内只有「复制链接」按钮 + 右上角···引导，页面绝不发起外部跳转请求
- 复制链接后**不要显示链接文本**（用户要求底部不出现 https://www.ttdazi.xyz/）——只弹「✅ 链接已复制」

## 演进教训（v1→v2→v3）
- v1：有「直接打开国际站」按钮 + 3秒自动跳转 → 用户否决：「微信会提示不安全吧」
- v2：微信内零跳转，但系统浏览器仍自动跳转 → 用户仍不满：「还是自动跳转页面不对」
- v3（最终）：**全环境零自动跳转**，系统浏览器给链接按钮，微信内给复制链接
- 教训：用户对「自动跳转」零容忍，即使只在系统浏览器跳转也不行。落地页统一静态展示 + 手动点击。

## 部署位置
- 服务器 B `/home/ubuntu/ttdazi-frontend/landing.html`（主站 Nginx root 目录）
- Nginx 路由：`location = /landing { rewrite ^ /landing.html break; }`
- ⚠️ 实际生效的 Nginx 文件是 `/etc/nginx/sites-enabled/huizhiyunma`（含 dazi.openai2000.cn server 块），不是 sites-available/ttdazi！改错文件不生效
- 验证：`curl -s https://dazi.openai2000.cn/landing` 应返回落地页 HTML；普通浏览器打开应显示按钮（不跳转）

## 公众号菜单指向
`menu/create` 接口更新「同途搭子」按钮 URL → `https://dazi.openai2000.cn/landing`，`errcode:0` 即生效（手机退出公众号重进刷新菜单缓存）。

## 跨站跳转：同构前端双域名部署时，绝对跳转 URL 必须按 hostname 分流 ⚠️

国际站和主站共用**同一份 Vite 构建产物**，前端代码 `location.hostname` 可以区分当前站点。凡是「支付后回跳」「授权后回跳」这类**绝对 URL**，在主站是相对路径（`/xxx`），在国际站必须拼完整域名，否则支付完跳到主站去了。

```javascript
// CreateOrder.vue 达人认证支付后回跳（2026-08-03 实战）
const site = location.hostname === 'www.ttdazi.xyz' ? 'https://www.ttdazi.xyz' : ''
const redirect = owner ? (site + '/#/companion/register?activated=1') : ('/service?companion_id=...')
```

**排查/验证**：改完构建后直接看产物 chunk 是否含域名判断——`grep -oE 'location\.hostname[^;]{0,60}' /var/www/ttdazi/assets/CreateOrder-*.js` 应出现 `location.hostname==="www.ttdazi.xyz"`。

**通用规则**：同构前端里任何会跳回站内的绝对 URL（支付 redirect、OAuth 回跳 redirect、下载页链接），统一套这个 hostname 分流模式；相对路径（`router.push('/xxx')`）不用管——SPA 路由天然跟随当前域名。

## 合规判断
- 公众号菜单放备案域名落地页：✅ 完全合规
- 落地页让用户复制链接去浏览器打开：⚠️ 灰色地带但一般不处罚
- 微信内 JS 自动跳转境外域名：❌ 高风险，会被拦截
- 系统浏览器打开国际站：✅ 不归微信管
