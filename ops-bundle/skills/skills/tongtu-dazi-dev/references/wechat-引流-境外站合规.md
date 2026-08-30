# 微信引流到境外国际站的域名合规（提示不安全/报错根因与方案）

## 场景
公众号主站（dazi.openai2000.cn，国内备案域名）引流用户到境外国际站
（www.ttdazi.xyz，.xyz 域名 + 香港服务器，未备案）完成使用，微信内置浏览器
提示"非微信官方网页"/风险拦截/报错。

## 根因
- **微信内置浏览器对境外未备案域名会提示风险**——这是根因，与服务器配置无关。
  检查顺序：证书链 → 域名备案 → 跳转链路。
- 证书链必须 **RSA + ISRG Root X1**（微信 X5 内核不认 ECDSA 证书），
  验证：`echo | openssl s_client -connect IP:443 -servername 域名 -showcerts | grep -E "s:|i:"`
  需看到链尾 `i:C = US, O = Internet Security Research Group, CN = ISRG Root X1`。
- 服务器在境外（香港等）= 域名无法 ICP 备案，微信信任度低。

## 三个方案（按见效速度排序）
| 方案 | 做法 | 优点 | 缺点 |
|:-----|:-----|:-----|:-----|
| A 备案域名中转页（推荐先做） | 公众号入口先打开主站落地页 dazi.openai2000.cn/landing（备案域名零提示），页面引导用户"右上角···在浏览器打开"或复制链接到系统浏览器访问国际站 | 1小时内上线，不碰 DNS/不改国际站 | 用户多点一步 |
| B 域名备案（根治） | ttdazi.xyz 完成 ICP 备案（域名实名 + 国内服务器接入腾讯云） | 备案后微信内直接打开无提示 | 周期 2-3 周，.xyz 备案要求主体一致 |
| C 备案子域名反代 | 用 ttdazi.openai2000.cn（已备案）Nginx 反代服务器D 内容 | 微信内零提示 | 用户看到的是 openai2000.cn 非 ttdazi.xyz，品牌不符 |

建议：先方案 A 快速见效，同时启动方案 B 长期根治。**先出方案让用户确认再执行**，
不要直接动手改配置。

## 方案A 落地实现（已上线验证，2026-08，v3 最终版）

落地页文件 `/home/ubuntu/ttdazi-frontend/landing.html`（放主站前端根目录，
Nginx `location / { try_files ... }` 自动服务，无需额外 location）：

### ⚠️ 核心原则：微信内零跳转，全环境不自动跳转（用户明确要求）

v1/v2 曾做"非微信浏览器自动 window.location.replace 跳转"，用户否决：
**"3秒后自动跳转国际站 这个微信会提示不安全吧"**。微信内任何 JS 跳转到
境外未备案域名（location.replace/href/open/assign）都可能触发风控提示。
最终 v3 全环境去掉自动跳转，改为手动触发：

- 微信/QQ/钉钉内 → 隐藏"进入国际站"链接，显示 3 步引导卡（右上角···→在浏览器打开）
  + 「复制链接」按钮（`navigator.clipboard` + `execCommand('copy')` 双降级）
  - 验证微信分支零跳转：`grep -c 'window.location.replace\|location.href' landing.html` 应为 0
- 系统浏览器 → 显示「🚀 进入国际站」按钮 = 纯 `<a href="https://www.ttdazi.xyz/">`
  链接（非 JS 跳转，点击才进，微信外无风险提示）
- UA 检测：`/MicroMessenger|WeChat/i.test(navigator.userAgent)`
- 视觉：深蓝紫渐变背景 + 蓝紫渐变圆角 Logo 卡 + 三步行引导，移动端优先
- 用户要求（2026-08）：点「复制链接」后**底部不要显示链接文本**（去掉 fallback 元素
  `<p class="fallback">https://www.ttdazi.xyz/</p>` 及其 JS 显示调用、CSS），
  只保留「✅ 链接已复制」toast —— 改完 `grep -c 'fallback' landing.html` 应为 0

路由：在 **huizhiyunma**（不是 sites-available/ttdazi）dazi server 块内加
`location = /landing { rewrite ^ /landing.html break; }`，reload 生效。
带参数访问验证绕过浏览器缓存：`/landing?v=20260803a`。
⚠️ 用户手机仍看到旧行为 = 微信缓存旧版，退出微信重进/清缓存，不是配置问题。

### 调试方法（无法真机微信时）
- curl 模拟微信 UA 看返回内容：`-A "Mozilla/5.0 (Linux; Android 10; wechat) AppleWebKit/537.36 MicroMessenger/8.0.49"`
- 用 node 把 `<script>` 内容 `new Function('navigator','document','window','setTimeout', js)` 注入模拟 UA 跑一遍，确认微信分支不触发跳转、按钮切换逻辑正确
- 浏览器工具实测普通环境：页面不自动跳转、显示按钮，即为正确

## 相关已知事实
- 微信对未备案域名不是一律拦截，但境外 .xyz 新后缀 + 香港服务器命中风险提示概率高
- 公众号"业务域名/JS接口安全域名"白名单仅对已备案域名生效，未备案域名无法加白
- 用户曾明确要求"先出个方案，我确认后再执行"——引流改造属于影响面大的变更，
  必须出方案确认，不能直接动手
