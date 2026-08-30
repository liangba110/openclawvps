# 微信引流落地页（备案域名中转，规避微信风控）— 2026-08 上线

## 场景
公众号主站（备案域名 `dazi.openai2000.cn`）引流用户到国际站 `www.ttdazi.xyz`
（**.xyz 未备案 + 境外服务器**）。微信对未备案境外域名的风控行为：
- 微信内 JS 跳转（`location.href / location.replace / window.open / location.assign`）
  到境外域名 → 触发「非微信官方网页」风险提示
- 大量用户跳转还可能停用公众号菜单功能（`is_menu_open=0`，历史踩坑）

## 方案：备案域名下放静态落地页，微信内零跳转

| 环境 | 落地页行为 |
|---|---|
| 微信/QQ/钉钉内 | 3 步引导（右上角···在浏览器打开）+ 「复制链接」按钮，**零跳转** |
| 系统浏览器 | 「🚀 进入国际站」链接按钮（`<a href>`），**也零自动跳转**（2026-08 v3 修正） |

## ⚠️ 2026-08 v3 修正：全环境零自动跳转

用户明确否定了系统浏览器的自动跳转（"还是自动跳转页面不对啊"）。**最终形态：**
- 所有环境都不执行 JS 自动跳转（无 `setTimeout` + `location.replace`）
- 系统浏览器显示「🚀 进入国际站」**纯 `<a href>` 链接**（点击才跳转，不是 JS 跳转）
- 微信内隐藏该链接（避免点击触发风控），只留复制链接
- 验证：`grep -c 'location.replace\|location.href' landing.html` → 全文件 0（含非微信分支）

## 实现要点（2026-08 踩坑记录）

### 文件与路由
- 落地页：Server B `/home/ubuntu/ttdazi-frontend/landing.html`（www-data 属主）
- Nginx：主站 server 块加 `location = /landing { rewrite ^ /landing.html break; }`
- ⚠️ **Server B 实际生效配置是 `/etc/nginx/sites-enabled/huizhiyunma`，
  不是 `sites-available/ttdazi`**——两个文件都有 dazi server 块，改错文件不生效。
  症状：curl `https://dazi.openai2000.cn/landing` 返回的是 SPA index.html 而非落地页。
  排查：`sudo grep -n 'landing' /etc/nginx/sites-enabled/huizhiyunma`

### JS 双分支逻辑
```javascript
var isWechat = /MicroMessenger|WeChat/i.test(navigator.userAgent);
if (!isWechat) {
  // 系统浏览器：自动跳转（window.location.replace，不产生历史记录）
  setTimeout(function(){ window.location.replace('https://www.ttdazi.xyz/'); }, 1200);
  return;
}
// 微信/QQ/钉钉：只复制链接 + 引导，绝不跳转
```

### 硬性检查清单
- 微信分支零跳转调用：`grep -c 'window.location.replace\|location.href' landing.html` → 0
- 微信分支只允许 `copyLink()`；禁用「直接打开国际站」按钮（点击跳转同样触发风控）
- **复制按钮不显示链接文本**（用户明确要求）：点击只弹 toast「✅ 链接已复制」，
  不要 fallback 段落显示 `https://www.ttdazi.xyz/`
- 渲染验证：curl 无法执行 JS（自动跳转是 JS 行为），必须用真实浏览器；
  微信 UA 分支可用 node 注入 navigator/document mock 跑页面 JS 验证

### 公众号菜单
- `menu/create` 把「同途搭子」view 按钮 URL 设为 `https://dazi.openai2000.cn/landing`
- errcode 0 即生效；客户端需退出公众号重新进入刷新菜单缓存

## 合规定性
| 行为 | 性质 |
|---|---|
| 菜单放备案域名落地页 | ✅ 完全合规 |
| 复制链接 / 引导在浏览器打开 | ⚠️ 灰色地带，微信一般不处罚 |
| 微信内 JS 自动跳转境外域名 | ❌ 高风险，拦截/风险提示 |
| 系统浏览器打开境外站 | ✅ 不归微信管 |
