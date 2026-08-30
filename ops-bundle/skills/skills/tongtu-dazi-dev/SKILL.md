---
name: tongtu-dazi-dev
description: Develop, debug, fix, or deploy the 同途搭子 (Tongtu Dazi) gaming companion platform. Covers Flask+Vue3+Vant+MySQL dual-server architecture, frontend component patterns, API integration, deployment workflow, and project-specific pitfalls.
---

# 同途搭子开发技能

## 铁律：新项目不得影响现有系统

用户要求：开发任何新项目时，**严禁修改**同途搭子（ttdazi）、AI建站（aiweb）以及其他现有项目的：
- 支付系统
- 数据库（数据结构、内容）
- 网站代码
- Nginx 配置（除非明确要求）
- 域名/DNS 配置

每个新项目必须完全独立：
- 新数据库（CREATE DATABASE）
- 新后端端口（不与 5002/5003/5005 冲突）
- 新域名或子域名
- 新代码目录（`/opt/<project>/`）
- 新 Nginx server block

部署新项目后，必须验证现有项目仍正常工作：
```bash
curl -s http://127.0.0.1:5002/api/health  # ttdazi
curl -s http://127.0.0.1:5003/api/health  # aiweb
```

## 品牌文字全站替换（公司名/版权名改版）

用户要求"网站上所有 X 换成 Y"（如公司名/品牌改名）时，必须**全栈覆盖**才算完成，只改前端 dist 不算：
- ⚠️ **三端都要检查，Server B `/home/ubuntu/ttdazi-frontend/` 才是主站 dazi.openai2000.cn 的线上真实前端**
  （Server A 的 `/opt/ttdazi/frontend/dist/` 只是构建产物，服务器D 的 `/var/www/ttdazi/` 是国际站）。
  2026-08 教训：只替换了 A 的 dist + D 的 assets，用户报"首页显示的不对"——因为 Server B 线上页脚
  仍是旧品牌词。**替换顺序：先 `npm run build`（A 上有 node/node_modules）→ 同步 dist 到 B（保留 landing.html）
  → 再同步到 D → curl + 浏览器实测两个域名页脚。**
- 数据库协议（`agreement.content`）、后端代码（wx_message.py/wx_code.py/faq.py/user.py）里也可能有品牌词，
  替换后必须 `grep -c '旧词'` 全库+全代码为 0，并 `python3 -m py_compile` 校验后端语法
- ⚠️ **gunicorn 重启必须用 HUP 优雅重启，禁止 `pkill -f 'gunicorn main:app'`**——该 pattern 会匹配到
  SSH 命令自身（命令行里含同样的字符串），把自己的 SSH 会话杀掉。正确姿势：
  `MASTER=$(pgrep -f 'gunicorn main:app' | head -1) && sudo kill -HUP $MASTER`
- ⚠️ **改多行 Python 字符串字面量（f-string 拼接）禁止用 sed 删行**——删掉一行会把左括号 `(` 悬空，
  直接 SyntaxError 导致整个 worker 启动失败。用 Python 脚本 `open().read().replace(old, new)` 精确替换。
- 微信引流到境外国际站（公众号 → 境外 .xyz/香港服务器）提示不安全的问题与方案，见 📖 `references/wechat-引流-境外站合规.md`
- 用户对"全站替换"的验收标准：浏览器实测页脚/协议显示新品牌词 + 无 JS 错误，交付前必须 curl + 浏览器双验证
- ⚠️ **hash 缓存陷阱**：只 sed 改线上 dist JS（文件名 hash 不变）用户端不会更新——
  assets 带 `Cache-Control: public, immutable` + `max-age=604800`，浏览器 7 天不重新拉取。
  必须 **`npm run build` 重新构建生成新 hash 文件名**（服务器A `/opt/ttdazi/frontend/` 有 node v22 + node_modules，约 16s），
  再把新 dist 部署到三个位置。验证：`grep -oE 'assets/[A-Za-z0-9_-]+\.js' index.html` 看 hash 是否变化
- 改后端代码后优雅重启 gunicorn：`kill -HUP <master_pid>`（`pgrep -f 'gunicorn main:app' | head -1`），
  ⚠️ **不要用 `pkill -f 'gunicorn main:app'`**——会连自己的 SSH 会话一起杀掉（exit -15），
  且 pkill 后必须重新 nohup 启动。改 Python 多行 f-string 拼接用 python replace 而非 sed 删行（sed 删行会破坏括号导致 SyntaxError）
- 前端 dist：**三个位置都要改**：
  - 服务器B `/home/ubuntu/ttdazi-frontend/`（**主站 dazi.openai2000.cn 线上真实服务目录**，最容易漏）
  - 服务器D `/var/www/ttdazi/assets/`（国际站）
  - 服务器A `/opt/ttdazi/frontend/dist/assets/`（构建产物，同名 hash chunk）
- ⚠️ **immutable hash 缓存陷阱**：dist JS 文件名带内容 hash（如 Home-CsjOjG0H.js），直接 sed 改内容用户仍看旧版（浏览器 immutable 缓存不重新拉取）。**必须重新构建**让 hash 变化（服务器A `npm run build` 约16秒），再三端同步。完整流程见 📖 `references/前端hash缓存与三端部署.md`
- 文案替换后还需同步：**数据库**（agreement 表 content 用 `UPDATE ... SET content=REPLACE(content,'旧','新')`）、**后端代码**（验证码/欢迎语等含品牌词的文件）、**src 源码**（防止下次构建回退）ome-CsjOjG0H.js），
  Nginx 对 /assets/ 配置了 `Cache-Control: public, immutable`（7天）。
  直接 sed 改 dist JS 内容 = 文件名 hash 不变 = 浏览器永远用旧缓存（实测线上仍显示旧文案）。
  **正确做法**：改完 src 后重新构建 `cd /opt/ttdazi/frontend && npm run build`（约16s），
  让 hash 文件名变化，再把新 dist 同步到 Server B + 服务器D 两处。
- ⚠️ **Server B 的 Nginx 生效文件是 `sites-enabled/huizhiyunma`**，不是
  `sites-available/ttdazi`（改 ttdazi 不生效，reload 后仍走旧配置）。
  改 dazi.openai2000.cn 的 server 块必须编辑 huizhiyunma（记忆铁律"改huizhiyunma才持久"的实践验证）。
- 前端 src：`/opt/ttdazi/frontend/src/views/{Home,Agreement,Settings,About}.vue`（**必改，否则下次构建回退旧文案**）
- 数据库：`agreement` 表 `content` 字段（5 条协议页脚）
- 后端代码：`/opt/ttdazi/backend/app/{faq.py, user.py, wx_code.py, wx_message.py}`（FAQ 回复、验证码消息抬头【汇智云同途搭子】、关注欢迎语）

详见 📖 `references/brand-replacement.md`（位置清单、执行流程、坑：pkill 误杀 SSH、协议接口 type 参数等）。

## 公众号验证码系统（wx_code.py）

独立验证码模块（`/api/wxcode/send|verify|bind-phone`）：通过**公众号客服消息**把验证码推到用户微信，替代未接通的短信服务。
微信客服消息有 **48h 交互窗口限制**（errcode 45015 = 超窗），用户扫码登录/网页授权会刷新窗口，真实绑定场景可用。
详见 📖 `references/wechat-verification-code.md`（含账号能力探测命令、access_token 缓存、测试写操作后必须恢复真实数据的教训）。

## 微信菜单发布 + 消息回调（wx_message.py）

公众号自定义菜单 + 服务器配置回调模块 `/opt/ttdazi/backend/app/wx_message.py`（Blueprint `/api/wechat`，路由 `/message`）。
详见 📖 `references/wechat-menu-and-callback.md`（菜单 JSON、curl 命令、诊断顺序、当前状态）。

**关键规则（2026-07 实测）**：
1. **`menu/create` 只是存草稿**（2020年后微信改草稿+发布制），必须再调 `menu/publish` 才生效。验证 `get_current_selfmenu_info` 返回 `is_menu_open:1`。
2. **40066 invalid url 两种根因**：① view 按钮 URL 含 `#`（hash 路由不被接受，如 `/#/verify-identity`）→ 改 click 按钮；② 公众号后台"自定义菜单"功能被停用 → **纯 click 菜单 publish 同样报 40066**，可据此判断是账号侧问题，需用户在「微信开发者平台 → 我的业务 → 公众号 → 基础信息」开启。
3. **服务器配置回调**：URL `https://dazi.openai2000.cn/api/wechat/message`，Token `huizhiyun_ttdazi_2026`，明文模式。GET=echostr 签名验证（`sha1(sorted([token,timestamp,nonce]))`）；POST=XML 事件处理（CLICK 菜单 key：`GET_VERIFY_CODE`/`NOTICE`/`VERIFY_GUIDE`，subscribe 欢迎语，文本"验证码"关键词触发发码）。
4. **点菜单=与公众号交互** → 刷新 48h 客服消息窗口 → 验证码必达（绕开 45015 限制）。

## 实名认证聊天拦截

**业务规则：发起聊天（私聊/客服）前必须完成实名认证**（`verify_status==1` 管理员审核通过才放行，0/2/3 均 403 拦截，各状态提示文案不同）。
后端硬拦截在 `chat.py /api/chat/send`，前端体验拦截在 `CustomerService.vue` + `ChatConversation.vue`（未通过 → Toast + 跳 `/verify-identity`）。
详见 📖 `references/chat-verify-gate.md`（状态语义表、拦截代码、验证方法）。

## 数据盘备份记录日报

Hermes cron 每天早上 08:00 推送 Server A 数据盘备份记录到 QQ（job：`数据盘备份记录日报`，no_agent，脚本 `~/.hermes/scripts/data_disk_backup_report.py`，SSH root@42.193.113.230 读 `/root/data/disk/daily_*`）。
详见 📖 `references/backup-report-cron.md`。

## 扫码登录/微信OAuth 调试（已踩坑）

⚠️ 两个必查陷阱，详见 📖 `references/scan-login-debug.md`：

1. **函数内 `import json` 遮蔽全局名**：`wx_callback()` 里曾有分支内 `import json`，导致整个函数作用域内 `json` 变局部变量，函数开头 `json.loads()` 必抛 `UnboundLocalError` → 扫码登录 100% 报"登录失败"。修复=删除函数内 import（顶部已有全局导入）。排查任何回调类 bug 先搜函数内 `import` 是否遮蔽已用名字。
2. **gunicorn `--log-level warning` 吞掉 print**：`ttdazi.service` 默认 warning 级别，print 调试日志在 `journalctl -u ttdazi` 完全看不到。要么改 `--log-level info`，要么用共享日志模块 `app/scan_log.py` 的 `flog()` 写 `/tmp/wx_scan.log`（双通道：文件+stdout）。

无手机验证回调：`curl -s 'http://127.0.0.1:5002/api/wechat/callback?code=test&state=scan_test'`，`微信错误(errcode 40029)`=正常路径，`登录失败`=token 换取异常。

## 架构
- **Server A (42.193.113.230):** Flask + MySQL + gunicorn (port 5002)
  - **即本机（VM-0-15-ubuntu）**，本地开发/运维，无需 SSH
  - MySQL root 密码：在 `backup_api.py` 中配置，默认 `huizhiyun2026`
  - 数据盘：`/dev/vdb` → `/root/data/disk/`（20G）
  - **独立支付微服务**: `pay.openai2000.cn` → Caddy → `127.0.0.1:5005`
    - 代码 `/opt/ttdazi/payment_service/`，systemd `ttdazi-pay.service`
    - 数据库表 `pay_merchant/pay_order/pay_transaction`
    - 详见 📖 `references/payment-microservice.md`
  - Web 服务器: Caddy（管理 SSL + 反向代理 pay 域名）
- **Server B (82.157.202.24):** Nginx reverse proxy + frontend static files + OpenClaw + 1Panel面板
  - 🔴 **1Panel 管理 Nginx 配置**：1Panel 会恢复对 `sites-enabled/` 的手动修改。新增站点应写入 `huizhiyunma` 文件（不被 1Panel 管理），或通过 1Panel 网站管理界面配置。
  - 🔴 **sites-enabled 是独立副本**：`huizhiyunma` 在 `sites-enabled/` 中是副本而非软链接，需直接修改 `sites-enabled/huizhiyunma`
  - 🔴 **iptables 规则重启丢失** — Server A 默认 DROP 策略，每次新服务（5005/80/443）需手动加 iptables 放行规则。持久化：`sudo apt install -y iptables-persistent && sudo netfilter-persistent save`  
  - OpenClaw 二进制：`~/.nvm/versions/node/v22.23.0/bin/openclaw`（2026.6.11）
  - 🔴 **若二进制不可用**：`~/.local/share/pnpm/` 被清理后需 `npm install -g openclaw` 重装
  - Gateway 端口 38598，systemd 用户服务 `openclaw-gateway.service`
📖 `references/server-b-openclaw-maintenance.md` — Server B OpenClaw 诊断/修复/运维
📖 `references/server-b-baota-maintenance.md` — Server B 宝塔面板运维（Python 3.7 环境恢复/端口/面板故障）
### 🔴 管理后台路径轮换已知 Bug（2026-07-16 修复）

**Bug 1：`const defaultPrefix` 未被更新**

**症状**：路径轮换后新路径可访问，但刷新页面后恢复为旧路径。

**根因**：`rotate_admin_path.sh` 的 sed 不会更新 `frontend/src/router/index.js` 中的：
```javascript
const defaultPrefix = 'op-ztHWaT-0706'  // 硬编码默认值，轮换时不更新
```
该变量是 sessionStorage 为空时的 fallback，不更新则新用户首次访问时路由表以旧路径生成，导致 404。

**修复**：
```bash
# 手动更新
sed -i "s/const defaultPrefix = 'op-旧路径'/const defaultPrefix = 'op-新路径'/" frontend/src/router/index.js
```

**Bug 2：`CURRENT_PATH` 变量失效**

**根因**：`rotate_admin_path.sh` 中 `OLD_PATH=$(grep "^CURRENT_PATH" ... || echo "op-manage-7x2d9")` 依赖 `CURRENT_PATH` 变量，但该变量可能未写入脚本导致始终回退到硬编码默认值。

**修复**：每次轮换后更新脚本顶部的默认 fallback：
```bash
OLD_PATH=$(grep "^CURRENT_PATH" /opt/ttdazi/rotate_admin_path.sh 2>/dev/null | head -1 | cut -d= -f2 || echo "op-当前路径")
```

**Bug 3：deploy.sh 超时**

轮换脚本包含 `npm run build` + `bash deploy.sh`，deploy.sh 中的 rsync 到 Server B 可能因网络超时。脚本本身无超时保护，长时间运行后超时中断，构建可能已完成但部署未完成。手动执行 `bash /opt/ttdazi/deploy.sh` 补部署即可。

📖 `references/admin-path-rotation.md` — 完整文档
📖 `references/server-a-backup.md` — Server A 完整备份流程（数据库+程序+配置到数据盘）
📖 `references/back-arrow-and-bug-patterns.md` — 返回箭头规范、密码Bug、conn作用域、审计清单、Banner高度标准
- **Deploy:** `/opt/ttdazi/deploy.sh` builds frontend, restarts backend, syncs to Server B
- **Frontend:** Vue3 + Vant4 + Vite, source at `/opt/ttdazi/frontend/src`
- **Backend:** Flask blueprints at `/opt/ttdazi/backend/app/`

## 3D Card Design System (全站统一样式)

在 `frontend/src/assets/global.css` 中定义，所有页面共用。

### 卡片类
- **`.card-3d`** — 16px圆角白色卡片，多层紫色阴影 + `perspective(1200px) rotateX(2deg) rotateY(-1deg)` 3D倾斜 + 白色顶部高光 + ::before渐变光晕 + 按下回正上浮
- **`.menu-item-3d`** — 14px圆角菜单项，`rotateX(1deg)` 更平缓 + 紫色阴影（无::before避免遮文字）
- **`.login-page`** — 渐变紫全屏背景，配合 `.login-bg` 装饰圆 + `.login-card` 白色卡片

### 子组件类（全局共享）
- `.mi-icon` — 38px圆角图标容器
- `.mi-info` — 文字区（`overflow:hidden` 防溢出）
- `.mi-title` — 14px加粗标题（省略号）
- `.mi-desc` — 12px灰色描述（省略号）
- `.mi-arrow` — 20px灰色箭头（`margin-left:auto`右对齐）
- `.mi-locked` — 12px锁定图标

### 规则
1. 任何白色卡片用 `.card-3d`，不用自定义 `.card` 类
2. 任何可点击菜单行用 `.menu-item-3d`
3. 禁止嵌套 `.menu-item-3d`（transform 冲突）
4. 禁止在同一元素混用 `translateX`（滑动）和 `rotateX`（3D）
5. scoped style 不重复定义 `.card-3d` / `.menu-item-3d`
6. 登录/注册页必须用 `login-page` + `login-bg` + `login-card card-3d`
7. 仅限搭配 `.card-3d` / `.menu-item-3d` 使用，不单独使用。

## 用户沟通协议

每次收到消息：
1. 先回复 **"老板收到，开始安排任务！"**
2. 执行任务
3. 先发任务结果（代码改动、部署说明等）
4. **单独再发一条消息** `"老板，任务执行完毕，请您审核！"`（不跟任务结果合并）

## ⚠️ 自测交付协议（用户强制要求，不可跳过）

**用户原话：**
> "以后交给你的问题，检查出问题，修复后，必须自己再测试一下问题，有问题不断地进行自我优化和代码调整，达到完全没问题了，再给我交付"

这条规则不可违反。**不允许修完不测就直接交付**——即使只是改了一个字符。

### 强制流程：

```
1️⃣ 定位问题 → 2️⃣ 修复代码 → 3️⃣ ✅ 自测验证 → ❌ 有 Bug？→ 回到 2️⃣  → ✅ 全过 → 4️⃣ 交付
```

### 每次提交前必须做的三步检查：

```bash
# 1️⃣ API 测试（后端改动后）
curl -s -H "Authorization: Bearer $TOKEN" <endpoint> | python3 -c \
  "import sys,json;d=json.load(sys.stdin);print(f'code={d.get(\"code\")}')"

# 2️⃣ 构建测试（前端改动后）—— 必须确认有 "✓ built in Xs" 行
cd /opt/ttdazi/frontend && npm run build 2>&1 | tail -5
# 检查：最后一行以 "✓ built in" 开头？ 没有→构建失败，不可部署

# 3️⃣ 日志检查（后端 500 错误）
sudo journalctl -u ttdazi --no-pager -n 5 2>/dev/null | grep -q "Traceback\|Error" && echo "⚠️ 后端错误"
```

### 🔴 Vue `finally` 中 `loading.value` 未定义导致页面崩溃

**症状**：页面数据加载完成后瞬间崩溃，控制台报 `ReferenceError: loading is not defined`。

**根因**：`finally { loading.value = false }` 中引用了未声明的 `loading` 变量。常见于模板中无 loading 状态但有 loading ref 的代码遗留。

**排查**：
```bash
grep -rn "finally.*loading" frontend/src/ --include="*.vue" | grep -v "const loading\|let loading\|loading = ref"
```

**修复**：删除多余的 `finally { loading.value = false }` 或在组件中正确定义 `const loading = ref(true)`。

**案例**：`CreateOrder.vue` 的 `onMounted` 中曾包含 `finally { loading.value = false }` 但从未定义 `loading`，导致跳转至开通续期页面后崩溃。

### 🔴 常见自测遗漏场景（每个都是踩过的坑）

| 场景 | 自测方法 | 上次漏掉的后果 |
|------|---------|--------------|
| 改了一行 CSS | `npm run build` + 浏览器截屏 | 旧 dist 残留，用户看到的是旧样式 |
| 后端改了 API 逻辑 | curl 测试端点 + 验证响应 JSON | `audit_log` 函数不存在导致 500，点了没反应 |
| 改了前端的 API URL | 检查编译产物中的实际路径 | `/playmate/profile` vs `/companion/profile` 不匹配 |
| 改了数据库字段 | 验证 API 返回新字段值 | `pending_settle` 为 0 因为查错了 companion_id |
| 修复了 A 文件 | 检查是否引入了 B 文件的 Bug | `PlaymateIncome.vue` 的自动替换破坏了模板逻辑 |
| 改了某个页面 | 检查相关的所有页面布局 | `AdminWithdrawals.vue` 回退后 tab 类名变了 |
| 构建成功但没仔细看 | 确认最后一行是 `✓ built in` | Babel 错误在 stdout 中段，build 实际失败了 |

**黄金法则**：交付前必须自己走过一遍用户的操作路径（用 curl / Playwright 模拟）。不允许仅凭"代码看起来对"就交付。


## 全流程端到端测试方法

平台上线前或大版本更新后，执行以下测试步骤：

### 1. API 接口测试（curl）

```bash
# 获取验证码（如遇captcha无法自动破解，使用Playwright获取token）
CAPTCHA=$(curl -s /api/captcha/get)
# 注：dev模式下answer不返回，需用Playwright或直接跳过captcha

# 测试用户端核心API
TOKEN=...  # 从Playwright脚本获取或从login API获取
curl -s -H "Authorization: Bearer $TOKEN" /api/user/profile
curl -s /api/game/list
curl -s /api/companion/list
curl -s /api/companion/recommend
curl -s /api/demand/list
curl -s -H "Authorization: Bearer $TOKEN" /api/order/list
curl -s -H "Authorization: Bearer $TOKEN" /api/message/list

# 测试管理端
ADMIN_TOKEN=...
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" /api/admin/dashboard
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" /api/admin/users
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" /api/admin/orders
```

### 2. 浏览器截图验证

对所有用户端核心页面和管理端页面截屏：

```js
// 使用Playwright，先注入token，然后逐页导航截图
await page.evaluate((t) => { localStorage.setItem('token', t); }, token);
const pages = ['/#/', '/#/list', '/#/orders', '/#/demand-hall', '/#/profile', ...];
for (const url of pages) {
  await page.goto(`http://host${url}`);
  await page.screenshot({ path: `screenshot.png` });
}
```

### 3. 控制台错误检查

```js
const errors = [];
page.on('console', msg => {
  if (msg.type() === 'error') errors.push(msg.text());
});
page.on('pageerror', err => errors.push(err.message));
```

- **401 错误**：`/api/message/count` 在 token 过期时返回 401，axios 拦截器静默处理，是正常的
- **404 错误**：`/favicon.ico` 由 SVG inline favicon 替代，nginx 返回 404 是正常的
- 其他错误需逐个排查

### 4. 验证要点

| 检查项 | 正常结果 |
|--------|---------|
| 所有页面加载不白屏 | 可通过截图验证 |
| 控制台无报错（除无害401/404） | 无红色error |
| API返回格式一致 | `{code:0, data: {...}}` |
| 后端可访问 | `/api/health` 返回200 |
| 管理端页面可加载 | 后台侧栏每个页面打开正常 |

需要全面检查时，推荐并行派发3个subagent：
1. 用户端页面审计（所有 `.vue` 文件）
2. 管理端页面审计（`admin/` 下所有 `.vue` 文件）
3. 后端API审计（`app/` 下所有 `.py` 文件）

每个subagent输出标记严重程度（🔴🟡🟢）的问题清单，然后集中修复。修复后再部署。

### 审计重点
- 前端调用后端API路径是否匹配（MISSING API标记）
- HTTP方法 POST vs PUT vs DELETE 是否匹配
- 前端字段名 vs 后端字段名（如 `id_card` vs `id_number`, `nickname` vs `name`）
- 数据解包：后端 `{code:0, data:{list,total}}` vs 前端 `res.list`
- 认证缺失：管理端路由必须 `@admin_required`，用户路由 `@login_required`
- bare `except:` 吞错误 → 改为 `except Exception:`
- `except: pass` 在 `refreshCaptcha()` 等初始化函数中是故意的
- `admin_required` 从 `app.admin` 导入（不在 `app.utils`）
- 凡 Flask Blueprint 路由，管理端必须检查是否有 `@admin_required`，用户端必须检查 `@login_required`
- **历史漏洞**：`admin.py` 中 `/withdrawals` 和 `/withdrawals/<int:wid>/audit` 曾仅 `@login_required` —— 任何登录用户可查看+审核提现（金额+手机号泄露风险）
- **审核操作必须补 audit_log**：搭子审核、提现审核、实名认证审核等所有状态变更操作后立即调用 `audit_log()` 记录操作人和操作内容
- **coupon.py used_count 必须加行锁**：`SELECT ... FOR UPDATE` 防止高并发超发

### 后端修改后必须清缓存
修改 `utils.py` 等公共模块后：
```bash
find /opt/ttdazi/backend -name "__pycache__" -type d -exec rm -rf {} +
systemctl restart ttdazi
```

## 密码强度配置

`/opt/ttdazi/backend/app/utils.py` 中有 `PWD_MIN_LEN = 6` 密码规则：
- 默认要求16位+大小写+特殊字符 → 改为6位+数字即可
- 修改后必须清 `__pycache__` 重启

## 省市联动城市选择器模式

**场景**: 全国城市按省份→城市二级联动选择。已用于首页定位、列表筛选、设置页三处。

### 数据层 (`src/utils/cities.js`)

创建独立的城市数据模块，导出 `PROVINCES` 数组（每个元素 `{name, cities[]}`）和 `getAllCities()` / `searchCities()` 等工具函数。Vite 自动按需分块打包。

```javascript
import PROVINCES from '@/utils/cities'
const provinces = ref(PROVINCES)
const currentCities = computed(() => {
  const p = provinces.value.find(p => p.name === selectedProvince.value)
  return p ? p.cities : []
})
```

### 模板结构

```html
<!-- 省份列表 -->
<template v-if="!selectedProvince">
  <div @click="selectCity('')">全部城市/不定位</div>
  <div v-for="p in provinces" @click="selectedProvince = p.name">
    {{ p.name }} <span class="cp-arrow">›</span>
  </div>
</template>
<!-- 城市列表 -->
<template v-else>
  <div v-for="c in currentCities" @click="selectCity(c)">{{ c }}</div>
</template>
```

### 三处城市选择器的要点

| 页面 | 触发方式 | 保存行为 | 特殊点 |
|------|---------|---------|--------|
| 首页 Home.vue | 问候语旁「📍 定位城市」badge | localStorage + API `PUT /user/update` | 刷新后自动读取 |
| 列表 List.vue | 筛选栏「📍 城市」按钮 | `selectedCity` → `loadList()` | 「同城」按钮未设置城市时自动弹出picker(不弹Toast) |
| 设置 Settings.vue | 城市行点击 | API `PUT /user/update` | 城市列表可搜索过滤 |

### ⚠️ 陷阱: 用户说"还是不行"时的处理流程

用户连续说"还是不行/不行"时，说明**我没理解全需求范围**，而不是代码有bug。此时：

1. **立即确认范围**：问"还有哪些页面需要改？"而不是继续解释/验证已有改动
2. **逐页确认**：明确列出所有相关页面，让用户确认是否完整
3. **检查生产环境**：`ssh` 检查 Server B 上的 chunk 文件是否确实包含新代码（`grep` 关键词），有时旧 chunk 残留
4. **清理旧 chunk**：Server B 的 `/home/ubuntu/ttdazi-frontend/assets/` 目录可能残留旧版本 chunk（哈希不同），`rm -f` 清理

**已发生（2026-07-27）**：用户说"还是不行"时，我只在本地浏览器验证了代码功能正常，没意识到用户要的是**首页也有城市定位选择器**。下次用户抱怨时，先问"是哪些页面不行"再修。

## 常用模式

### 微信支付 JSAPI（公众号内支付）

推荐使用 `WeixinJSBridge.invoke('getBrandWCPayRequest')` 而不是 `wx.chooseWXPay`：
- 不需要加载微信 JS-SDK（jweixin-1.6.0.js）
- 不需要 `wx.config` 签名
- 不依赖当前页面的 URL（避免签名不匹配）
- 但仍需 JS接口安全域名配置

**架构**：使用独立支付子域名（如 `pay.openai2000.cn`）承载支付页面，主站只做跳转，不加载任何微信 JS-SDK。

**APIv3 JSAPI 签名**：用商户私钥 apiclient_key.pem 做 RSA-SHA256 签名，signType='RSA'。

### 🔴 支付回调 order_no 从 API 响应提取

跨域支付流程中，支付页（pay.openai2000.cn）创建订单后，**order_no 必须从 API 响应（`res.data.order_no`）中提取**，不能从 URL 参数取。URL 参数不包含 order_no。

```javascript
// ❌ 错误
var orderNo = getQuery('order_no');  // 永远为空
// 支付成功后用空 order_no 通知后端 → 找不到记录 → 余额不加

// ✅ 正确
xhr.onload = function() {
  var res = JSON.parse(xhr.responseText);
  myOrderNo = res.data.order_no;  // 从 API 响应保存
  orderData = res.data.jsapi;
};
// 支付成功回调时用 myOrderNo
xhr.send(JSON.stringify({order_no: myOrderNo, status: 1, amount: amount}));
```

### 🔴 跨域支付需双域名 JS接口安全域名

`WeixinJSBridge.invoke('getBrandWCPayRequest')` 会校验**当前页面**和**来源页面**的域名是否在 JS接口安全域名中。

当使用 `pay.openai2000.cn` 作为支付中转站时，**两个域名都必须添加**：
- `dazi.openai2000.cn` — 用户点击支付时所在的页面（WeixinJSBridge 会检查来源域名）
- `pay.openai2000.cn` — 支付中转页面

只加一个域名会在另一个域名上出现「当前页面的url未注册」错误。即使前端不再加载 wx JS-SDK，`WeixinJSBridge` 仍会校验。

### 🔴 支付回调用页面跳转代替 XHR 更可靠

跨域 XHR 在 WeChat 浏览器中可能被拦截。推荐改用**服务器端确认**模式：

**pay.html 支付成功：**
```javascript
location.href = 'https://dazi.openai2000.cn/api/pay/wxpay/confirm?order_no=' + encodeURIComponent(myOrderNo);
```

**服务器端确认端点**（不要加 `@login_required`）：
```
/api/pay/wxpay/confirm?order_no=xxx
  → 查微信支付 → 确认到账 → 302 跳回充值页
```

页面跳转 + 微信服务器通知构成双重保障。

### 🔴 服务端支付确认模式（推荐）

前端 `WeixinJSBridge.invoke()` 回调不可靠（跨域 XHR 被拦截）。改用页面跳转 + 服务器端查询微信支付结果：

1. 支付成功 → `location.href = '/api/pay/wxpay/confirm?order_no=' + myOrderNo`
2. 后端调用 `pay.openai2000.cn/api/v1/wxpay/query` 查支付结果
3. 确认 `trade_state == 'SUCCESS'` → 更新余额 + 写 money_log
4. 302 跳回充值页 `/api/pay/wxpay/confirm` **不要加 `@login_required`**（页面跳转会丢失 token）

详见 📖 `references/server-side-payment-confirm.md`

### 🔴 推荐搭子 API 查询缺少 `u.city`

**症状**：首页「推荐搭子」卡片不显示城市，但「人气搭子」正常显示。两个列表使用不同的 API 端点。

**根因**：`companion.py` 的 `recommend()` 函数 SQL 查询没有 SELECT `u.city`，而 `nearby()` 函数有。

```python
# recommend() — 缺少 u.city
SELECT c.id, ..., u.nickname, u.avatar, u.score, u.order_count, ...

# nearby() — 包含 u.city
SELECT c.id, ..., u.nickname, u.avatar, u.score, u.order_count, u.city, ...
```

**修复**：在 recommend 查询中添加 `u.city`：
```python
SELECT c.id, ..., u.nickname, u.avatar, u.score, u.order_count, u.city, ...
```

**排查方法**：用 curl 对比两个 API 的返回字段：
```bash
curl -sk /api/companion/recommend | python3 -c "import sys,json;print([i.get('city') for i in json.load(sys.stdin).get('data',[])])"
curl -sk /api/companion/nearby | python3 -c "import sys,json;print([i.get('city') for i in json.load(sys.stdin).get('data',[])])"
```

### 🔴 List.vue `cityFilter` 未定义变量（2026-07-16 修复）  
**症状**：游戏搭子列表页点击「📍 城市」选择城市后，页面报错无响应。  
**根因**：`selectCity()` 函数引用了 `cityFilter.value = c`，但 `cityFilter` 从未声明，ES Module strict 模式抛出 ReferenceError。  
**修复**：删除 `cityFilter.value = c` 行（城市筛选已由 `selectedCity` 处理）。

### 同城筛选（companion list city filter）  
列表页新增「同城」筛选按钮，从 localStorage 读取用户城市，传给后端 API 过滤。

**后端**：
```python
city_filter = request.args.get('city', '', type=str).strip()
if city_filter:
    where.append("u.city LIKE %s")
    params.append(f"%{city_filter}%")
```

**前端**：
```js
function toggleSameCity() {
  sameCity.value = !sameCity.value
  if (sameCity.value && !userCity.value) {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    userCity.value = user.city || ''
    if (!userCity.value) { safeToast('请先在设置中定位城市'); sameCity.value = false; return }
  }
  loadList()
}
```

**注意**：用户城市存储在 `localStorage.getItem('user')` 的 `city` 字段中，通过设置页的「📍 定位」按钮更新。

### 🔴 双域名支付：前端只跳转，pay页面创建订单

当从 `dazi.openai2000.cn` 跳转到 `pay.openai2000.cn/pay` 时：

```javascript
// ❌ 错误：前端创建订单 + pay页面创建订单 = 两条充值记录
const r = await api.post('/pay/wxpay/jsapi', { amount: amt })
location.href = 'https://pay.openai2000.cn/pay?token=' + token + '&amount=' + amt

// ✅ 正确：前端只跳转，pay 页面自己创建订单
const token = localStorage.getItem('token')
location.href = 'https://pay.openai2000.cn/pay?token=' + encodeURIComponent(token) + '&amount=' + amt
```

### 🔴 服务端支付确认端点不要加 `@login_required`

`/api/pay/wxpay/confirm` 端点通过页面跳转访问（`location.href`），浏览器导航不携带 `Authorization` header。加 `@login_required` 会导致 `401 未登录`。

```python
# ❌ 错误：页面跳转会丢失 token
@PAY_API.route('/wxpay/confirm', methods=['GET'])
@login_required
def wxpay_confirm(): ...

# ✅ 正确：通过 order_no 查询用户，不需认证
@PAY_API.route('/wxpay/confirm', methods=['GET'])
def wxpay_confirm():
    order_no = request.args.get('order_no', '')
    cur.execute("SELECT user_id, amount, status FROM recharge WHERE order_no=%s", (order_no,))
```

### 🔴 微信支付查询结果 `trade_state` 嵌套在 `data` 字段内

支付服务的 `/api/v1/wxpay/query` 端点返回 `{"code":0,"data":{"trade_state":"SUCCESS",...}}`，查询结果在嵌套的 `data` 中：

```python
result = json.loads(resp.read().decode())
# ❌ 错误：直接从顶层读
trade_state = result.get('trade_state', '')
# ✅ 正确：从 data 字段读
trade_state = ''
if isinstance(result, dict):
    trade_state = result.get('trade_state', '') or (result.get('data') or {}).get('trade_state', '')
```

### 🔴 跨域通知 CORS 配置

支付页（pay.openai2000.cn）向后端（dazi.openai2000.cn）发送回调通知时，后端 CORS 必须允许支付域名：
```python
CORS(app, resources={r"/api/*": {"origins": [..., "https://pay.openai2000.cn"]}})
```

详见 📖 `references/recharge-cross-domain-payment.md`

### `goTo()` 函数中的公开路径白名单

Profile.vue 的 `goTo(path)` 函数默认要求所有页面需登录。但用户协议/隐私政策/关于等页面应公开访问：
```js
function goTo(path) {
  const publicPaths = ['/', '/agreement/user', '/agreement/privacy', '/agreement/rules', '/agreement/disclaimer', '/about']
  if (!user.value.id && !publicPaths.includes(path)) {
    safeToast('请先登录')
    router.push('/login')
    return
  }
  router.push(path)
}
```

### 列表页 API 数据解包

后端分页列表返回 `{code:0, data:{list:[...], total:N, page:1}}`，axios 拦截器返回 `res.data.data`。
前端取值：
```js
const res = await api.get('/xxx/list')
items.value = Array.isArray(res.list) ? res.list : (Array.isArray(res) ? res : [])
```
不要用 `Array.isArray(res)` 判断（`res` 是 `{list,total}` 对象）。
后端GET列表时必须确认是否有 `@login_required` —— 漏掉会导致始终返回401（见 message.py #count 端点修复）。

### 日期格式化工具

全站日期格式化函数（Orders.vue / DemandHall.vue 共用模式）：
```js
function formatTime(t) {
  if (!t) return '--'
  const d = new Date(t)
  if (isNaN(d.getTime())) return String(t).slice(0,10)
  const pad = n => String(n).padStart(2,'0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`
}

function formatTimeOnly(t) {
  if (!t) return '--'
  const d = new Date(t)
  if (isNaN(d.getTime())) return String(t).slice(11,16)
  const pad = n => String(n).padStart(2,'0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}
```

后端 `created_at` 是 Python datetime 对象，Flask jsonify 序列化为 ISO 格式（如 `"Tue, 07 Jul 2026 14:23:18 GMT"`）。
**不要用** `.slice(0,10)` —— 会截出 `"Tue, 07 Ju"`。必须用 `Date()` 解析后格式化。

### loadingOverlay 开启/关闭次数匹配

每个 `loadingOverlay.value = true` 必须有对应的 `loadingOverlay.value = false`：
- 在 `try` 中开启 → 在 `finally` 中关闭
- 嵌套的 showLoading/hideLoading（DOM操作层）不要跟模板 loading ref 混用
- `onUnmounted` 中 `loadingOverlay.value = false` 是兜底清理

## 返回箭头统一标准

| 属性 | 值 |
|------|-----|
| 元素 | `<span class="back">‹</span>` |
| 字号 | 22px（header-bar标准）或28px（独立定位） |
| 颜色 | `#fff` |
| 位置 | flex布局（header-bar）或 absolute（自定义header） |
| 交互 | `@click="smartBack(route.path)"` |
| 导入 | `import { smartBack } from '@/utils/nav'` |
| 需导入 | `useRoute` + `const route = useRoute()` |

### 🔴 常见错误：`route is not defined`

在非标准页面（如Profile.vue）加返回箭头时，必须同时做两件事：
```js
import { useRouter, useRoute } from 'vue-router'  // 加 useRoute
const router = useRouter()
const route = useRoute()                            // 定义 route 变量
```
漏掉任意一个都会导致 `route.path` 为 undefined，`smartBack(undefined)` 无法判断返回路径，箭头点了没反应。

对于使用自定义 `profile-header`（无 `header-bar`）的页面，箭头用内联style定位：
```html
<span class="back" style="position:absolute;top:12px;left:14px;font-size:22px;color:#fff;z-index:20;cursor:pointer;line-height:1" @click="smartBack(route.path)">‹</span>
```
不要同时写 scoped CSS 和内联style（冲突导致样式叠加混乱）。

### smartBack FALLBACK_MAP 扩展

`frontend/src/utils/nav.js` 中的 `FALLBACK_MAP` 定义了各页面的返回目标。添加新页面后必须更新该映射——新页面若不注册 fallback，`smartBack()` 只会回退 `/`。需求系统新增条目：

```
'/demand-hall': '/',
'/my-demands': '/profile',
'/create-demand': '/my-demands',
```

## 按钮始终可点击（不要用 disabled 隐藏）

用户明确要求：**按钮不要用 disabled 条件让用户「不知为何点不了」**。

```html
<!-- ❌ 错误：用户不知为何点不了 -->
<button :disabled="!emailName.value || !code.value">注册</button>

<!-- ✅ 正确：始终可点击，函数内弹 Toast 提示 -->
<button @click="doRegister">注册</button>

function doRegister() {
  if (!emailName.value) { safeToast('请输入邮箱名'); return }
  if (!code.value) { safeToast('请输入验证码'); return }
  // ...
}
```

唯一允许用 disabled 的场景是 **loading 中**（防止重复提交）：
```html
<button :disabled="loading" @click="submit">提交</button>
```

## Tab / 分类栏自动换行（flex-wrap）

当分类较多时，使用 `flex-wrap: wrap` 代替 `overflow-x: auto`：

```css
/* ✅ 自动换行 */
.tab-bar, .filter-bar, .sort-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 6px 12px;
}
.tab, .filter-item, .sort-bar span {
  padding: 6px 10px;     /* 减少内边距，给换行留空间 */
  font-size: 13px;
  white-space: nowrap;   /* 防止文字折行 */
}

/* ❌ 不要用横向滚动 */
.tab-bar {
  overflow-x: auto;      /* 用户看不到全部选项 */
  scrollbar-width: none;
}
```

注意：`justify-content: center` 会导致最后一行元素居中而非左对齐。除非特意设计，否则保持左对齐。

## 悬浮 FAB 按钮规范

悬浮按钮（FAB）必须避开底部导航栏：

```css
.fab-create {
  position: fixed;
  bottom: 100px;              /* 底部导航栏约72px，留足间距 */
  right: 24px;
  width: 56px; height: 56px;  /* 够大的点击区域 */
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(102,126,234,0.4);
  cursor: pointer;
  z-index: 100;               /* 高于底部导航的z-index:1000？实际测试发现100即可 */
}
```

底部导航高度 64px + safe-area 约8px = 72px。FAB 的 `bottom` 应 ≥ 80px。经验值：**100px**。

## Banner 高度统一标准

所有页面的 banner（header-bar / gradient-header）必须使用相同的 padding：

```css
/* ✅ 标准 banner 高度 */
.header-bar, .gradient-header {
  padding: 44px 16px 16px;
}
```

- `44px` — 状态栏安全区（移动端 notch）
- `16px` — 左右安全间距
- `16px` — 底部间距（含标题文字到边缘的距离）

有 Tab 栏紧随的页面（订单、消息、大厅），Tab 栏紧贴 banner 底部，**无间距**：
```css
/* tab-bar 不要加 margin-top 或 border-top */
.tab-bar {
  background: linear-gradient(135deg, #667eea, #764ba2); /* 或者 #fff */
  padding: 2px 12px 8px;
}
```

## 订单号生成规范

需求发布时自动生成订单号：

```python
# 后端生成
order_no = datetime.now().strftime('%Y%m%d%H%M') + ''.join(random.choices('0123456789', k=4))
# 输出示例: 2026070703385642
```

格式：`YYYYMMDDHHmm` + 4位随机数字，共 16 位纯数字。

数据库字段：`VARCHAR(32)`，通过 `ALTER TABLE` 添加。之后需补全旧数据：
```sql
UPDATE demand_order SET order_no = CONCAT(DATE_FORMAT(created_at, '%Y%m%d%H%i'), LPAD(FLOOR(RAND()*10000), 4, '0')) WHERE order_no IS NULL OR order_no = '';
```

前端显示位置：卡片底部日期后面，格式 `订单号 XXXXXXXXXXXX`（字号10px，灰色）。

## 需求功能模块 (Demand System)

### 🔴 需求大厅双分类展示（2026-07-17）

需求大厅顶部显示 **游戏达人** 和 **同城达人** 两个分类卡片，点击后进入对应子分类Tab展示具体游戏/服务筛选。详见 📖 `references/demand-hall-dual-category.md`。

### 前端页面路由

| 路由 | 组件 | 功能 | API 端点 |
|------|------|------|---------|
| `/demand-hall` | `DemandHall.vue` | 需求大厅 — 游戏/同城双分类 + 子Tab筛选 + 3D卡片列表 | `GET /api/demand/list` |
| `/my-demands` | `MyDemands.vue` | 我的需求 — 状态tab筛选 + 取消/确认完成 | `GET /api/demand/my` + `POST /api/demand/cancel` + `POST /api/demand/complete` |
| ~~`/create-demand`~~ | ~~`CreateDemand.vue`~~ | ❌ **已移除** — 用户发布需求功能已取消，路由已删除，按钮已移除，后端 API 返回 `发布功能已关闭` | ~~`POST /api/demand/create`~~ |
| `/op-ztHWaT-0706/demands` | `admin/AdminDemands.vue` | 管理端 — admin-layout + 表格 + 删除 | `GET /api/demand/admin/list` + `POST /api/demand/admin/delete` |

### 实名/搭子认证检查

**发布需求** — `POST /api/demand/create`：
- 检查 `user.verify_status = 1`（实名认证通过）
- 未通过返回「请先完成实名认证后才能发布需求」

**接单** — `POST /api/demand/accept`：
- 检查 `user.verify_status = 1`（实名认证通过）
- 检查 `companion.status = 1`（搭子审核通过）
- 任一不通过返回中文提示

### 需求数据字段

```
{ id, user_id, title, game_id, game_name, price, duration,
  description, status, nickname, avatar, created_at }
```

status: 0=待接单, 1=已接单, 2=已完成, 3=已取消

### 页面编码 checklist
1. header-bar: `@click="smartBack(route.path)"` — 需导入 `useRoute` + `const route = useRoute()`
2. 状态标签 class: 带 `'sd' + d.status`，scoped style 定义 `.sd0`~`.sd3` 配色
3. 所有列表页需覆盖 4 种状态: 加载中 `.loading-state` / 加载失败 `.error-state` / 空数据 `.empty-state` / 正常列表
4. `showLoading`/`hideLoading` 函数复用标准模板（createElement + custom-loading-overlay）
5. 管理端页面用 `admin-layout` + `AdminSidebar` + `admin-main` 布局
6. 管理端表格列必须包含「操作」列（删除/编辑按钮）
7. admin sidebar 已有「需求管理」菜单项（`/op-ztHWaT-0706/demands`），无需重复添加
8. `CreateDemand.vue` 用 `card-3d` 分组字段 + `submit-btn` 全宽提交按钮

## 订单卡片结构（用户确认）

1. 顶部：订单号（左）+ 状态标签（右）
2. 中间：左=头像+昵称+备注 | 右=金额+游戏名（右对齐）
3. 底部日期行：📅日期 🕐时间 ⏱服务时长（浅灰分隔线上方）
4. 操作按钮区（border-top分隔）

底部 `.order-foot` 样式：`font-size:11px; color:#777; padding-top:6px; border-top:1px solid #f5f5f5; gap:12px`

### 全局 CSS 泄露影响所有组件（admin-main margin-left）\n\n**症状**：所有管理页面的内容区比预期多偏移了220px，即使用户级 scoped CSS 已删除 `margin-left: 220px`。\n\n**根因**：`frontend/src/assets/global.css` 中存在全局 `.admin-main { margin-left: 220px; flex: 1; }` 规则。该全局 CSS 被所有管理页面引入，优先级高于 scoped CSS 的同属性规则（scoped CSS 只覆盖了 `flex` 未覆盖 `margin-left`）。\n\n**排查方法**：\n```bash\n# 检查全局 CSS 中的规则\ngrep \"margin-left\" /opt/ttdazi/frontend/src/assets/global.css\n# 检查浏览器中实际应用的规则（开发者工具 → Computed → margin-left）\n```\n\n**修复**：删除 `global.css` 中的冲突规则，每个页面用 scoped 样式自行控制。\n\n**全局 CSS 检查清单**：修改任何页面布局时，同时检查 `global.css`、`App.vue` 的全局 `<style>` 块，以及所有 `index-*.css` 的 Vite 编译产物，确保没有全局 CSS 影响预期表现。\n\n### 构建产物缓存导致旧 CSS 残留\n\n**症状**：源文件已修复（global.css 已删除 margin-left），但浏览器仍显示旧的 margin-left。\n\n**根因**：`dist/` 目录的构建产物未被正确清除。之前因为有 CSS 语法错误导致构建失败，但 deploy.sh 误报成功，使用的仍是上一次成功的旧 dist。\n\n**排查**：\n```bash\n# 比较源码和编译产物的 CSS 规则\npython3 -c \"\nwith open('/opt/ttdazi/frontend/dist/assets/style-*.css', 'rb') as f:\n    data = f.read()\nidx = data.find(b'admin-main')\nif idx >= 0:\n    chunk = data[idx:idx+100].decode()\n    if 'margin-left' in chunk:\n        print('STALE CSS still has margin-left')\n\"\n# 检查构建实际是否成功（看最后一行是否有 \"✓ built in\"）\nnpm run build 2>&1 | tail -5\n```\n\n**修复**：\n```bash\nrm -rf /opt/ttdazi/frontend/dist /opt/ttdazi/frontend/node_modules/.vite\n# 然后重新构建 + 部署\ncd /opt/ttdazi/frontend && npm run build\nbash /opt/ttdazi/deploy.sh\n```\n\n**预防**：构建出错后必须修复语法错误并清除缓存，不可直接部署。\n\n### `patch` 工具留下的孤儿 CSS 行\n\n**症状**：CSS 文件中出现孤立的属性声明（不在任何 CSS 规则块内），如：\n```css\n.admin-main { flex: 1; padding: 20px; }\n  margin-left: 220px;   /* ← 孤儿行，不属于任何规则 */\n}\n```\n\n**根因**：使用 `patch` 工具移除 CSS 属性时，只删除了目标字符串但留下了相邻行的残余。`AdminConfig.vue` 的原始 CSS 是：\n```css\n.admin-main { flex: 1; padding: 20px; padding-bottom: 80px; \n margin-left: 220px;\n}\n```\n`patch` 工具无法删除跨行的 `margin-left`，Python 脚本替换后又留下了 `}` 和空白行。\n\n**后果**：PostCSS 解析报 `Unexpected }`，整个 Vite 构建失败。\n\n**修复**：构建失败时，检查错误位置对应的源文件是否有格式错误：\n```bash\n# 检查语法错误的文件\ngrep -n \"margin-left\\|Unexpected\\|}\" file.vue | head -10\n# 手动查看对应行号附近的 CSS 块\nsed -n '118,125p' file.vue\n```\n\n**预防**：\n1. 操作多行 CSS 时，始终用 `terminal` + `python3` 的 `content.replace()` 批量替换\n2. 替换后检查相邻行是否有残余\n3. 每次构建后确认有 `✓ built in Xs` 行，否则查看 `error during build:` 之前的错误详情\n\n## CSS 坑点

### `patch` 工具中的 `\\n` 转义问题
patch 工具写 `\\\\n` 会被序列化为字面量 `\\n`（反斜杠+n）而非换行符。修复：用 `terminal` + `python3` 写文件替换：
```python
with open('file.vue', 'rb') as f:
    data = f.read()
data = data.replace(b'\\\\n', b'\\n')
with open('file.vue', 'wb') as f:
    f.write(data)
```
更稳妥：避免使用 `patch` 操作带多行字符串的CSS/HTML替换。改为：
1. 用 `terminal` + `python3` 做 `content.replace('old', 'new')`
2. 或用 `execute_code` 工具做文件读写

### `overflow: hidden` 裁剪 absolute 子元素
当父元素有 `overflow: hidden` 且子元素 `position: absolute` 在父元素内边距内时，不会裁剪。但如果子元素超出父元素边界会被裁剪。修复：改为 `overflow: visible`。

### 内联style vs scoped CSS 冲突
当内联style和scoped CSS选择同一个元素的同一属性时，内联style优先级更高，但未被覆盖的属性会从CSS继承。这导致 font-size/z-index 等不一致。策略：要么全用内联，要么全用CSS，不要混用。

## Server B 综合运维

### 🔴 Chrome 进程 OOM 预防

Server B 上的浏览器自动化（Chrome renderer/GPU 进程）会占用大量 CPU 和内存（累计可达 CPU 142% + 内存 1.2GB），导致服务器崩溃、SSH 超时。

**症状**：SSH TCP 端口通（nc 成功）但 banner exchange 超时，nginx/1panel 无响应。

**修复**：杀掉 Chrome 进程后重启服务器。添加定时清理 cron：
```bash
*/30 * * * * pgrep -f "chrome.*--renderer" | head -10 | xargs kill -9 2>/dev/null; pgrep -f "chrome.*--gpu-process" | head -5 | xargs kill -9 2>/dev/null; true
```

### Server B Nginx 域名白名单与多站点配置

Server B (82.157.202.24) 的 `huizhiyunma` 站点监听 80/443 并设置了域名白名单：

```nginx
if ($host !~ ^(openai2000\\.cn|www\\.openai2000\\.cn)$) { return 403; }
```

这意味着通过 IP 访问（`http://82.157.202.24/api/...`）会被拦截返回 403。

**影响**：Hermes cron 脚本（如 `daily_admin_push.py`）或外部健康检查如果通过 IP 访问 API，会收到 403。

**修复**：改为直连后端 `http://127.0.0.1:5002/api/...` 绕过 Nginx。因为 Hermes 跑在 Server A 上，127.0.0.1 就是 Flask 后端。

### 🔴 1Panel 管理 Nginx 配置：手动写入 sites-enabled 会被还原

Server B 的 **1Panel 面板** 监控并管理 Nginx 配置。手动写入 `sites-enabled/ttdazi`、`sites-available/ttdazi` 等独立文件会被 1Panel 自动还原为旧内容（ModSecurity + server_name 82.157.202.24 的旧配置）。

**后果**：即使 `sudo tee /etc/nginx/sites-enabled/ttdazi` 写入正确配置并 `nginx -s reload` 成功，几分钟后配置被还原。新域名 SSL 证书不匹配，用户看到「不安全」。

**排查方法**：
```bash
# 检查配置是否被还原
sudo head -5 /etc/nginx/sites-enabled/ttdazi
# 如果显示的是旧配置（ModSecurity on; server_name 82.157.202.24），说明被 1Panel 还原
```

**所有失败的模式**：
```bash
# ❌ 失败模式 1：写入 sites-available + ln -sf 独立文件
echo '...' | sudo tee /etc/nginx/sites-available/ttdazi
sudo ln -sf /etc/nginx/sites-available/ttdazi /etc/nginx/sites-enabled/

# ❌ 失败模式 2：sudo tee 直接写入 sites-enabled 独立文件
sudo tee /etc/nginx/sites-enabled/ttdazi > /dev/null << 'NGINX' { ... NGINX }

# ❌ 失败模式 3：删除重建独立文件（Inode 变化后 1Panel 检测到并恢复）
sudo rm -f /etc/nginx/sites-enabled/ttdazi && sudo tee ...
```

**根本解决方案**：将新站点的配置写入 **1Panel 不管理的文件**（如 `huizhiyunma`），不要建立独立文件。推荐用写入临时文件 + `sudo cp` 的方式：
```bash
cat > /tmp/ttdazi.conf << 'NGINX'
# 原 huizhiyunma 配置 + 新增的 server block
server { ... }
NGINX
sudo cp /tmp/ttdazi.conf /etc/nginx/sites-enabled/huizhiyunma
sudo nginx -s reload
```

**注意**：sites-enabled/huizhiyunma 是**独立副本**（非软链接），直接修改它即可。修改 sites-available/huizhiyunma 不影响生效配置。

**验证 SSL 证书是否正确**（配置被还原的最明显症状）：
```bash
openssl s_client -connect dazi.openai2000.cn:443 -servername dazi.openai2000.cn </dev/null 2>&1 | grep 'subject='
# 正确应为 CN = dazi.openai2000.cn
# 若显示 CN = openai2000.cn，说明 1Panel 还原了配置
```

### 🔴 sites-enabled 是独立副本而非软链接

Server B 上某些站点配置文件（如 `huizhiyunma`）在 `sites-enabled/` 中是**独立副本**，不是指向 `sites-available/` 的软链接。

**后果**：修改 `sites-available/huizhiyunma` 不影响 `sites-enabled/huizhiyunma`。`sed` 后 `nginx -t` 通过，但实际生效的是旧配置。

**排查方法**：
```bash
file /etc/nginx/sites-enabled/huizhiyunma
# "ASCII text" = 副本，直接修改 sites-enabled 下的文件
# "symbolic link" = 软链接，修改 sites-available 即可
```

### 🔴 `server_tokens off;` 仅在 nginx.conf 的 `http` 块中生效

若配置在 `server` 块则无效。但它在 `http` 块中已存在（`/etc/nginx/nginx.conf`）。

### 🔴 Nginx sites-enabled 是独立副本而非软链接

Server B 上某些站点配置文件（如 `huizhiyunma`）在 `sites-enabled/` 中是**独立副本**，不是指向 `sites-available/` 的软链接。

**后果**：修改 `sites-available/huizhiyunma` 不影响 `sites-enabled/huizhiyunma`。`sed` 后 `nginx -t` 通过，但实际生效的是旧配置。

**排查方法**：
```bash
# 检查 sites-enabled 中的文件类型
file /etc/nginx/sites-enabled/huizhiyunma
# 如果是 "ASCII text" 就是副本，需要直接修改 sites-enabled 下的文件
# 如果是 "symbolic link" 就是软链接，修改 sites-available 即可
```

### 🔴 添加新域名时必须避免 `default_server` 冲突

当 `huizhiyunma` 设为 `default_server` 时，添加 `dazi.openai2000.cn` 并配置 `listen 443 ssl` 会导致：
- `dazi.openai2000.cn` 的请求被 `huizhiyunma` 的 SSL 证书拦截（证书不匹配 → SSL 错误）
- 新站点的 SSL 证书不被使用

**正确步骤**：
1. 关闭 `huizhiyunma` 的 `default_server`（`sites-enabled/` 和 `sites-available/` 都要改）
2. 新站点不要加 `default_server`
3. 用 `server_name` 区分，Nginx 根据 TLS SNI 自动路由

### 多域名 HTTPS 站点（SNI 匹配）

Server B 上有两个 HTTPS 站点共享 443 端口，通过 SNI (Server Name Indication) 区分：

| 域名 | 说明 | SSL 证书 |
|------|------|---------|
| `openai2000.cn` / `www.openai2000.cn` | huizhiyunma 主站 | Let's Encrypt (openai2000.cn) |
| `dazi.openai2000.cn` | 同途搭子前端站点 | Let's Encrypt (dazi.openai2000.cn) |

**要点**：
- `huizhiyunma` 不能设为 `default_server`，否则会抢占新域名的 HTTPS 连接
- 新域名必须有自己的 `server_name` + `ssl_certificate` 配置
- 证书用 `certbot certonly --webroot -w <webroot_path> -d <domain>` 单独申请
- 同一端口上的 server block 通过 `server_name` 匹配，Nginx 根据 TLS SNI 自动路由

### 新站点配置模板

```nginx
server {
    listen 80;
    server_name dazi.openai2000.cn;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dazi.openai2000.cn;

    ssl_certificate     /etc/letsencrypt/live/dazi.openai2000.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dazi.openai2000.cn/privkey.pem;

    root /home/ubuntu/ttdazi-frontend;
    index index.html;

    location /api/ { proxy_pass http://42.193.113.230:5002; ... }
    location / { try_files \$uri \$uri/ /index.html; }
}
```

## 部署流程
```bash
cd /opt/ttdazi/frontend && npm run build
bash /opt/ttdazi/deploy.sh
```
前后端一起部署。确认：`git add -A && git commit -m "..."`

### 🔴 deploy.sh 用 scp 而非 rsync，旧文件不自动清理

**问题**：`deploy.sh` 使用 `scp -r` 同步前端文件到 Server B，**不会删除旧文件**。多次部署后积累了多个版本的 hash 文件名（如 2 个 `WxLogin-*.js`），导致用户浏览器加载旧版含 Bug 的文件。

**症状**：代码已修复+构建+部署，但用户仍看到旧行为（如"页面加载错误"）。`deploy.sh` 输出 `✅ 同步完成` 但旧文件仍在。

**排查**：
```bash
# 检查 Server B 上旧文件数量
ssh ubuntu@82.157.202.24 "ls /home/ubuntu/ttdazi-frontend/assets/WxLogin-*.js | wc -l"
# 如果 > 1，有旧文件残留
```

**修复**：
1. 立即清理：`ssh ubuntu@82.157.202.24 "rm -f /home/ubuntu/ttdazi-frontend/assets/旧的-文件名.js"`
2. 或改用 `rsync -avz --delete dist/ ubuntu@82.157.202.24:/home/ubuntu/ttdazi-frontend/`
3. 强烈建议修改 `deploy.sh` 第60行的 `scp -r` 为 `rsync -avz --delete`

## 全量服务器迁移检查清单

📖 `references/server-migration-checklist.md` — 完整6步部署命令
📖 `references/server-a-backup.md` — Server A 完整备份流程（数据库+程序+系统配置）

将平台迁移到新服务器时：
- **备份包含**：项目源码、MySQL dump、Nginx 配置模板、上传文件
- **备份缺失**：MySQL/Node/Nginx 服务、Python 依赖包、Systemd 服务文件、SSL 证书、定时任务
- **双→单服务器合并**：`proxy_pass` 改为 `127.0.0.1:5002`，移除 `allow 42.193.113.230`
- **定时任务重建**：订单结算(5min)、路径轮换(3am)、财务备份(8/14/22点)
- **验证清单**：API健康 → 页面加载 → 登录 → 订单流程 → 数据对比

## 磁盘清理标准流程

📖 `references/disk-REDACTED-workflow.md` — 完整排查步骤

当用户要求检测/清理磁盘时：
```bash
df -h /                                    # 1层：整体使用
du -sh /home /var /tmp /opt | sort -rh     # 2层：大目录
du -sh /home/ubuntu/* /home/ubuntu/.* | sort -rh | head -20  # 3层：含隐藏文件
ls -lhS /tmp/ | head -10                   # 4层：/tmp 大文件
journalctl --disk-REDACTED                    # 5层：日志
```
- **安全可删**：`/tmp/backup.tar.gz`、`~/.cache/`、`~/.npm/`、`/var/log/journal`
- **需确认**：其他项目副本（`hui_zhi_yun/`、`python_site/`）、`.openclaw/`

## Vite 前端配置
```js
export default defineConfig({
  server: { host: '0.0.0.0', port: 5173 },
  build: { cssCodeSplit: false },
})
```

### 纯展示引流模式（当前运营模式，2026-07-16 起）

**定位**：搭子付费开通展示 → 免费让用户看到 → 私聊沟通 → 线下对接。平台纯做信息撮合，**不涉及任何线上交易**。

### 已移除的功能（合规清理）

| 功能 | 移除原因 | 移除时间 |
|------|---------|---------|
| 订单管理（PlaymateOrders.vue） | 搭子不再接单 | 2026-07-16 |
| 收入提现（PlaymateIncome.vue 路由） | 平台不代收代付 | 2026-07-16 |
| 搭子端收入统计 | 无收入来源 | 2026-07-16 |
| 搭子首页待处理订单区块 | 无订单系统 | 2026-07-16 |
| 价格中的"包夜"选项 | 合规红线 | 2026-07-16 |

### 搭子端当前功能入口

| 入口 | 路由 | 说明 |
|------|------|------|
| ✏️ 资料编辑 | `/playmate/profile` | 编辑展示信息、游戏、参考价格 |
| 📢 需求大厅 | `/demand-hall` | 查看用户发布的需求 |
| 💬 私信列表 | `/chat-list` | 查看所有聊天会话 |
| 🔄 开通/续期 | 跳转至`/order/create` | 付费开通展示服务 |

### 🔴 搭子端路由现状（2026-07-16 起）

```javascript
// 当前有效的 playmate 路由：
{ path: '/playmate/login', name: 'PlaymateLogin' },
{ path: '/playmate/', name: 'PlaymateHome' },
{ path: '/playmate/profile', name: 'PlaymateProfile' },
// ❌ 已删除：
// { path: '/playmate/orders' },   // 2026-07-16 移除（搭子不再接单）
// { path: '/playmate/income' },   // 2026-07-16 移除（平台不代收代付）
```

### 🔴 游戏/同城分类 ID 范围（2026-07-17 最新）\n\n**当前分类布局**（game 表 id 范围）：\n\n| 范围 | 分类 | 说明 |\n|:----:|------|------|\n| 1 ~ 7 | 🎮 游戏 | 王者荣耀、和平精英等（原版7个） |\n| 8 ~ 14 | 📍 同城达人 | 景点讲解、行程规划等（原旅游7个） |\n| 15 ~ 22 | 🎮 游戏（新增） | 金铲铲、英雄联盟、DNF手游等 |\n| 23 ~ 32 | 📍 同城（新增） | 出行翻译、包车向导、露营向导等 |\n| 33 ~ 40 | 📍 同城（技能兴趣） | 台球交流、声乐交流、健身指导等 |\n\n📖 `references/game-category-id-management.md` — 完整过滤条件同步清单

**2026-07-17 实现**：服务类型改为两级展开结构——大类（游戏达人/同城达人）+ 子分类（具体游戏/服务），每个子类可独立设置参考价格。

**模板结构**：
```html
<!-- 大类卡片（点击展开/收起） -->
<div class="type-grid">
  <div :class="['type-card', { selected: selectedTypes.includes('game') }]" @click="toggleType('game')">
    <span class="tc-icon">🎮</span>
    <span class="tc-name">游戏达人</span>
    <span class="tc-desc">{{ gameSubs.length }}个子分类</span>
    <span v-if="selectedTypes.includes('game')" class="tc-check">✓</span>
  </div>
  <div :class="['type-card', { selected: selectedTypes.includes('travel') }]" @click="toggleType('travel')">
    ... 同城达人 ...
  </div>
</div>

<!-- 子分类网格（在大类卡片下方展开） -->
<div v-if="selectedTypes.includes('game')" class="sub-grid">
  <div v-for="g in gameSubs" :key="g.id"
    :class="['sub-item', { active: selectedSubs.includes(g.id) }]"
    @click="toggleSub(g.id)">
    <span class="si-icon">{{ g.icon }}</span>
    <span class="si-name">{{ g.name }}</span>
  </div>
</div>

<!-- 各子类独立价格 -->
<div class="section" v-if="selectedSubs.length">
  <div class="sub-price" v-for="gid in selectedSubs" :key="gid">
    <div class="sp-label">{{ getGameName(gid) }}</div>
    <div class="price-row">
      <div class="price-col"><span>1小时</span><input type="number" v-model.number="subPrices[gid]" placeholder="50" /></div>
      <div class="price-col"><span>2小时</span><input type="number" v-model.number="subPrices2h[gid]" placeholder="90" /></div>
    </div>
  </div>
</div>
```

**关键JS模式**：
```js
// 用 reactive 存每个子类的价格（不要用 ref 对象）
const subPrices = reactive({})
const subPrices2h = reactive({})

function toggleSub(gid) {
  const idx = selectedSubs.value.indexOf(gid)
  if (idx >= 0) selectedSubs.value.splice(idx, 1)
  else if (selectedSubs.value.length < 10) {
    selectedSubs.value.push(gid)
    if (!subPrices[gid]) subPrices[gid] = 50    // 设置默认值
    if (!subPrices2h[gid]) subPrices2h[gid] = 90
  }
}
```

**子分类过滤**（延续游戏/同城ID范围规则）：
```js
const gameSubs = computed(() => allGames.filter(g => g.id < 8 || (g.id >= 15 && g.id <= 22)))
const travelSubs = computed(() => allGames.filter(g => (g.id >= 8 && g.id <= 14) || g.id >= 23))
```

**🔴 `v-model` 陷阱**：`v-model.number="subPrices[gid] || ''"` 会导致双向绑定失效（`||` 表达式不可写）。必须用 `v-model.number="subPrices[gid]"`，默认值在 toggle 时用 `if (!subPrices[gid]) subPrices[gid] = 50` 单独设置。

**取消大类时的清理**：取消「游戏达人」时，需同时移除该大类的所有子分类选择：
```js
if (type === 'game') selectedSubs.value = selectedSubs.value.filter(id => (id >= 8 && id <= 14) || id >= 23)
else selectedSubs.value = selectedSubs.value.filter(id => id < 8 || (id >= 15 && id <= 22))
```

### 支付页 JSAPI/Native 降级（pay.html 双平台自动适配）

**2026-07-17 修复**：支付页 `pay.html` 在非微信环境下仍会先调用 JSAPI 接口（需要微信 openid），导致「参数不完整」错误。

**修复**：
1. 无 `order_no` 参数时，非微信环境直接调用 `createNativePay()`（原生扫码），跳过 JSAPI
2. 微信环境先用 JSAPI，失败后 2 秒自动降级到 Native 扫码

```javascript
if (isWeChat) {
  // 微信内 → JSAPI 支付
  xhr.open('POST', '/api/pay/wxpay/jsapi', true);
  // ... 失败时 setTimeout(createNativePay, 2000)
} else {
  // 非微信 → 直接 Native 扫码
  createNativePay();
}
```

**修改文件**：`/opt/ttdazi/payment_service/templates/pay.html`

### 术语映射更新（2026-07-17）

| 旧术语 | 新术语 |
|--------|--------|
| 旅游搭子 → **同城达人** | 首页/列表/搭子页面 |
| 底部导航「陪陪」→ **搭子** | App.vue |
| 电竞技术交流/声音好听/耐心陪伴 | 轮播图第三个改为「信息对接平台/技能交流」 |

**修改文件**：`List.vue`、`Home.vue`、`Profile.vue`、`App.vue`、`Settings.vue`

**修改分类时需同步更新的文件：**
- `List.vue` — `isTravel ? filter(g=>...) : filter(g=>...)`
- `Home.vue` — `searchByGame()` 中的 `game.id >= 8 && <= 14` 判断
- `DemandHall.vue` — 分类筛选 computed 和 `subGames` 过滤
- `companion.py` — 后端 `WHERE game_id>=...` 条件

**规则**：新游戏 ID > 14，新旅游 ID 在 23~32。添加后必须在上述四个文件中同步更新 filter 条件。

### 登录方式与邮箱/密码登录（用户端）

用户端支持 **四种登录方式** 并存（2026-07-18 起）：
1. **微信一键登录** — `wxLogin()` → 跳转 `/api/wechat/login`（限微信内置浏览器）
2. **PC扫码登录** — Login.vue 的「扫码登录」Tab → 生成二维码 → 手机微信扫码确认 → PC自动登录（桌面/PC端推荐）
3. **邮箱/手机号 + 密码登录** — `POST /api/user/login`（支持 phone/email/username 三种账号字段）
4. **邮箱注册** — 走 `EmailRegister.vue` 验证码注册流程，注册后可用密码登录

📖 `references/pc-scan-login.md` — PC扫码登录完整实现文档

**后端启用记录**：
| 函数 | 之前状态 | 当前状态 |
|------|---------|---------|
| `user.py login()` | `return fail('仅支持微信登录')` | ✅ 正常执行 |
| `user.py register_by_email()` | `return fail('仅支持微信登录')` | ✅ 正常执行 |

### 术语映射（全站强制，合规要求，2026-07-17 新版）

| 旧术语 | 新术语 | 说明 |
|--------|--------|------|
| 搭子认证/激活 | → **展示/开通** | 搭子付费开通 |
| 认证有效 | → **展示中** | 状态标签 |
| 未激活 | → **未开通** | 状态标签 |
| 认证费 | → **展示服务费** | 费用说明 |
| 续费 | → **续期** | 续费按钮 |
| 已过期 | → **已到期** | 状态标签 |
| 接单/待接单 | → **对接/待对接** | 订单系统已移除 |
| 包夜 | → **长时间/3小时+** | 参考价格选项 |
| 定价 | → **参考价格** | 价格标签 |
| 游戏搭子(泛指) | → **搭子** | 导航/底部等通用场景 |
| 游戏技术指导 | → **信息对接** | 服务描述 |
| **旅游搭子** | → **同城达人** | 首页/列表/搭子页面（2026-07-17） |
| **底部导航「陪陪」** | → **搭子** | App.vue（2026-07-17） |
| **地陪翻译** | → **出行翻译** | game 表分类名（2026-07-17） |
| **电竞技术交流 / 声音好听 / 耐心陪伴** | → **信息对接平台 / 技能交流** | 首页轮播图第三个（2026-07-17） |
| **游戏搭子 / 旅游搭子**（设置页平台声明） | → **游戏达人 / 同城达人** | 所有合规声明（2026-07-17） |

### 游戏分类 ID 边界（2026-07-17 新增游戏后修复）

**症状**：新增游戏后（ID 15+），游戏搭子列表页不显示新游戏，或新游戏被归类到「旅游搭子」。

**根因**：前端硬编码 `g.id >= 8` 作为旅游判断条件。新游戏 ID 15+ 被错误归为旅游。

**修复**：旅游 ID 范围固定为 8~14，所有判断改为 `g.id >= 8 && g.id <= 14`。

**预防**：新游戏必须分配 ID > 14。添加后检查所有 `g.id >= 8` 条件。

### 分类栏自动换行
分类多时用 `flex-wrap: wrap`，勿用 `overflow-x: auto`。

### 🧩 `async onMounted` 时序陷阱 — auto confirm 不触发

**症状**：OAuth 回调后页面带 `auto=1` 参数跳回确认页，但自动确认从未执行。用户手动点确认按钮才有效。

**根因**：`onMounted` 中的 `await` 导致后续代码延迟执行，但 auto-confirm 检查写在 profile fetch 之前：

```javascript
// ❌ 有问题的顺序
onMounted(async () => {
  hasToken.value = !!localStorage.getItem('token') && !!user.id  // false
  const u = await api.get('/user/profile')                       // 异步
  hasToken.value = true                                          // 太晚了
  if (needAutoConfirm && hasToken.value) { doConfirm() }         // 永不执行
})
```

**修复**：所有依赖异步数据的 auto-action 必须放在 `await` 之后：

```javascript
onMounted(async () => {
  if (route.query.token) localStorage.setItem('token', route.query.token)
  let hasToken = !!localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  if ((route.query.token || localStorage.getItem('token')) && !user.id) {
    try { const u = await api.get('/user/profile')
      if (u?.id) { localStorage.setItem('user', JSON.stringify(u)); hasToken = true }
    } catch { hasToken = false }
  }
  // ✅ auto-action 在 await 之后，hasToken 是最终值
  if (route.query.auto === '1' && hasToken) setTimeout(() => doConfirm(), 500)
})
```

**关键规则**：Vue 的 `async onMounted` 中，`await` 之前代码是同步执行的。任何依赖异步结果的检查必须放在 `await` 之后。

**涉及场景**：OAuth 回调后自动确认、扫码登录自动确认、绑定手机后跳回确认页、任何 URL 参数带 token 需自动执行下一步的 SPA 页面。

### 付费节点总览

| 节点 | 付费方 | 金额 | 说明 |
|------|:----:|:----:|------|
| 👤 **浏览搭子** | 用户 | 免费 | 浏览资料、搜索 |
| 💬 **聊一聊/免费聊天** | 用户 | 免费 | 进入私聊 |
| 📝 **发布需求** | 用户 | 免费 | 发布需求 |
| 🔓 **查看需求详情** | 🏛️ 搭子 | ¥10 | 搭子在需求大厅查看用户信息 |
| 🟢 **搭子开通展示** | 🏛️ 搭子 | ¥19~¥899 | 按类型和时长付费开通展示 |
| ⏰ **到期续期** | 🏛️ 搭子 | 同上 | 到期自动下架，续期恢复 |

### 双重认证（游戏达人 + 同城达人）

**2026-07-17 起支持**：搭子可同时认证为「游戏达人」和「同城达人」，两种认证独立付费、独立到期。

**数据库**：
```sql
-- companion 表新增两个有效期字段
ALTER TABLE companion ADD COLUMN expires_at_game datetime DEFAULT NULL AFTER expires_at;
ALTER TABLE companion ADD COLUMN expires_at_travel datetime DEFAULT NULL AFTER expires_at;
```

**后端 order.py**（支付时按类型更新对应字段）：
```python
cert_col = 'expires_at_travel' if game_id >= 8 else 'expires_at_game'
cur.execute(f"UPDATE companion SET {cert_col} = DATE_ADD(NOW(), INTERVAL %s DAY) WHERE id=%s", (days, companion_id))
```

**后端 companion.py 列表查询**（按类型过滤）：
```python
if service_type == 'travel':
    where.append("(c.expires_at_travel IS NOT NULL AND c.expires_at_travel > NOW())")
elif service_type == 'game':
    where.append("(c.expires_at_game IS NOT NULL AND c.expires_at_game > NOW())")
else:
    where.append("((c.expires_at_game IS NOT NULL AND c.expires_at_game > NOW()) OR (c.expires_at_travel IS NOT NULL AND c.expires_at_travel > NOW()))")
```

**前端 PlaymateHome.vue**：显示两张独立状态卡（🎮 游戏达人 + 🏛️ 旅游达人），各有 ✅ 展示中 / ⚠️ 即将到期 / ❌ 已到期 / 🔄 未开通 四种状态。

**前端 CreateOrder.vue**：`goRenew(isTravel)` 接受布尔参数，跳转时带 `travel=1` 或 `travel=0`。

**费用配置键**（site_config 中）：
- 游戏：`game_cert_7d` / `game_cert_30d` / `game_cert_365d`
- 旅游：`travel_cert_7d` / `travel_cert_30d` / `travel_cert_365d`

### 展示费用分级（从 site_config 动态读取）

| 类型 | 7天 | 包月(30天) | 包年(365天) |
|:----:|:---:|:----------:|:-----------:|
| 🎮 **游戏达人或同城达人** | **¥19~¥69** | **¥69~¥199** | **¥369~¥899** |
| 🎮 **游戏达人或同城达人** | **¥19~¥69** | **¥69~¥199** | **¥369~¥899** |

**配置键**：`game_cert_7d` / `game_cert_30d` / `game_cert_365d` / `travel_cert_7d` / `travel_cert_30d` / `travel_cert_365d`

### 后端实现（order.py create 函数）

```python
order_type = data.get('type', 'visitor_chat')
amount = float(data.get('amount', 10))
days = int(data.get('days', 0))

# 如果是搭子激活，更新过期时间
if order_type == 'companion_activate' and days > 0:
    cur.execute("UPDATE companion SET expires_at = DATE_ADD(NOW(), INTERVAL %s DAY) WHERE id=%s", (days, companion_id))
```

### 数据库字段

```sql
ALTER TABLE companion ADD COLUMN expires_at datetime DEFAULT NULL AFTER chat_paid;
```

### 列表API过滤过期搭子

```python
where = ["c.status=1", "c.is_online=1", "u.status=1", "(c.expires_at IS NULL OR c.expires_at > NOW())"]
```

### 前端：详情页主人检测 + 按钮

```js
// 检查当前用户是否是本搭子主人
const user = JSON.parse(localStorage.getItem('user') || '{}')
isOwner.value = user.id && d.user_id && Number(user.id) === Number(d.user_id)

// 搭子本人看到"续期"，访客看到"聊一聊"
<template v-if="isOwner">
  <div class="dpb-renew">
    <div class="dpb-renew-label">展示{{ expiresText }}</div>
    <button class="dpb-go dpb-edit" @click="goOrder">续期</button>
  </div>
</template>
<template v-else>
  <div class="dpb-chat" @click="goChat">💬 聊一聊</div>
</template>
```

### 🔴 常见问题

- **PyMySQL `%s` 与 `%` 冲突**：SQL 中文字 `%`（如 `'95%'`）需写为 `'95%%'`，否则报 `unsupported format character`
- **城市选择器共享数据**：List.vue 和 Settings.vue 共用 `src/utils/cities.js`（34省份+300+城市），修改城市列表只改该文件即可

### 🔴 常见问题

- **推荐API缺少`u.city`**：recommend() SQL 查询没有 SELECT u.city，导致首页推荐卡片不显示城市
- **双域名支付**：`dazi.openai2000.cn` 和 `pay.openai2000.cn` 都必须添加 JS接口安全域名
- **Image Beacon 回调**：跨域 XHR 在 WeChat 中不可靠，改用 `new Image().src` 做 GET 回调
- **服务端确认**：`/api/pay/wxpay/confirm` 不能加 `@login_required`（页面跳转会丢失 token）
- **旧文件残留**：Vite hash 文件名堆积，需定期清理旧 `Detail-*.js` 和 `index-*.js` 文件

### 🔴 pay.html JSAPI 参数取错层级导致微信支付调起失败（2026-07-18 修复）

**症状**：微信浏览器内点「确认支付」→ 微信支付窗口不弹出 → 显示"jsapi 失败"。

**根因**：后端 `/api/pay/wxpay/jsapi` 返回 `{data:{amount, jsapi:{...}, order_no}}`，微信支付参数在 **`data.jsapi`** 中嵌套，但 pay.html 用了 `orderData = res.data`（取了整个 `data` 对象，包括 `amount`, `jsapi`, `order_no`），传给 `WeixinJSBridge.invoke()` 后微信找不到 `appId/timeStamp/package` 等字段。

```javascript
// ❌ 错误：取整个 data 对象
orderData = res.data;  // {amount:69, jsapi:{appId,timeStamp,...}, order_no:"JS..."}
WeixinJSBridge.invoke('getBrandWCPayRequest', orderData, cb);

// ✅ 正确：取 data.jsapi 才是微信需要的支付参数
orderData = res.data.jsapi || res.data;  // {appId, timeStamp, nonceStr, package, signType, paySign}
myOrderNo = res.data.order_no || myOrderNo;
WeixinJSBridge.invoke('getBrandWCPayRequest', orderData, cb);
```

**影响范围**：pay.html 中 `myOrderNoParam` 分支+无订单号分支共两处。

**完整修复**（2026-07-18 重写 pay.html）：
1. ✅ 两处 `orderData` 改为 `res.data.jsapi || res.data`
2. ✅ JSAPI 失败后立即 `createNativePay()`（旧版只显示错误不降级）
3. ✅ 微信内自动调起（无需手动点击"确认支付"按钮）
4. ✅ 监听 `WeixinJSBridgeReady` 事件处理 JSBridge 未就绪
5. ✅ PC端直接 Native 扫码（不变）

📖 `references/pay-html-jsapi-nesting-bug.md` — 完整修复记录

## 站内通知系统

### 数据库
```sql
CREATE TABLE notifications (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNSIGNED NOT NULL,
  title VARCHAR(100) NOT NULL,
  content VARCHAR(500) NOT NULL,
  type VARCHAR(30) DEFAULT 'system',
  related_id INT UNSIGNED DEFAULT NULL,
  is_read TINYINT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user (user_id, is_read)
);
```

### API 端点
| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/notify/list` | GET | 获取通知列表（分页） |
| `/api/notify/unread` | GET | 未读通知数 |
| `/api/notify/read` | POST | 标记已读（支持单条/全部） |

### 前端
- 组件：`Notifications.vue`，路由 `/notifications`
- 入口：底部导航「聊天」角标显示未读数（消息+通知合计）
- Profile：「消息通知」→ `/notifications`
- 定时轮询：App.vue 的 `fetchUnread()` 同时获取消息和通知未读数

### 发送通知
```python
from app.notification import send_notification
send_notification(user_id, '标题', '内容', type='system', related_id=0)
```

### 认证到期提醒
脚本 `/opt/ttdazi/scripts/check_expiry.sh` 每天凌晨4点运行（cron）：
1. 查询3天内到期的搭子
2. 发送站内通知
3. 自动下架已过期搭子（`is_online=0`）

## 一键举报系统

### 数据库
```sql
CREATE TABLE reports (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  reporter_id INT UNSIGNED NOT NULL,
  target_type VARCHAR(20) DEFAULT 'companion',
  target_id INT UNSIGNED NOT NULL,
  reason VARCHAR(200),
  detail TEXT,
  status TINYINT DEFAULT 0,
  handler_id INT DEFAULT 0,
  admin_note VARCHAR(500),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  processed_at DATETIME DEFAULT NULL
);
```

### API 端点
| 端点 | 方法 | 权限 | 功能 |
|------|------|------|------|
| `/api/report/create` | POST | `@login_required` | 提交举报 |
| `/api/report/list` | GET | 公开 | 举报列表（后台用） |
| `/api/report/process` | POST | `@admin_required` | 处理（封禁/驳回） |

**注意**：`admin_required` 装饰器从 `app.admin` 导入，不在 `app.utils`。

### 前端
- Detail.vue 右上角 🚩 按钮 → 弹窗选择举报原因 → 提交
- 举报后管理员在后台查看/处理

## 私聊系统 - 聊天入口分发

搭子详情页「聊一聊」和「免费聊天」都跳转到 `/service?companion_id=X&name=XX`，由 CustomerService.vue 处理：

- 有 `companion_id` → 走**搭子私聊**（`/api/chat/send` + `/api/chat/messages`）
- 无 `companion_id` → 走**客服消息**（`/api/cs/send` + `/api/cs/history`）

**API 路径区别**：
| 场景 | 发送 | 历史记录 |
|------|------|---------|
| 搭子私聊 | `/api/chat/send` (带 `to_id`) | `/api/chat/messages?user_id=X` |
| 客服对话 | `/api/cs/send` | `/api/cs/history` |

**`/api/chat/messages` 返回格式**：直接返回 `data: [{id,from_id,to_id,content,...}]`（数组），前端接收后根据 `from_id` 判断消息方向：
```js
const userId = JSON.parse(localStorage.getItem('user') || '{}').id || 0
const msgList = Array.isArray(res) ? res : (res?.messages || [])
messages.value = msgList.map(m => ({
  ...m, is_admin: Number(m.from_id) !== Number(userId)
}))
```

**敏感词拦截**：`/api/chat/send` 内部调用 `check_and_punish(content, user_id, '聊天消息')`，命中敏感词则消息发送失败。

## 合规弹窗（聊天页倒计时）

CustomerService.vue 进入聊天时自动弹出⚠️合规提醒，带倒计时：

```js
const countdown = ref(3)
const cdTimer = setInterval(() => { countdown.value--; if (countdown.value <= 0) clearInterval(cdTimer) }, 1000)
```

按钮文字实时显示倒计时：`请阅读 3秒 → 2秒 → 1秒 → 我知道了`
倒计时结束按钮才可关闭（`:disabled="countdown > 0"`）。

## 信息服务套餐模式（替代充值）

**定位**：平台收取的是**信息匹配服务费**（信息中介服务报酬），非游戏娱乐服务费。

**前端实现**（Recharge.vue）：显示套餐卡片列表，用户选择套餐后跳转到 pay.openai2000.cn 支付。

**套餐定义**：
```js
packages = [
  { name: '单次匹配', desc: '完成1次信息对接匹配', price: 10 },
  { name: '5次套餐', desc: '5次信息匹配对接，立省20%', price: 40, original: 50 },
  { name: '10次套餐', desc: '10次信息匹配对接，立省30%', price: 70, original: 100 },
  { name: '包月无限', desc: '30天内无限次匹配对接', price: 199, popular: true },
  { name: '季度无限', desc: '90天内无限次匹配对接', price: 499 },
]
```

**支付流程**：前端只跳转，pay.html 创建订单，页面传递 subject 参数（套餐名），微信备注显示"同途搭子-信息匹配服务¥xxx"。

**关键词替换清单**：
| 旧 | 新 |
|----|----|
| 充值中心 | 信息服务 |
| 充值金额 | 服务金额 |
| 充值记录 | 购买记录 |
| 充值成功 | 已生效 |
| 同途搭子-充值 | 同途搭子-信息匹配服务 |

**注意**：配合 `game-platform-compliance` 技能合规指南使用。

### 搭子列表默认query
```sql
WHERE c.status=1 AND c.is_online=1 AND u.status=1
```
列表返回 `{list, total, page, page_size}`，前端取 `res.list`。

## 综合/首页推荐（recommend）排序规则
```sql
ORDER BY c.is_online DESC, smart_score DESC
```
`smart_score = score*30 + order_count*0.5 + good_rate*0.2`

## 邮箱注册API流程
1. `POST /api/user/send-email-code` — 发送验证码
2. `POST /api/user/verify-email-code` — 验证
3. `POST /api/user/register-by-email` — 注册

email拼接：`emailName + '@' + emailDomain`（域名列表不带`@`前缀）

### 🔴 邮箱注册 phone 字段被填入邮箱地址

**症状**：设置页显示「手机号：xxx@qq.com」（邮箱地址替代了手机号），`user.phone` 和 `user.email` 值相同。

**根因**：邮箱注册 SQL：
```python
# 后端 app/user.py - register_by_email()
cur.execute(
    "INSERT INTO `user` (username, phone, email, password, nickname, ...) VALUES (%s, %s, %s, %s, %s, ...)",
    (email, email, email, ...)  # ← phone 也被传了 email！
)
```

**修复**：
1. 后端：`phone` 参数改为 `''`（空字符串）
2. 数据库（补丁）：`UPDATE user SET phone=NULL WHERE phone=email AND email != ''`（注意 phone 字段可能为 NOT NULL，需要改用唯一占位符）
3. 前端显示保护：设置页手机号展示加正则过滤
```html
<span class="mi-desc">{{ user.phone && /^1\d{10}$/.test(user.phone) ? maskPhone(user.phone) : '未绑定' }}</span>
```

### 🔴 `encodeURIComponent` + Vue Router 双重编码

**症状**：私聊跳转URL显示 `name=%25E5%25B7%2585...`（`%25`是`%`的编码），页面显示乱码昵称。

**根因**：
```js
// ❌ 错误：双重编码
const name = encodeURIComponent(order.nickname || '搭子')
router.push({ path: '/chat', query: { user_id: uid, name: name } })
// Vue Router 对 query 值再做一次 encodeURIComponent
// 结果：name 被编码两次，变成 %25XX%25XX...
```

**修复**：直接传原始字符串，Vue Router 自动处理编码：
```js
// ✅ 正确
router.push({ path: '/chat', query: { user_id: uid, name: order.nickname || '搭子' } })
```

**适用于**：所有通过 `router.push({ query: {...} })` 传参的地方。不要在 query 值上预先调用 `encodeURIComponent`。

### 🔴 deploy.sh 的成功误报

**症状**：`deploy.sh` 输出 `✅ 前端编译完成`，但实际上 `npm run build` 失败了（输出 `error during build:`）。

**根因**：`deploy.sh` 只检查 `npm run build` 的 exit code 是否为 0，但 vite 构建错误时 exit code 可能仍为 0（取决于错误类型）。

**排查方法**：
```bash
# 直接运行 build，看最后是否有 "✓ built in Xs"
npm run build 2>&1 | tail -5
# 如果有 "error during build:"，构建失败
# 如果有 "✓ built in 9.53s"，构建成功
```

**常见构建失败原因**：
1. `function X` 用了 `await` 但没加 `async`
2. 模板缺少 `</template>` 闭合标签
3. CSS 块有多余的 `}` 或不匹配的括号
4. `patch` 工具写入了字面量 `\\n` 导致 CSS 语法错误

### `async` 缺失导致构建失败

**症状**：Vite 报 `Unexpected reserved word 'await'`，指出 `await` 不在 `async` 函数内。

**根因**：`function foo() { await bar(); }` — 缺少 `async` 关键字。常见于添加新功能时复制了已有 `async function` 的 `try/await` 代码块但没有把 `function` 改为 `async function`。

**后果**：整个生产构建失败（`error during build:`），所有页面的修改都不会部署。`deploy.sh` 可能误报成功。

**排查**：运行 `npm run build` 观察输出末尾。如果有 `error during build:` 但无 `✓ built in Xs`，说明构建失败。

**修复**：
```bash
# 找到所有使用 await 但不是 async 的函数
grep -n "await" file.vue
# 对比对应的 function 签名
grep -n "function.*{" file.vue
# 修复：function → async function
```

**预防**：在 `.vue` 文件中任何使用 `await` 的地方，函数签名必须有 `async` 关键字。常见的漏掉场景：在现有非 async 函数中插入一段带 `await` 的 try/catch 代码块。

### 构建排错

### 🔴 构建排错：`async` 缺失导致构建静默失败

**症状**：Vite 报 `Unexpected reserved word 'await'`，指出 `await` 不在 `async` 函数内。
**后果**：整个生产构建失败（`error during build:` 但无 `✓ built in`），所有页面的修改都不会部署。`deploy.sh` 可能输出 `✅ 前端编译完成` 误报成功。

**排查方法**：
```bash
# 不要依赖 deploy.sh 的输出，直接看 build 输出末尾
npm run build 2>&1 | tail -5
# 如果最后一行的结尾是 "✓ built in Xs" → 成功
# 如果有 "error during build:" → 失败
```

**常见原因**：在 `function` 中插入 `await` 但漏加 `async` 关键字。

**修复**：
```bash
grep -n "await" file.vue  # 找到所有 await 的行
grep -n "function" file.vue  # 对比函数签名，寻找缺失 async 的地方
```

### 构建排错：Vue 模板缺少 `</template>` 标签

**症状**：Vite 构建报错 `Element is missing end tag`，且报错位置指向文件第一行（1:1），实际问题在模板末尾缺少 `</template>`。

**排查方法**：
```bash
# 检查模板开闭标签数量是否匹配
grep -c "<template>" file.vue    # 应为1
grep -c "</template>" file.vue   # 应为1
```

**根因**：频繁使用 `patch` 工具修改文件时，可能误删 `</template>` 闭合标签行。后果是整个构建失败，所有文件的修改都不会部署。

**修复**：在 `<script setup>` 前补上 `</template>`：
```
content = content.replace('\n<script setup>', '\n</template>\n\n<script setup>')
```

### Vue 3 模板不能直接访问 `sessionStorage` / `window` 全局变量

**症状**：`TypeError: Cannot read properties of undefined (reading 'getItem')` 或 `Cannot read properties of undefined (reading 'sessionStorage')`，报错在 AdminSidebar 等模板中使用 `sessionStorage` 的组件。

**根因**：Vue 3 SFC 模板编译器的变量解析顺序：
1. 组件 setup 绑定（refs, reactive）
2. 组件 props
3. 全局 app 属性
4. 内置全局白名单（`Math`, `Date`, `Array`, `Object`, `JSON`, `isNaN`, `parseInt`, `parseFloat`, `RegExp`, `Map`, `Set`, `Promise`, `console`, `setTimeout`, `clearTimeout`, `setInterval`, `clearInterval`）

`sessionStorage`、`window`、`location`、`navigator` **不在白名单内**。模板中引用时 Vue 会尝试从组件上下文查找，找不到返回 `undefined`。

```html
<!-- ❌ 错误：Vue 在组件上下文中找不到 sessionStorage -->
<div :class="{ active: isActive(`/${sessionStorage.getItem('path')}/`) }">

<!-- ❌ 仍然错误：Vue 把 window 当组件属性查找 -->
<div :class="{ active: isActive(`/${window.sessionStorage.getItem('path')}/`) }">
```

**修复**：在 `<script setup>` 中读取全局变量，模板引用变量名：

```html
<template>
  <div :class="{ active: isActive(`/${adminPath}/`) }">
</template>

<script setup>
const adminPath = sessionStorage.getItem('admin_route_path') || 'op-ztHWaT-0706'
</script>
```

**注意**：这种方式只适合初始化时读取（组件创建时）。如果路径会动态变化（如管理后台路径轮换后的刷新），需要在 App.vue 的 `onMounted` 中检测路径变化并 `window.location.reload()` 让路由器用新路径重新创建。

### `companion_user_id` 缺失导致私聊跳转失败

**症状**：私聊按钮点击后导航到 `/chat?user_id=2` 而非正确的 `user_id=10002`。

**根因**：订单 API 返回 `companion_id`（搭子表ID，如 `2`），但私聊系统需要 `user_id`（用户表ID，如 `10002`）。前端直接用 `companion_id` 传参会错误的用户。

**修复**：
1. 后端 order.py 的订单列表查询需加上 `c.user_id as companion_user_id`：
```python
SELECT o.*, c.id as companion_id, c.user_id as companion_user_id, u.nickname ...
FROM orders o
JOIN companion c ON c.id = o.companion_id
JOIN user u ON u.id = c.user_id
```
2. 前端 `chatWithCompanion(order)` 函数用 `order.companion_user_id`（不是 `order.companion_id`）
3. 其他页面同理：需求大厅用 `d.user_id`（需求发布者），搭子端用 `order.user_id`（下单用户）

### CSS 类名不匹配导致组件无样式

**症状**：Vue 组件渲染了 HTML 结构（开发者工具中可看到元素），但没有任何 CSS 样式应用——白色背景、默认字体、无边框无圆角。

**根因**：模板使用的 CSS 类名与 scoped style 中定义的类名不一致。常见于从其他页面复制模板但忘记更新 CSS 类名。

检查方法：
```bash
# 列出模板中使用的类名
grep -oP 'class="[^"]*"' component.vue | tr ' ' '\n' | sort -u
# 列出 scoped style 中定义的类名
sed -n '/<style scoped>/,/<\/style>/p' component.vue | grep -oP '^\.[a-zA-Z_-]+' | sort -u
# 对比两个列表，找出不匹配的类
```

确保模板中的每个类名在 scoped style 中有对应定义。特别是从其他页面复制代码时，CSS 类名可能使用不同的命名约定。

### `patch` 工具 CSS 多行转义 Bug

`patch` 工具在处理 CSS 多行替换时，可能将 `\n`（换行符）序列化为字面量 `\\n`（反斜杠+n）。

**症状**：构建报 CSS 语法错误，检查文件发现 `.class {\\n  property: value;\\n}` 形式的伪换行。

**修复方案（按优先级）**：
1. **首选**：用 `terminal` + `python3` 做 `content.replace('old', 'new')` + `with open(path, 'w')`
2. **次选**：用 `execute_code` 工具做文件读写
3. **补救**：用二进制替换修复：
```python
with open('file.vue', 'rb') as f:
    data = f.read()
data = data.replace(b'\\\\n', b'\n').replace(b'\\n', b'\n')
with open('file.vue', 'wb') as f:
    f.write(data)
```

**预防**：涉及多行 CSS 替换时，不使用 `patch` 工具。改用 Python 脚本直接操作文件。

## 城市定位（城市选择器，2026-07-17 重写）

**注意**：旧方案使用 GPS + IP 定位（`ip-api.com`/`ipinfo.io`），因中国 IP 数据库不准（青岛→济南、青岛→嘉兴等），已**全部替换为城市选择器**。

### 当前实现（Settings.vue）

用户点击城市行 → 弹出城市选择器 → 选择城市 → 保存到 `user.city`。

```html
<!-- 城市行 -->
<div class="menu-item-3d no-3d">
  <div class="mi-icon">📍</div>
  <div class="mi-info"><div class="mi-title">城市</div></div>
  <div class="city-edit">
    <span class="city-val" @click="showCityPicker = true">{{ userCity || '点击选择' }}</span>
    <button class="loc-btn" @click="showCityPicker = true">切换</button>
  </div>
</div>

<!-- 城市选择器弹窗 -->
<div class="city-picker-overlay" v-if="showCityPicker">
  <div class="city-picker-box">
    <div class="cp-header">
      <span class="cp-title">选择城市</span>
      <span class="cp-close" @click="showCityPicker=false">✕</span>
    </div>
    <div class="cp-search">
      <input v-model="citySearch" placeholder="搜索城市..." class="cp-input" />
    </div>
    <div class="cp-list">
      <div class="cp-item" :class="{ active: !userCity }" @click="selectCity('')">不显示城市</div>
      <div class="cp-item" v-for="c in filteredCities" :key="c" :class="{ active: userCity === c }" @click="selectCity(c)">{{ c }}</div>
    </div>
  </div>
</div>
```

### JS 逻辑

```js
const showCityPicker = ref(false)
const citySearch = ref('')
const userCity = ref('')
const CITY_LIST = ['北京市','上海市','广州市','深圳市','杭州市','成都市','青岛市',...]

const filteredCities = computed(() => {
  if (!citySearch.value) return CITY_LIST
  return CITY_LIST.filter(c => c.includes(citySearch.value.trim()))
})

function selectCity(c) {
  userCity.value = c
  showCityPicker.value = false
  if (c) { safeToast('已设置城市：' + c) }
  else { safeToast('已隐藏城市') }
  updateCity()
}

function updateCity() {
  if (userCity.value) api.put('/user/update', { city: userCity.value }).then(() => {
    updateLocal({ city: userCity.value })
  }).catch(() => {})
}
```

### 注意事项
- 删除了旧的 `getLocation()`、`reverseGeo()`、`locating` ref
- 删除了 `navigator.geolocation` GPS 定位代码（用户常拒绝权限）
- 删除了 `/api/config/geoip` 后端接口依赖（青岛定位为济南/嘉兴的问题不复存在）
- 腾讯位置服务 demo key `OB4BZ-D4W3U-B7VVO-4PJWW-6TKDJ-WPB77` 不支持 WebserviceAPI，已废弃
- 城市列表硬编码在 `CITY_LIST` 中，内置 60+ 常见城市

### 🔴 WxLogin.vue 未保存 user 数据导致成为搭子/开通续费失败（2026-07-18 修复）

**症状**：微信登录成功后，点击"成为搭子"或"开通续期"等按钮报错或重定向到实名认证页。

**根因**：`WxLogin.vue` 保存了 `token` 和 `refresh_token`，但**没有获取并保存用户信息**到 `localStorage`：
```js
// ❌ 错误：只保存 token，不保存 user 数据
localStorage.setItem('token', token)
localStorage.setItem('refresh_token', route.query.refresh_token || '')
// 缺少 localStorage.setItem('user', JSON.stringify(...))
```

导致 `CompanionRegister.vue` 中 `JSON.parse(localStorage.getItem('user') || '{}').verify_status` 为 `undefined`，判断条件 `undefined !== 2` 为 `true` → 重定向到实名认证页。

**修复**：微信登录成功后，调 `/user/profile` API 获取用户信息并保存：
```js
onMounted(async () => {
  const token = route.query.token || ''
  nickname.value = route.query.nickname || '微信用户'
  if (token) {
    localStorage.setItem('token', token)
    localStorage.setItem('refresh_token', route.query.refresh_token || '')
    // ✅ 获取用户信息并保存
    try {
      const api = (await import('@/api')).default
      const userData = await api.get('/user/profile')
      if (userData && userData.id) {
        localStorage.setItem('user', JSON.stringify(userData))
      }
    } catch(e) { /* 静默处理 */ }
    setTimeout(() => router.replace('/'), 1500)
  }
})
```

**对比清单** — 微信登录后必须执行的三步：
| 步骤 | Login.vue（密码登录） | WxLogin.vue（微信登录） |
|------|---------------------|----------------------|
| 1️⃣ 存 token | ✅ `setItem('token', r.token)` | ✅ `setItem('token', token)` |
| 2️⃣ 存 refresh_token | ✅ `setItem('refresh_token', r.refresh_token)` | ✅ `setItem('refresh_token', route.query.refresh_token)` |
| 3️⃣ 存 user 数据 | ✅ `setItem('user', JSON.stringify(r))` | ⚠️ 需调 `/user/profile` 获取后保存 |

**排查**：微信登录后查看 localStorage：
```bash
# 浏览器控制台
> localStorage.getItem('user')  # 应为 {...}，若为 '{}' 则是丢失
> localStorage.getItem('token')  # 应有值
> localStorage.getItem('refresh_token')  # 应有值
```

**影响**：所有依赖 `localStorage.getItem('user')` 的功能（实名认证检查、搭子身份判断、详情页主人检测）都会受影响。

### 🔴 `order/create` 搭子认证续期强制校验 companion.status=1 导致续期失败（2026-07-18 修复）

**症状**：搭子点击“微信支付” → 提示“游戏搭子不存在”。新注册搭子（`status=0` 待审核）无法完成续期。

**根因**：`order.py` 的 `create()` 查询强制 `WHERE id=%s AND status=1`，但 `companion_activate` 应允许 `status=0`（支付的是认证有效期，不是审核状态）。

**修复**：
```python
# 搭子激活/续期允许 status=0，其他情况需要 status=1
if order_type == 'companion_activate':
    cur.execute("SELECT id, user_id FROM companion WHERE id=%s", (companion_id,))
else:
    cur.execute("SELECT id, user_id FROM companion WHERE id=%s AND status=1", (companion_id,))
```
同时增加所有者验证：`if companion['user_id'] != user_id: return fail('只能给自己的搭子续期')`

### 🔴 Login.vue / WxLogin.vue / BindPhone.vue 未保存 refresh_token 导致30分钟强制退出（2026-07-17+20 修复）

**症状**：登录后约30分钟自动退出，需重新登录。控制台可见 401 → refresh 失败 → 跳转登录页。

**根因**：
- `ACCESS_TOKEN_TTL = 7200`（2小时），但无 refresh_token 则过期后无法续期
- Login.vue/WxLogin.vue/BindPhone.vue 登录成功未保存 `refresh_token` 到 localStorage
- `api/index.js` 的 401 拦截器尝试用 `localStorage.getItem('refresh_token')` 刷新，但该值为空
- **WxLogin.vue 更大 Bug**：`refreshToken` 变量未定义（`ReferenceError`），页面直接崩溃不跳转
- **后端 `wechat_login.py`** OAuth 回调使用旧版 `create_token()`（纯JWT），未生成 `refresh_token`，跳转URL只传了 `token`

**修复清单（必须同步改 3 个前端文件 + 1 个后端文件）**：

#### 后端：`wechat_login.py` — OAuth回调必须用 v2 token 系统
```python
# 替换 create_token(user_id, openid[:16]) 为：
from app.token_auth import gen_token, gen_refresh_token
from urllib.parse import urlencode

device_id = f'wx_{openid[:8]}'
access_token = gen_token(user_id, device_id)
refresh_tok = gen_refresh_token(user_id, device_id)
params = urlencode({'token': access_token, 'refresh_token': refresh_tok, 'nickname': nickname})
# 跳转URL带 refresh_token
return redirect(f'https://dazi.openai2000.cn/#/wx-login?{params}')
# 或绑定手机号页：
return redirect(f'https://dazi.openai2000.cn/#/bind-phone?{params}')
```

#### 前端：`Login.vue doLogin()` — 从 API 响应保存
```js
localStorage.setItem('token', r.token)
localStorage.setItem('refresh_token', r.refresh_token || '')  // ← 缺这行
localStorage.setItem('user', JSON.stringify(r))
```

#### 前端：`WxLogin.vue` — 从 URL query 参数读取（注意：不能用未定义变量！）
```js
// ❌ 错误：refreshToken 未定义 → ReferenceError 页面崩溃
localStorage.setItem('refresh_token', refreshToken || '')

// ✅ 正确：从 route.query 读取
localStorage.setItem('token', token)
localStorage.setItem('refresh_token', route.query.refresh_token || '')  // ← 改这里
```

#### 前端：`BindPhone.vue` — 同样需要保存
```js
localStorage.setItem('token', token.value)
if (route.query.refresh_token) localStorage.setItem('refresh_token', route.query.refresh_token)  // ← 补上行
```

#### token 参数调整（可选）
```python
# token_auth.py
ACCESS_TOKEN_TTL = 7200       # 30分 → 2小时（2026-07-17 调整）
REFRESH_TOKEN_TTL = 604800    # 7天（不变）
```

**排查方法**（登录后30分钟自动退出且控制台401）：
```bash
# 检查 localStorage 中是否有 refresh_token
grep -n "refresh_token" frontend/src/views/WxLogin.vue       # 应该从 route.query 读取
grep -n "refresh_token" frontend/src/views/Login.vue          # 应该从 r.refresh_token 读取
grep -n "refresh_token" frontend/src/views/BindPhone.vue      # 应该从 route.query 读取
# 检查后端是否生成并传递 refresh_token
grep -n "gen_refresh_token\\|refresh_tok" backend/app/wechat_login.py
```

### 🔴 `user/profile` API 缺少 `verify_status` 和 `real_name`

**症状**：收入页面的「已完成实名认证」提示不显示，因为 `account.verifiedName` 始终为空。

**根因**：后端 `/api/user/profile` 的 SQL 查询未包含 `verify_status` 和 `real_name` 字段：
```python
# ❌ 缺失字段
SELECT u.id, u.username, u.nickname, u.avatar, u.gender, u.city,
       u.role, u.score, u.order_count, u.points, u.favorite_count,
       u.created_at FROM user u WHERE u.id=%s
```

**修复**：在 SELECT 中添加 `u.verify_status, u.real_name`。

**注意**：`real_name` 仅在 `verify_status=1`（已认证）时有值。未认证用户的 `real_name` 为空字符串或 NULL。

### 收款账户绑定后不可修改

**模式**：类似手机号绑定的「一次绑定不可修改」策略也适用于支付宝账号和收款人姓名。

**后端实现**：
```python
# 检查是否已绑定
cur.execute("SELECT alipay_account, account_name FROM companion WHERE id=%s", (cid,))
existing_acct = cur.fetchone()
if existing_acct:
    if existing_acct['alipay_account'] and data.get('alipay_account') and data['alipay_account'] != existing_acct['alipay_account']:
        return fail('支付宝账号已绑定，不可修改')
    if existing_acct['account_name'] and data.get('account_name') and data['account_name'] != existing_acct['account_name']:
        return fail('收款人姓名已绑定，不可修改')
    # 首次设置（当前为空）
    if not existing_acct['alipay_account'] and data.get('alipay_account'):
        cur.execute("UPDATE companion SET alipay_account=%s WHERE id=%s", (data['alipay_account'], cid))
    if not existing_acct['account_name'] and data.get('account_name'):
        cur.execute("UPDATE companion SET account_name=%s WHERE id=%s", (data['account_name'], cid))
```

**前端实现**：
```html
<div v-if="!account.alipay">
  <input v-model="account.alipay" placeholder="输入支付宝账号" />
</div>
<div v-else class="af-item locked">
  <span class="af-val">{{ account.alipay }}</span>
  <span class="af-lock">🔒</span>
</div>
```

### 🔴 `audit_log` 函数不存在导致 500 崩溃

**症状**：点击后台「通过/拒绝」按钮无响应，后端日志报 `NameError: name 'audit_log' is not defined`。

**根因**：admin.py 中不存在 `audit_log` 函数。该函数既不在 `utils.py` 中，也不在 `admin.py` 内定义。代码中的 `audit_log(...)` 是通过 `cur.execute("INSERT INTO audit_log ...")` 直写数据库实现的，但函数名不存在于 import 或定义中。

**排查**：
```bash
# 检查 audit_log 是否在任何地方定义
grep -n "def audit_log" /opt/ttdazi/backend/app/*.py
# 检查当前用法
grep -n "audit_log(" /opt/ttdazi/backend/app/admin.py
```

**修复**：
1. 删除 `audit_log(...)` 函数调用
2. 替换为直接 SQL：
```python
cur.execute(
    "INSERT INTO audit_log (user_id, action, detail) VALUES (%s, %s, %s)",
    (request.current_user['user_id'], 'verify_approve', f'实名认证通过(uid={uid})')
)
```

**预防**：在添加函数调用前，先用 `grep -rn "def FUNCTION_NAME"` 确认函数确实存在。

### 🔴 添加 `reactive` / `computed` / `watch` 时漏了 import

**症状**：`ReferenceError: reactive is not defined` / `ReferenceError: computed is not defined` / `ReferenceError: watch is not defined`。

**根因**：在已有 `<script setup>` 中新增 `reactive({})`、`computed(()=>...)` 或 `watch(()=>..., ...)`，但 `import { ref } from 'vue'` 未同步添加 `reactive` / `computed` / `watch`。

**后果**：运行时直接抛 `ReferenceError`，被 App.vue `onErrorCaptured` 捕获后弹出「页面加载出错，建议刷新」Toast。构建可能成功（Vite 不会报错），页面完全无法使用。

**修复**：
```js
// ❌ 缺 reactive
import { ref, computed, onMounted } from 'vue'
// ✅ 补上
import { ref, reactive, computed, onMounted } from 'vue'
```

**排查方法**：检查浏览器控制台（不是构建输出），找 `ReferenceError: XXX is not defined`。`onErrorCaptured` 的错误日志中会包含完整的组件名称和错误消息。

**常见遗漏场景**：
- 每个子类独立存储价格（`const subPrices = reactive({})`）
- 给列表页添加 filter tabs（`const filteredList = computed(...)`）
- 给表单添加计算校验（`const canSubmit = computed(...)`）
- 添加 watch 响应数据变化

### 🔴 `companion` 表不存在 `nickname` 列导致 500

**症状**：搭子审核通过时返回「服务器内部错误」，日志报 `Unknown column 'nickname' in 'field list'`。

**根因**：`nickname` 在 `user` 表，不在 `companion` 表。查询 `SELECT user_id, nickname FROM companion WHERE id=%s` 会报错。

**排查**：
```bash
DESCRIBE companion;  # 检查有哪些列
# nickname 在 user 表，不在 companion 表
```

**修复**：只查 `user_id`，不查 `nickname`：
```python
# ❌ 错误
cur.execute("SELECT user_id, nickname FROM companion WHERE id=%s", (cid,))
# ✅ 正确
cur.execute("SELECT user_id FROM companion WHERE id=%s", (cid,))
```

**关联**：所有 `JOIN user` 的查询中，`nickname` 带 `u.` 前缀（如 `u.nickname`）才正确。

### 🔴 `git checkout` 回退带回了旧 Bug

**症状**：`git checkout -- file.vue` 回退文件后，之前已修复过的 Bug 重新出现（如 `margin-left: 220px` 布局偏移）。

**根因**：`git checkout` 恢复到 Git 中最近一次 commit 的版本，不保留未 commit 的修复。如果最近的 commit 是在 Bug 修复前，checkout 会带回所有旧问题。

**排查**：先检查 Git 状态确认文件是否包含未提交的修复：
```bash
git log --oneline -3 path/to/file.vue    # 查看文件的最近提交
git diff HEAD -- path/to/file.vue         # 对比工作区和 HEAD
```

**安全回退替代方案**：
- 用 `git revert <commit-hash>` 回退某个 commit（保留后续修复）
- 用版本号参数恢复特定 commit 的版本：`git checkout <hash> -- file`
- 手动编辑文件删除不需要的部分

### goPlaymate() 跳转到不存在的路由 `/apply`

**症状**：我的页面 → 我的陪玩 → 页面白屏打不开（跳转到不存在的路由）。

**根因**：Profile.vue 的 `goPlaymate()` 函数：
```js
// ❌ 错误：/apply 路由不存在
if (r && r.id) { router.push('/playmate/') }
else { router.push('/apply') }          // ← 这里应该跳转到 /companion/register
```

**排查**：写新入口函数时，确认 `router.push()` 的目标路由在 `router/index.js` 中存在：
```bash
grep "'/apply'" /opt/ttdazi/frontend/src/router/index.js || echo "❌ 无此路由"
```

### 🔴 admin 后台验证码与仅微信登录的冲突

密码登录改为「仅支持微信登录」后，管理后台 `/api/admin/login` 仍需要验证码，但 captcha 页面可能无法正常显示，导致管理员无法登录。

**注意**：admin 登录使用的是独立端点 `/api/admin/login`，不是 `/api/user/login`。修改 user 登录不影响 admin 登录。

**处理**：临时注释掉 admin login 的验证码检查：
```python
# admin.py login() 中
# from app.captcha import require_captcha
# ok, msg = require_captcha(...)
```
恢复密码登录后需取消注释。

### 🔴 页面水平滚动（overflow-x: hidden 缺失）

**症状**：「我的」页面或其他页面可以左右滑动，布局错乱。

**根因**：`.page-container { max-width: 100vw; }` 缺少 `overflow-x: hidden`。

**修复**：在 `frontend/src/assets/global.css` 中添加：
```css
.page-container { overflow-x: hidden; }
```

详见 📖 `references/page-container-horizontal-scroll.md`

### 微信 OAuth 回调中 cur 在 with 块外使用

**错误**：`pymysql.err.OperationalError: (1054, "Unknown column 'wx_openid'")` 或 `while self.nextset()`。

**根因1**：`user` 表缺少 `wx_openid` 字段。首次部署微信OAuth时需手动添加：
```sql
ALTER TABLE `user` ADD wx_openid VARCHAR(64) DEFAULT '' COMMENT '微信openid';
ALTER TABLE `user` ADD INDEX idx_wx_openid (wx_openid);
```

**根因2**：OAuth 回调中 `with conn.cursor() as cur:` 块结束后继续使用 `cur`。修复：把 phone_bound 的查询移到 with 块内，用变量保存结果后在块外引用。

## 登录方式与邮箱/密码登录（用户端）

用户端支持 **三种登录方式** 并存（2026-07-16 起）：
1. **微信一键登录** — `wxLogin()` → 跳转 `/api/wechat/login`
2. **邮箱/手机号 + 密码登录** — `POST /api/user/login`（支持 phone/email/username 三种账号字段）
3. **邮箱注册** — 走 `EmailRegister.vue` 验证码注册流程，注册后可用密码登录

### 前端登录页（Login.vue）

- 两个 Tab：「微信登录」和「账号密码」
- 「账号密码」Tab 显示：邮箱/手机号输入框 + 密码输入框 + 图形验证码 + 登录按钮
- 底部「还没有账号？邮箱注册」链接到 `/email-register`
- 需要导入 `safeToast`（2026-07-16 补加，修复登录错误无提示问题）

### 后端启用记录

| 函数 | 位置 | 之前状态 | 当前状态 |
|------|------|---------|---------|
| `user.py login()` | 第90行 | `return fail('仅支持微信登录')` | ✅ 正常执行 |
| `user.py register_by_email()` | 第763行 | `return fail('仅支持微信登录')` | ✅ 正常执行 |
| `user.py register()` | 第36行 | `return fail('仅支持微信登录')` | ⚠️ 仍禁用（手机号注册，暂不需恢复） |

### 注意事项

- `login()` 的 SQL 查询已支持 `WHERE phone=%s OR username=%s OR email=%s`，邮箱和手机号均可登录
- 图形验证码为数学题（`a + b = ?`，`a - b = ?`，`a × b = ?`），答案在 `captcha_log` 表中
- 验证码图片使用 PIL 生成，英文文字显示

## 登錄方式切换模式

平台可能要求从「多方式登录」切换到「仅微信登录」（或反之），影响多个层面：

### 前端改动
1. 路由：移除 `/register`、`/follow-register`、`/email-register` 等注册页路由
2. 登录页：删除密码/验证码输入框 + 底部注册链接，仅保留微信按钮
3. Profile.vue：`goTo()` 如果跳转到 `/register` 需改为 `/login` 或 `/wx-login`
4. API 拦截器：`/api/user/login` 等接口会返回 1（错误），前端需处理而不是重试刷新 Token

### 后端改动
1. `user.py`：`login()`、`register()`、`register_by_code()`、`register_by_email()` 返回值改为 `fail('仅支持微信登录')`
2. ⚠️ **admin 登录是独立接口**（`/api/admin/login`），不受 `/api/user/login` 修改影响

### 管理后台验证码去除

如果 captcha 图片不显示（或数据库 captcha_log 表被清理），管理员无法登录。临时修复：注释掉 `admin.py` 中的验证码检查：
```python
# from app.captcha import require_captcha
# ok, msg = require_captcha(...)
```

### 实名认证模式切换

用户可在「仅姓名+身份证号」和「含上传身份证正反面」两种模式间切换：
- 简单模式：`Verification.vue`（仅输入框）
- 完整模式：`VerifyIdentity.vue`（含文件上传 + OCR）
- 修改路由：`{ path: '/verify', component: () => import('@/views/Verification.vue') }` vs `VerifyIdentity.vue`
- 切换时需重建 `dist/`，否则旧组件缓存仍生效

### 实名认证双表同步（user ↔ verify_application）

**架构**：用户提交实名认证时，数据写入 `verify_application` 表（管理员审核用），同步更新 `user` 表状态。

**数据流**：
1. 用户提交 `POST /user/verify` → 同时 `INSERT INTO verify_application` + `UPDATE user SET verify_status=2`
2. 管理员查看 `GET /admin/verifies` → 查询 `verify_application` JOIN `user` + 补充 `user` 表中 `verify_status IN (1,2)` 但不在 `verify_application` 中的记录
3. 管理员审核 `POST /admin/verify/{vid}/approve` → `UPDATE verify_application SET status=1` + `UPDATE user SET verify_status=1`

**状态映射**：
| verify_application.status | user.verify_status | 含义 |
|--------------------------|-------------------|------|
| 0 | 2 | 待审核 |
| 1 | 1 | 已通过 |
| 2 | 3 | 已拒绝 |

**backfill 记录处理**（历史数据）：
### backfill 记录处理（历史数据）

- 对于只存在于 `user` 表但 `verify_application` 中无记录的用户（`verify_status=2` 待审核或 `verify_status=1` 已通过或 `verify_status=3` 已拒绝），管理端 API 通过补充查询展示
- backfill 记录的 `vid` 通过 Python 条件表达式设置：`'id': 0 if sc == 0 else -r['id']` —— **不要用 `sc == 0 and 0 or -r['id']`**，因为 Python 中 `0 or X` 返回 `X`（0为假），导致待审核记录的 id 被设为负数而非 0
- 审核 backfill 记录时（`vid=0`），前端必须额外发送 `{ user_id: xxx }` 请求体参数，后端据此直接更新 `user` 表（不涉及 `verify_application`）
  - 前端 approve：`const body = v.id === 0 ? { user_id: v.user_id } : {}`
  - 前端 reject：`const body = { reason: rejectReason.value }; if (rejectTarget.value.id === 0) body.user_id = rejectTarget.value.user_id`
```python
# 补充查询
SELECT id, nickname, phone, real_name, id_number, verify_status FROM user
WHERE verify_status IN (1,2) AND id NOT IN (SELECT user_id FROM verify_application)
```
- backfill 记录的 `vid` 设为 `0`（待审核）或 `-user_id`（已通过/已拒绝）\n  - **Python 条件表达式陷阱**：用 `0 if sc == 0 else -r['id']`，不要用 `sc == 0 and 0 or -r['id']`——Python 中 `0 or X` 返回 `X`（0 为假），待审核记录的 id 会变成负数而非 0\n- 审核 backfill 记录时（`vid=0`），从请求体获取 `{ user_id: xxx }`，直接更新 `user` 表（不涉及 `verify_application`）

### 🔴 `cur` 在 `with conn.cursor() as cur:` 块外使用 → "Cursor closed"

**症状**：后台操作（搭子审核、订单支付通知、OAuth回调等）报 `pymysql.err.ProgrammingError: Cursor closed` 或 `while self.nextset()` 错误，操作无响应。

**根因**：`with conn.cursor() as cur:` 块结束后，`cur` 被自动关闭。但代码在块结束后继续使用 `cur.execute()` 查询数据。

**变体：OAuth 回调中 cur 在 with 块外使用**

```python
# ❌ 错误：phone_bound 查询在 with 块外
conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("INSERT ...")
        conn.commit()
    # 这里 cur 已关闭
    cur.execute("SELECT phone_bound FROM user WHERE id=%s", (user_id,))  # 报错！
finally:
    conn.close()

# ✅ 正确：所有 cur 操作都在 with 块内
conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("INSERT ...")
        cur.execute("SELECT phone_bound FROM user WHERE id=%s", (user_id,))
        u = cur.fetchone()
        conn.commit()
    # 块外使用变量而非 cur
    if u and not u['phone_bound']:
        ...
finally:
    conn.close()
```

```python
def playmate_audit(cid):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE companion SET status=1 WHERE id=%s", (cid,))
            conn.commit()
        # ❌ 此处 cur 已关闭
        cur.execute("SELECT user_id FROM companion WHERE id=%s", (cid,))
        c = cur.fetchone()
    finally:
        conn.close()
```

**排查**：看错误日志中是否有 `Cursor closed`，然后检查对应函数的 `with conn.cursor()` 块结束位置。

**修复**：
1. 将块后需要 `cur` 的查询移到 `with` 块内部（在 `conn.commit()` 之前或之后均可）
2. 用变量保存查询结果（`companion_user = cur.fetchone()`），块外部引用变量而非 `cur`

```python
def playmate_audit(cid):
    conn = get_connection()
    companion_user = None  # 提前声明
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE companion SET status=1 WHERE id=%s", (cid,))
            # ✅ 在 with 块内查询
            cur.execute("SELECT user_id FROM companion WHERE id=%s", (cid,))
            companion_user = cur.fetchone()
            conn.commit()
        # ✅ 块外使用变量而非 cur
        if companion_user:
            send_notification(companion_user['user_id'], '...')
    finally:
        conn.close()
```

**预防**：`with conn.cursor() as cur:` 块外的所有 `cur.execute()` 都是潜在 Bug。写代码后 grep 检查：
```bash
# 检查 with 块结束后是否有 cur. 调用
# 观察缩进是否正确
```

### 🔴 订单支付通知必须同时通知用户和搭子

**症状**：用户支付后搭子收不到任何通知。

**根因**：`order.py` 的 `pay()` 函数只调用了 `send_notification(user_id, ...)`，未通知搭子。

**修复**：在 `with conn.cursor() as cur:` 块内（`conn.commit()` 之前）查询搭子的 `user_id`，然后在 commit 之后调用 `send_notification()`：

```python
# 在 with 块内、commit 之前
cur.execute("""
    SELECT c.user_id FROM `orders` o
    JOIN `companion` c ON c.id = o.companion_id
    WHERE o.id=%s
""", (order_id,))
companion = cur.fetchone()
companion_uid = companion['user_id'] if companion else None
conn.commit()

# 通知用户
send_notification(user_id, f'订单(#{...})支付成功', ...)
# 通知搭子
if companion_uid and companion_uid != user_id:
    send_notification(companion_uid, f'有客户下单(#{...})，请尽快处理', ...)
```

**注意**：`cur.execute()` 必须在 `with conn.cursor() as cur:` 块内使用，在 `conn.commit()` 之前或之后均可。移出 `with` 块后 `cur` 会关闭。

### 🔴 MySQL DECIMAL + Python float 类型不兼容（支付系统常见）

**症状**：支付确认/充值接口返回 500，日志报 `TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'`

**根因**：MySQL 的 DECIMAL 类型被 PyMySQL 返回为 Python `decimal.Decimal`，而 Python 的 `float` 不能与之直接运算。

**修复**：每次从数据库读取 DECIMAL 后立即转换为 `float()`：
```python
old_balance = float(m['balance'])
new_balance = old_balance + amount  # amount 已经是 float
```

**所有用到 DECIMAL 的字段都要这样处理**：`balance`、`amount`、`price` 等字段。涉及 `balance_before`、`balance_after` 流水记录也同样需要转换。

### 🔴 本机 iptables 默认只开放 22 和 5002（限 Server B）

**症状**：部署新服务（如支付微服务、Caddy）后外网无法访问，curl 超时。

**检查**：
```bash
sudo iptables -L INPUT -n
```

**修复**：放行所需端口：
```bash
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 5005 -j ACCEPT
```

**注意**：iptables 规则重启后丢失，需写入 iptables-persistent 或加入启动脚本。

### 收藏在线状态基于 `login_log`（动态判断）

**症状**：收藏页所有搭子都显示「在线」，因为 `companion.is_online` 字段默认值=1 且从未更新。

**修复**：在 `favorite/list` 查询中使用 LEFT JOIN `login_log` 判断最近5分钟是否有登录活动：

```python
SELECT f.id, f.created_at,
       c.id as companion_id, c.price_1h as price_per_hour, c.rank_title as title,
       u.nickname, u.avatar,
       CASE WHEN ll.last_active > NOW() - INTERVAL 5 MINUTE THEN 1 ELSE 0 END as online_status
FROM `favorite` f
JOIN `companion` c ON c.id = f.companion_id
JOIN `user` u ON u.id = c.user_id
LEFT JOIN (
    SELECT user_id, MAX(created_at) as last_active FROM login_log GROUP BY user_id
) ll ON ll.user_id = c.user_id
WHERE f.user_id=%s
```

**注意**：前端使用 `item.online_status`，不要用 `item.is_online`。查询字段名必须一致。

## 私聊系统（Private Chat）

全平台私聊互通 — 需求大厅/订单/搭子端均可发起。

### 数据库
```sql
CREATE TABLE chat_message (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  from_id INT NOT NULL,
  to_id INT NOT NULL,
  content TEXT NOT NULL,
  is_read TINYINT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_from_to (from_id, to_id),
  KEY idx_to_read (to_id, is_read)
);
```

### API 端点
| 端点 | 方法 | 功能 |
|------|------|------|
| /api/chat/send | POST | 发送私聊消息（from_id→to_id） |
| /api/chat/messages | GET | 获取与某用户的聊天记录（分页） |
| /api/chat/conversations | GET | 会话列表（含对方昵称/最后消息/未读数） |
| /api/chat/unread | GET | 私聊未读总数 |

### 前端文件
| 路由 | 组件 | 功能 |
|------|------|------|
| /chat | ChatConversation.vue | 私聊对话页（气泡 + 5s轮询） |
| /chat-list | ChatList.vue | 会话列表页，Profile入口「我的私聊」 |

### 入口路由跳转
/chat?user_id={对方ID}&name={对方昵称}

### 全平台私聊入口分布

| 页面 | 显示条件 | 聊天对象 | 跳转参数 |
|------|---------|---------|---------|
| 需求大厅 | status=1（已接单） | 需求发布者 | user_id=d.user_id |
| 我的需求 | status=1（已接单） | 接单搭子 | user_id=d.companion_id |
| 我的订单 | status=1/2（进行中/待确认） | 搭子 | user_id=order.companion_id |
| 搭子订单 | 进行中 | 下单用户 | user_id=order.user_id |
| 我的 → 我的私聊 | 始终可见 | 所有对话 | 点击会话项进入 |

### 聊天行模式（Order Card Chat Row）

在订单卡片底部，操作按钮之上，添加独立的一行私聊入口：

```html
<!-- 私聊入口 - 进行中/待确认订单可见 -->
<div class="chat-row" v-if="order.status === 1 || order.status === 2" @click="chatWithCompanion(order)">
  <span class="chat-icon">💬</span>
  <span class="chat-text">与搭子私聊</span>
  <span class="chat-arrow">›</span>
</div>
```

```css
.chat-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 0; margin: 0 0 6px;
  border-top: 1px solid #f0f0f0; cursor: pointer;
}
.chat-row:active { opacity: 0.6; }
.chat-icon { font-size: 16px; }
.chat-text { flex: 1; font-size: 13px; color: #667eea; font-weight: 500; }
.chat-arrow { font-size: 18px; color: #ccc; }
```

通用聊天跳转函数（**不要用 `encodeURIComponent`** — Vue Router 自动编码）：

私聊对话页自动 5s 轮询 /api/chat/messages 获取新消息。
onUnmounted 中必须 clearInterval(pollTimer)。
在对话页内发送新消息后，调用 await loadMsgs() 刷新。

📖 references/private-chat-system.md — 完整参考文档

### 路由路径不匹配（前端 /playmate → 后端 /companion）

**症状**：资料编辑页保存时提示「服务器内部错误」，但后端测试 curl 返回 200。

**根因**：前端 `api.put('/playmate/profile')` → 解析为 `/api/playmate/profile`，但后端蓝图前缀是 `companion_bp = Blueprint('companion', ..., url_prefix='/api/companion')`，路由 `@companion_bp.route('/profile')` 对应 `/api/companion/profile`。路径不匹配 → 404 → axios 误报500。

**全链路排查方法**：
```bash
# 1. 检查前端调用的路径
grep -n "api\.\(get\|post\|put\|delete\)" frontend/src/views/xxx.vue
# 2. 检查后端蓝图前缀
grep "url_prefix" backend/app/xxx.py
# 3. 检查后端路由
grep "@bp.route" backend/app/xxx.py
# 4. 组合得到完整路径: url_prefix + route
```

**预防**：所有新 API 端点先在 `curl` 验证后再写前端。前后端路径命名保持一致——如果后端用 `companion`，前端也用 `companion`。

### 搭子资料编辑（PUT /companion/profile）

`PlaymateProfile.vue` 调用 `api.put('/companion/profile', payload)`，后端 `update_profile()` 函数处理：

#### 字段映射
| 前端字段 | 后端 companion 表字段 | 映射 |
|---------|---------------------|------|
| `bio` | `intro` | 自动映射 |
| `max_hours` | `max_hours_per_day` | 自动映射 |
| `nickname` | user.nickname | 更新 user 表 |
| `avatar` | user.avatar | 更新 user 表 |
| `rank_title` | rank_title | 直接对应 |
| `tags` | tags | 数组→逗号分隔字符串 |
| `games` | companion_game 表 | 删除旧记录+批量插入 |

```python
# 映射实现
field_key = {'intro': 'bio', 'max_hours_per_day': 'max_hours'}.get(field, field)
val = data.get(field_key) or data.get(field)
if val is not None:
    updates.append(f"{field}=%s")
    params.append(val)
```

#### 多游戏更新
```python
if games:
    cur.execute("DELETE FROM companion_game WHERE companion_id=%s", (cid,))
    for g in games:
        cur.execute(
            "INSERT INTO companion_game (companion_id, game_id, price_1h, price_2h, price_night) VALUES (%s,%s,%s,%s,%s)",
            (cid, g['game_id'], g.get('price_1h',0), g.get('price_2h',0), g.get('price_night',0))
        )
    # 用第一个游戏更新 companion 主表
    first = games[0]
    cur.execute("UPDATE companion SET game_id=%s, price_1h=%s, price_2h=%s, price_night=%s WHERE id=%s",
        (first['game_id'], first.get('price_1h',0), first.get('price_2h',0), first.get('price_night',0), cid))
```

#### 常用模式
```python
# 先检查是否存在
cur.execute("SELECT id FROM companion WHERE user_id=%s", (user_id,))
row = cur.fetchone()
if not row:
    return fail('您还不是搭子')
cid = row['id']
```

### 搭子页面显示底部导航

在 App.vue 中：
```js
// ❌ 错误：/playmate/ 前缀下所有页面都隐藏底部导航
const noTabBarPages = ['/login', '/register', '/email-register', '/follow-register', '/playmate/']
// ✅ 正确：只隐藏 /playmate/login（独立登录页），其他搭子页面显示底部导航
const noTabBarPages = ['/login', '/register', '/email-register', '/follow-register', '/playmate/login']
```

### 实名认证模块（VerifyIdentity.vue）

详细文档见 `references/verify-identity-module.md`。

### 关键规范

1. **CSS 类名必须同步**：模板用的 `pd-*` 类必须在 scoped style 中有对应定义。模板与 CSS 类名不匹配 → 弹窗完全无样式。
2. **状态保护三重锁**：设置页（不可点击→Toast）→ 验证页 uploadId（不可上传→Toast）→ submitVerify（不可提交→Toast）
3. **审核中显示「提交成功，请等待审核」** 页面，非空表单
4. **上传文件 5MB 限制**：前端 `file.size > 5*1024*1024` → 返回；后端同样校验
5. **图片保存路径**：必须到 `/opt/ttdazi/backend/app/uploads/idcards/`（含 `app` 目录层级）

### 常见 Bug

- `/user/upload-id` 端点如果字段名不匹配（前端 `form.append('image', file)` vs 后端 `request.files['file']`）→ 永远返回「请选择图片」
- 上传后 file input 必须 `e.target.value = ''` 否则再次选择同一文件不触发 change 事件
- submit 成功后状态变为 `verify_status=2`（审核中），不是 1（已认证），Toast 应提示「提交成功，请等待审核」而非「认证成功」

## E2E Playwright 全页面截图测试

### 获取有效 token（绕过 captcha）

```python
# 用后端 create_token 生成有效 token
import sys; sys.path.insert(0, '/opt/ttdazi/backend')
sys.path.insert(0, '/home/ubuntu/.local/lib/python3.12/site-packages')
from app.utils import create_token
token = create_token(user_id, phone)
```

然后注入到 Playwright browser 的 localStorage 后 reload。

### 全页面截图脚本

```js
const { chromium } = require('/home/ubuntu/.npm/_npx/.../playwright');
const token = fs.readFileSync('/tmp/user_token.txt', 'utf-8').trim();
const page = await (await browser.newContext({viewport:{width:390,height:844}})).newPage();

await page.goto('http://host/#/');
await page.evaluate((t) => { localStorage.setItem('token', t); }, token);

const pages = ['/#/', '/#/list', '/#/orders', '/#/demand-hall', '/#/profile', ...];
for (const url of pages) {
  await page.goto(`http://host${url}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `/tmp/ft_${name}.png`, fullPage: true });
}
```

### 控制台错误检查

```js
const errors = [];
page.on('console', msg => {
  if (msg.type() === 'error') errors.push(`[${msg.type()}] ${msg.text()}`);
});
page.on('pageerror', err => errors.push(`[PAGE_ERROR] ${err.message}`));
// 遍历页面后输出 JSON.stringify(errors)
```

无害错误: `/favicon.ico` 404（SVG inline 替代）、`/api/message/count` 401（拦截器静默处理）

### 🔴 无效赋值表达式 `a || b = c`

**症状**：构建报错 `Invalid left-hand side in assignment expression`，指出某行有赋值表达式。

**根因**：`account.verifiedName || account.name = prof.account_name || ''` — JavaScript 不允许在布尔表达式左侧赋值。这是自动文本替换（`account.name =` 被错误替换为 `account.verifiedName || account.name =`）导致的结果。

**排查**：
```bash
# 搜索所有文件中的类似模式
grep -rn '||[^=]*=' frontend/src/ --include="*.vue" --include="*.js"
```

**修复**：确保赋值运算符 `=` 左边是一个单独的变量名，不是表达式：
```js
// ❌ 错误
account.verifiedName || account.name = 'value'

// ✅ 正确
account.name = account.verifiedName || 'value'
```

**预防**：批量替换时使用精准正则，替换后运行构建验证，不要仅靠文本匹配。

### 搭子通知全链路

搭子入驻和审核流程必须发送系统通知：

| 阶段 | 通知谁 | 内容 |
|------|--------|------|
| 📝 提交申请 | 用户 | 您的搭子入驻申请已提交，请等待管理员审核 |
| 📝 提交申请 | 管理员 | 有新的搭子入驻申请来自用户ID:xxx |
| ✅ 审核通过 | 用户 | 您的搭子入驻申请已通过，您现在可以开始接单了！ |
| ❌ 审核拒绝 | 用户 | 您的搭子入驻申请未通过，请完善资料后重新提交 |
| ✅ 提现通过 | 用户 | 您的提现¥XX申请已通过 |
| ❌ 提现拒绝 | 用户 | 您的提现¥XX申请未通过 |

通知使用 `send_notification()` 函数，`ntype='system'`。

### 管理员查询搭子审核用 `companion_id` 而非 `user_id`

管理端搭子审核路由定义：
```python
@admin_bp.route('/playmate/<int:cid>/audit', methods=['PUT', 'POST'])
def playmate_audit(cid):  # cid = companion.id，不是 user.id
```

前端调用时传 `companion.id`，非 `user.id`。

### 搭子审核通过后不可再申请

```python
# companion.py register()
cur.execute("SELECT id, status FROM companion WHERE user_id=%s", (user_id,))
existing = cur.fetchone()
if existing:
    if existing['status'] == 1:
        return fail('您已通过审核，无需重复申请')
```

前端 CompanionRegister.vue 的 `onMounted` 也检测：
```js
const prof = await api.get('/companion/my')
if (prof && prof.id && prof.status === 1) {
    safeToast('您已通过搭子审核，无需重复申请')
    router.replace('/')
}
```

### 🔴 Vue 3 Scoped CSS：兄弟根元素不继承 scoped 样式

**症状**：组件模板有多个根元素（fragment）时，非第一个根元素的 CSS 完全不生效——元素在 DOM 中存在但没有任何样式。

**根因**：Vue 3 的 `<style scoped>` 通过 `data-v-xxxxx` 属性选择器为编译后的元素添加样式。但该属性只添加到**模板根元素及其子元素**上。兄弟根元素（模板中的同级元素）无法获取 `data-v-xxxxx` 属性。

```html
<!-- ❌ 错误：.bar 匹配不到 scoped 样式 -->
<template>
  <div class="page">...</div>      <!-- 有 data-v-xxx ✓ -->
  <div class="bar">...</div>        <!-- 无 data-v-xxx ✗ -->
</template>

<!-- ✅ 正确：用一个根元素包裹全部 -->
<template>
  <div class="root">
    <div class="page">...</div>
    <div class="bar">...</div>      <!-- 有 data-v-xxx ✓ -->
  </div>
</template>
```

**排查**：浏览器开发者工具中检查元素是否带有 `data-v-xxxxx` 属性。没有 = scoped CSS 不生效。

**修复**：确保所有元素都在一个根元素内。需要固定定位（`position: fixed`）的底部栏也必须在根元素内部。

**备选方案**：使用非 scoped `<style>` 块（不带 `scoped` 属性）放置关键样式。非 scoped 样式不经转换，直接应用到所有匹配元素。但注意会全局污染。

### 🔴 底部固定栏与 App 底部导航冲突

**症状**：详情页等页面的 `position: fixed` 底部操作栏遮挡了 App.vue 的底部导航栏（64px 高），或反之。

**根因**：App.vue 的底部导航使用 `position: fixed; bottom: 0; height: 64px`。页面内的固定栏也使用 `bottom: 0`。两者重叠。

**修复**：页面底部栏使用 `bottom: 64px`（导航栏高度），使操作栏位于导航栏上方：

```css
.page-bottom-bar {
  position: fixed;
  bottom: 64px;           /* App 底部导航高度 */
  left: 0; right: 0;
  z-index: 99;
}
```

页面内容底部需增加 64px（导航）+ 52px（操作栏）= 116px 的 padding：

```html
<div style="height: 120px"></div>  <!-- 页面内容底部 -->
```

🔴 **不要通过隐藏 App 导航来解决**：将 `/detail` 加入 `noTabBarPages` 会导致导航闪烁、用户无法快速返回首页。

### 🔴 部署后旧构建残留文件导致浏览器加载旧版本

**症状**：修改后的代码已部署，浏览器仍显示旧版本（按钮不出现、样式不对）。浏览器强制刷新无效。

**根因**：Vite 每次构建生成带新 hash 的 JS/CSS 文件，但旧 hash 文件从未被清理。部署多次后，服务器上堆积了数十个旧版本的组件文件（如 35 个 `Detail-*.js` 文件）。浏览器可能从缓存中加载旧 hash 文件。

```bash
# 检查服务器上旧文件数量
ssh server "ls /path/to/assets/Detail-*.js | wc -l"
# 如果 > 1，就有旧文件残留
```

**排查**：对比本地构建的 hash 和服务器上的 hash：
```bash
# 本地 hash
ls dist/assets/Detail-*.js
# 服务器 hash
ssh server "ls /path/to/assets/Detail-*.js"
```

**修复**：
1. 清理服务器旧文件：`rsync --delete` 或在 deploy 脚本末尾加上清理命令
2. 或手动删除：`rm -f /path/to/assets/Detail-*.js`（保留最新）
3. 用户端清理微信缓存：`我 → 设置 → 通用 → 存储空间 → 缓存 → 清理`

**预防**：在 deploy.sh 中 `rsync -avz --delete` 使用 `--delete` 参数，确保服务器上只有最新文件。

### 🔴 后端重命名 `where` / `params` 时容易误删 `params = []`

**症状**：搭子列表页 / 推荐页报 500 错误，后端日志 `NameError: name 'params' is not defined`（行号指向 `params.extend([page_size, offset])` 或 `params.append(...)`）。

**根因**：修改 `companion_list()` 函数中的 `where` 逻辑时，`params = []` 被意外删除或移动到了 `params.append(game_id)` 之后。Python 不会提前声明变量——在 `params.append()` 之前必须有 `params = []`。

```python
# ❌ 错误：params 在 append 时未定义
where = ["c.status=1", ...]
if game_id > 0:
    where.append("c.game_id=%s")
    params.append(game_id)    # ← 这里报错！params 未初始化
params = []                   # ← 写在这里太晚了

# ✅ 正确
where = ["c.status=1", ...]
params = []                   # ← 必须在使用前初始化
if game_id > 0:
    where.append("c.game_id=%s")
    params.append(game_id)
```

**排查**：
```bash
# 检查 params 的定义位置
sed -n '36,70p' companion.py | grep -n 'params'
# 第一行应该看到 'params = []'，其后才是 params.append/params.extend
```

**预防**：修改 `companion.py` 的 `companion_list()` 函数后，立即用 curl 测试：
```bash
curl -s /api/companion/list?type=game | python3 -c "import sys,json;print(json.load(sys.stdin).get('code'))"
# 返回 0 正常，返回 -1 或报错就是 params 问题
```

### 🔴 推荐API（companion/recommend）缺少认证有效期过滤

**症状**：首页「推荐搭子」显示已过期的搭子（展示已到期但仍被推荐）。

**根因**：`companion.py` 的 `recommend()` SQL 查询只用 `WHERE c.status=1 AND c.is_online=1 AND u.status=1`，没有过滤 `expires_at_game` / `expires_at_travel`。而 `companion/list` 端点已有该过滤。

```python
# ❌ 缺少有效期过滤
WHERE c.status=1 AND c.is_online=1 AND u.status=1
ORDER BY c.is_online DESC, smart_score DESC

# ✅ 需要加上
WHERE c.status=1 AND c.is_online=1 AND u.status=1
  AND (c.expires_at_game > NOW() OR c.expires_at_travel > NOW())
ORDER BY c.is_online DESC, smart_score DESC
```

**排查**：对比 `companion/list` 和 `companion/recommend` 的 WHERE 条件是否一致。`companion/list` 已有 `(c.expires_at_game IS NOT NULL AND c.expires_at_game > NOW())` 等条件，但 `companion/recommend` 完全没有有效期过滤。

**修复**：在 recommend SQL 中添加 `AND (c.expires_at_game > NOW() OR c.expires_at_travel > NOW())`。

### 旅游搭子服务分类

```sql
INSERT INTO game (name, icon, sort_order, status) VALUES
('景点讲解','🏛️',10,1),
('行程规划','🗺️',11,1),
('美食向导','🍜',12,1),
('结伴徒步','🥾',13,1),
('旅拍','📷',14,1),
('自驾带路','🚗',15,1),
('景区协助','🎫',16,1);
```

**ID 分配**：ID 从 8 开始（前 7 个为游戏分类）。列表页筛选时按 `game_id` 区分。`game_id < 8` = 游戏, `game_id >= 8` = 旅游。

列表 API 支持 type 参数：后端 companion_list() 中 `service_type = request.args.get('type')`，`type=travel` 过滤 game_id>=8，`type=game` 过滤 game_id<8。

前端 List.vue 通过 `route.query.type` 控制，按 game.id>=8 过滤分类列表。

**合规要求**：服务名称硬编码在 game 表中，用户不可自定义。禁止出现伴游、陪同、陪逛、陪吃饭等关键词。详见 travel-companion-compliance 技能。

### 首页双入口卡片

在热门搭子上方并排显示游戏搭子和旅游搭子两张卡片。使用 .dual-cards { display:flex; gap:12px; } 布局，.entry-game (紫色渐变) 和 .entry-travel (绿色渐变) 各占 flex:1。

### 敏感词三级拦截

sensitive_words 表 word_type 字段：block(直接拦截), warn(弹窗警告), profile_block(主页拦截), travel(旅游违规词)。

### 聊天合规弹窗

CustomerService.vue 进入聊天时自动弹出合规提醒，3秒后可关闭。使用 setTimeout + showCompliance ref 控制。

### 旅游敏感词

新增 21 个旅游合规敏感词，`word_type='travel'`：

```
私人陪伴、贴身陪伴、独处、私下付费、场外价格、有偿约会、
私人伴游、深夜陪同、一对一同伴、不通过平台、陪聊、陪逛、
陪吃饭、深度陪伴、酒店陪、陪同过夜、请吃饭、出去吃饭、
晚上一起、单独相处、闺蜜式
```

这些词在聊天和用户资料中触发拦截，搭配 `chat_message` 监控系统使用。

## 资源链接
- 📖 `references/axios-api-path-duplication.md` — 前端 API 路径重复 /api/（baseURL 陷阱）
- 📖 `references/payment-microservice.md` — 独立支付微服务（pay.openai2000.cn + WeChat Pay 配置）
📖 `references/pc-native-pay.md` — PC 端扫码支付（Native 模式 + QR 轮询）
📖 `references/ip-blocking-ttdazi-config.md` — Server B IP 直连（ttdazi 配置）排查与修复
📖 `references/compliance-term-map.md` — 短期合规关键词替换映射
📖 `references/companion-home-cert-card.md` — 搭子首页展示状态卡实现
📖 `references/email-password-login.md` — 邮箱/手机号+密码登录实现
📖 `references/create-order-pricing.md` — 展示费用套餐（CreateOrder.vue 价格方案）
📖 `references/dual-certification.md` — 双重认证（expires_at_game + expires_at_travel）
📖 `references/city-picker-settings.md` — 城市选择器（替换 GPS/IP 定位）
📖 `references/geoip-china-fix.md` — ip-api.com 中国 IP 不准修复为 ipinfo.io
📖 `references/pc-payment-native-qr.md` — PC 端微信支付 Native 二维码实现（pay.html 双平台自动适配：WeChat浏览器→JSAPI，桌面→Native扫码+轮询）
📖 `references/pay-html-auto-detect.md` — pay.html 微信/桌面浏览器自动检测 + JSAPI/Native 降级逻辑
- 📖 `references/nginx-ssl-security.md` — Nginx SSL 多域名配置 + 安全头 + iptables 端口管理
- 📖 `references/disk-REDACTED-workflow.md` — 磁盘清理排查步骤（避免误删 pyenv/pnpm）
- 📖 `references/server-migration-checklist.md` — 迁移到新服务器检查清单
- 📖 `references/wechat-pay-setup.md` — 微信支付配置详情
- 📖 `references/wechat-pay-jsapi-weixinjsbridge.md` — WeChat Pay JSAPI + WeixinJSBridge 支付调起（推荐方案 vs wx.chooseWXPay）
📖 `references/recharge-cross-domain-payment.md` — 跨域充值支付流程 (dazi → pay 跳转 + order_no 从API响应提取 + 回调通知 + 双域名JS接口安全域名)
📖 `references/image-beacon-payment-callback.md` — Image Beacon 无跨域回调模式 + 服务器端支付确认查询
📖 `references/back-arrow-and-bug-patterns.md`
- 📖 `references/build-and-patch-issues.md` — 构建失败排查、patch转义Bug
- 📖 `references/private-chat-system.md` — 私聊系统数据库/API/前端
- 📖 `references/companion-seed-data-patterns.md` — 同城达人/游戏达人种子数据模式
- 📖 `references/e2e-testing-and-chat-system.md`
- 📖 `references/admin-audit-bug-patterns.md` — 管理端缺失导入/硬编码路径/实名审核不显示/safeToast→safeConfirm等
- 📖 `references/vue3-template-globals.md` — Vue 3 模板全局变量白名单
- 📖 `references/db-seed-data-pattern.md` — 种子数据注入模式（API关闭时DB直插+PyMySQL %转义陷阱）
- 📖 `references/province-city-picker.md` — 省市二级联动城市选择器（全国34省300+市）
- 📖 `references/admin-verify-dual-table.md` — 实名认证双表同步
- 📖 `references/funds-settlement-system.md` — 订单资金冻结3天结算系统
- 📖 `references/verify-reject-reason.md` — 拒绝原因保存、backfill vid=0 处理
- 📖 `references/withdrawal-fee-system.md` — 平台抽成/提现手续费完整体系
- 📖 `references/withdrawal-fee-system.md` — 平台抽成/提现手续费完整体系（site_config读取、净额显示、余额计算、前后端一致、常见bug）
- 📖 `references/wechat-oauth-integration.md` — 微信网页授权登录（OAuth + 手机号绑定 + 踩坑记录）
- 📖 `references/wechat-phone-quick-verify.md` — 微信手机号快速验证（JS-SDK + wxa/business/getuserphonenumber + 降级）
- 📖 `references/security-bug-patterns.md` — 安全 Bug 模式（聊天XSS/证书权限/SSL多域名冲突/iptables持久化）
- 📖 `references/captcha-debugging.md` — Captcha 自动化调试：从数据库查答案、绕过验证码生成 token
- 📖 `references/ip-blocking-ttdazi-config.md` — Server B IP 直连泄露（ttdazi 配置）排查与修复
- 📖 `references/wechat-pay-setup.md` — 微信支付配置（APIv3、证书、公钥模式）
- 📖 `references/recharge-wechat-pay-integration.md` — 充值中心对接微信支付 Native 二维码（轮询 + 回调通知 + 数据库）
- 📖 `references/companion-profile-reaudit.md` — 搭子资料编辑后触发重新审核（status=0 + CompanionRegister pending 检测）
- 📖 `references/server-b-baota-maintenance.md` — Server B 宝塔面板运维
- 📖 `references/session-2026-07-14.md` — Session: 1Panel Nginx persistence, WeChat OAuth wire-up, phone binding 3 ways, identity check before companion register
- 📖 `references/compliance-term-map.md` — 短期合规关键词替换映射（包夜→3小时+、游戏搭子→信息对接）
📖 `references/deploy-troubleshooting.md` — deploy.sh 超时排查、rsync --delete 残留文件清理
📖 `references/wxlogin-bug-chain-20260718.md` — WxLogin.vue 4个连锁Bug修复记录（refreshToken未定义/未生成refresh_token/未保存user数据/order.py status=0）
📖 `references/pay-html-jsapi-nesting-bug.md` — pay.html JSAPI 数据嵌套问题修复
📖 `references/pc-scan-login.md` — PC扫码登录实现文档（方案B：自建二维码登录系统）