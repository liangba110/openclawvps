---
name: ai-web-builder
description: 汇智云互联AI智能建站系统 — Flask+Vue3+Vite 双服务器架构。部署、开发、维护、扫码登录、AI建站引擎。
---

# AI智能建站系统（aiweb）

## 项目架构

```
用户浏览器 → https://aiweb.openai2000.cn
        │
Server B (Nginx 443) — 前端静态文件
  ├── /var/www/aiweb/frontend/dist/
  └── /api/* → Server A:5003 (直连，不再绕 Caddy)
                    │
              gunicorn (auto workers, venv路径) :5003
                  │
            MySQL: aiweb 库（7张表）
```

## 关键信息

| 项目 | 值 |
|:----|:----|
| 代码目录 | `/opt/aiweb/` |
| 后端端口 | 5003（gunicorn + systemd） |
| 数据库 | `aiweb`（MySQL，独立于 ttdazi） |
| 前端 | Vue3 + Vite，`/opt/aiweb/frontend/` |
| Nginx 配置 | Server B `/etc/nginx/sites-available/aiweb` |
| 模板配置 | `/opt/aiweb/server_b_nginx.conf` |
| 系统服务 | `aiweb.service` |
| 管理账号 | admin / admin（首次登录后修改密码） |
| 品牌名 | **汇智云**（原汇智云互联已弃用，详见下方 Logo 章节） |

## 用户风格偏好（铁律）

这个用户对汇智云AI建站系统有明确的风格偏好，**必须遵守**：

| 偏好 | 说明 |
|:----|:------|
| 🚫 **不要废话** | 直接给答案，不要展示中间调试步骤或分析过程。用户极度反感多步骤过程和冗长解释。 |
| ⚡ **批量操作** | 一次性执行多个工具调用，减少来回。用户会说"怎么这么卡"。 |
| 🎨 **视觉品质** | 极简AI科技感，蓝紫渐变(#2563EB→#7C3AED)，注重居中对齐和比例精确。不满意会直接说"不行"要求重做。 |
| ✅ **自测后交付** | 部署后必须 curl 验证（文件权限200、页面内容正常），确保端到端可用。**绝不能让用户看到 403 或页面打不开。** |
| 🔧 **一步到位** | 修复问题一次性彻底解决，不要修一半问"这样可以吗"。 |
| 🇨🇳 **中文回复** | 全部使用中文，使用 ✅/❌ 标记状态。 |

## Logo 正式版

6款 SVG 图标，蓝紫渐变云朵+AI纯图标（无底框），文件存 `/opt/aiweb/logo/`。

| # | 文件 | 尺寸 | 用途 |
|:-:|:----|:----:|:----|
| ① | `logo-horizontal.svg` | 200×52 | 横版主Logo（**白色/浅色导航栏用**） |
| ② | `logo-app.svg` | 200×200 | 方形App图标 |
| ③ | `logo-favicon.svg` | 64×64 | Favicon |
| ④ | `logo-dark.svg` | 200×52 | **深色版（黑色导航栏用）** — 白字+紫云朵 |
| ⑤ | `logo-badge.svg` | 80×80 | 徽章图标 |
| ⑧ | `logo-social.svg` | 1200×630 | 社交分享图 |

**黑色导航栏 (#0d0d0d) 必须使用 `logo-dark.svg`**（白字+紫云朵），不要用 CSS `filter: brightness(0) invert(1)` 反白！

下载包: `http://42.193.113.230/hui-zhi-cloud-logo.zip`

注意事项:
- **黑色导航栏 (#0d0d0d)** → 使用 `logo-dark.svg`（白字版），无需 CSS 反白
- **白色导航栏** → 使用 `logo-horizontal.svg`（深色字版）
- 替换 Logo: 复制到 `frontend/public/logo.svg` → `npm run build` → rsync → **chmod 644**（致命陷阱！否则 403）
- 部署后必须 curl 验证: `curl -sk -o /dev/null -w "%{http_code}" https://aiweb.openai2000.cn/logo.svg` → 期望 200

## UI 主题（蓝白太空星系风）

汇智云采用 **蓝白太空星系风** 视觉方案，详见 `references/space-theme-ui.md`。

关键设计要素：
- **黑色导航栏**（#0d0d0d）+ 蓝白渐变背景（#d0e2ff → #e8f0fe）
- 科技轨道环（3个旋转圆环+发光节点）
- SVG网络连接线（9条实线+脉冲节点+3个流动光点）
- 80个扩散粒子从中心burst扩散（±2000px范围）
- 3D卡片效果（hover旋转-3° + 图标浮起50px）
- 登录页卡片蓝色顶边3px、注册页青色顶边3px
- 导航栏 **所有按钮统一蓝渐变样式**（登录+注册都是渐变蓝）
- **页面层级区分**：特色区白底55%、行业区淡蓝底45%、流程区白底35%

### CSS 陷阱（致命）

详见 `references/css-pitfalls.md`。

**铁律:**
1. **`overflow: hidden` 在父元素上会杀死子元素的 `position: sticky`** — 这是最常见的滚动吸顶失效原因。`#app-root` 上绝不能用 `overflow: hidden`。
2. **输入框不能用 `transition: all`** — 后台轮询造成频繁 re-render 时，`transition: all` 会让输入框抖动。用 `transition: border-color 0.2s, box-shadow 0.2s` 替代。**`.card` 和 `.btn` 同样不能用 `transition: all`** — 目录改为只过渡 `border-color, box-shadow, transform`。
   - **此外,切换tab时必须清除定时器**（`clearInterval(timer); timer = null`），否则轮询在后台持续触发 Vue re-render。用 `switchToForm()` / `switchToScan()` 函数管理。
3. **动画元素加 `will-change: transform, opacity`** — 80+ 粒子动画 + SVG animate 会造成大量 repaint，用 will-change 开启 GPU 合成层。
4. **`router-link` 在 `page-header` 内需要 `position:relative; z-index:2`** — 因为 `.page-header::before` 伪元素（`position:absolute; inset:0`）会覆盖在 router-link 上方，阻止点击。如果不加 z-index，Logo 看上去存在但无法点击跳转首页。
5. **`isolation: isolate` 隔离背景动画对前景的影响** — 页面有大量 CSS 动画时，在 `.page` / `.home-page` 上加 `isolation: isolate` 可以防止背景合成层干扰前景元素的渲染性能。

## 部署命令

```bash
# 一键部署
bash /opt/aiweb/deploy.sh

# 或手动:
cd /opt/aiweb/frontend && npm run build
rsync -avz --delete /opt/aiweb/frontend/dist/ ubuntu@82.157.202.24:/var/www/aiweb/frontend/dist/
ssh ubuntu@82.157.202.24 "sudo chmod 644 /var/www/aiweb/frontend/dist/logo.svg /var/www/aiweb/frontend/dist/favicon.svg"

# 重启后端
sudo systemctl restart aiweb
```

## 部署验证（致命步骤）

部署后**必须验证文件可访问**，否则用户会非常不满:

```bash
# 1. Logo/Favicon 不可 403
curl -sk -o /dev/null -w "%{http_code}" https://aiweb.openai2000.cn/logo.svg   # → 期望 200
curl -sk -o /dev/null -w "%{http_code}" https://aiweb.openai2000.cn/favicon.svg # → 期望 200

# 2. 页面正常加载
curl -sk https://aiweb.openai2000.cn/ 2>/dev/null | head -c 100
```

**致命陷阱**: `cp`/`rsync` 后的 SVG 文件权限默认 600，Nginx 无法读取返回 403。每次部署后必须 `chmod 644` + curl 验证。

## 后端 API 蓝图

| 前缀 | 功能 |
|:----|:------|
| `/api/auth/` | 注册/登录/个人信息 |
| `/api/sites/` | 站点 CRUD |
| `/api/ai/` | AI建站引擎（generate / conversations） |
| `/api/publish/` | 预览 / 发布 / deploy |
| `/api/admin/` | 管理后台（用户/站点/模板/统计） |
| `/api/login/scan/` | 扫码登录（create / status / confirm） |
| `/api/register/scan/` | **扫码注册**（create / status / confirm） |

## 扫码登录

- 数据库表: `scan_login`（code / status / user_id / token / expires_at）
- PC端: 调用 `POST /api/login/scan/create` → 生成二维码 → 每1.5s轮询 `GET /api/login/scan/status`
- 手机端: 扫码打开 `/#/scan-confirm?code=XXX` → 调用 `POST /api/login/scan/confirm`
- 二维码有效期: 300秒（5分钟）
- npm 依赖: `qrcode` 包（非 qrcodejs2）
- **🔥 竞态条件**: `confirm` 端点必须**一步到位**设置 status=2 + token，不要先设 status=1 再提交再设 status=2。中间提交导致 PC 轮询到 status=1（无token）的不完整状态。

## 扫码注册（三阶段模式 - 手机授权 + PC绑定）

复用 `scan_login` 表，二维码有效期 600秒（10分钟）。完整流程详见 `references/scan-qr-register-pattern.md`。

**流程**: PC生成二维码 → 手机扫码（显示头像/昵称 + 需用户点击"确认授权"）→ PC检测到扫码 → 显示绑定表单（昵称+手机+密码）→ 用户填写 → 完成注册（PC自动登录）

| 步骤 | 操作 | API |
|:----:|:-----|:----|
| ① | PC创建二维码 | `POST /api/register/scan/create` |
| ② | 手机扫码，打开授权页（显示微信头像+昵称），用户点击"确认授权" | `POST /api/register/scan/authorize`（传code+nickname） |
| ③ | PC轮询到 status=1，**立即停止轮询**，显示绑定表单 | `GET /api/register/scan/status` |
| ④ | 用户填手机号+密码，点完成注册 | `POST /api/register/scan/bind`（创建用户，返回token） |
| ⑤ | PC自动登录跳转 /dashboard | localStorage.setItem('token') |

**关键**: PC端切换到"手机注册"Tab时，**必须清除轮询定时器**（`clearInterval(timer); timer = null`）。否则后台轮询持续触发 Vue re-render，导致输入框抖动。详见 `references/css-pitfalls.md` 第2条、第6条。

**数据库**: `scan_login` 表需 `extra VARCHAR(500)` 字段存昵称 JSON。

**手机端**: `ScanRegister.vue` — 显示昵称+头像，用户点击确认后才调用 authorize API。

**PC端**: `Register.vue` 扫码Tab — 轮询检测到 status=1 后停止轮询，显示绑定表单。使用 `switchToForm()` 和 `switchToScan()` 函数管理 tab 切换（切换时自动清理/重启定时器）。

## AI 建站引擎（v2 重写版）

### 架构

生产模式（配置 AI_API_KEY）-> 调用 DeepSeek API。无 Key 时走智能模板引擎。

### 智能模板输出（无 API Key 时）

| 字段 | 说明 |
|:----|:------|
| pages | 4~7页（随机：首页/关于/服务/案例/商城/新闻/联系），每页 2~5 个组件 |
| theme | 14个行业自动配色（9套主色+辅色） |
| admin_panel | 5个管理模块（仪表盘/内容/服务/客户/设置） |

**随机化策略**: 标语、功能点、组件组合、按钮文案均用 `pick()` + `random.shuffle()` 确保每次生成不同。详见 `references/ai-build-engine-v2.md`。

**30个行业**: 含传统行业（制造/农业/物流/建筑/汽车/家政/婚庆/印刷/环保/珠宝/家具/玩具/食品/酒业/保险/传媒），各有独立配色、slogan、模板风格（warm/cute/clean/elegant/bold/trust/shop/minimal/tech/nature/premium/formal等）。

**组件随机化**: 首页组件在 hero 和 cta 之间的中部组件随机打乱；案例区/评价区/数据区各 50%~70% 概率出现，每次生成结果不同。

### 组件类型（13种）

| 组件 | 渲染函数 | 说明 |
|:----|:---------|:------|
| hero | render_hero | 渐变背景 + 大标题 + CTA按钮 + 可选统计数字 |
| features | render_features | 3列卡片网格（图标+标题+描述） |
| showcase | render_showcase | 3列图片卡片（图片+标签+描述） |
| testimonials | render_testimonials | 3列评价卡片（星级评分+引用+作者） |
| cta | render_cta | 全宽行动号召（渐变背景+按钮） |
| page_header | render_page_header | 页面标题横幅（纯色背景） |
| about | render_about | 公司介绍 + 统计数字网格 |
| team | render_team | 4列团队头像卡片 |
| services | render_services | 3列服务卡片（功能列表+价格） |
| pricing | render_pricing | 3列价格方案（含"推荐"标签） |
| blog | render_blog | 3列文章卡片（日期+标题+摘要） |
| contact / contact_info | render_contact | 3列联系信息（电话/地址/邮箱） |
| footer | render_footer | 深色页脚 |

### 生成与精化流程

| 操作 | action 参数 | 说明 |
|:----|:-----------|:------|
| 创建新站 | `create`（默认） | 根据 prompt 生成完整 5页+后台 |
| 优化已有 | `refine` | 传入 current_result + 反馈文字，调整主题色/名称等 |

### HTML 渲染引擎（publish.py）

- 内联 CSS 框架（grid-3 / grid-4 响应式网格）
- 组件渲染函数在 `COMPONENT_RENDERERS` 字典中注册
- CSS 使用 `{ff}`（字体）和 `{p}`（主色）模板变量
- 输出完整 HTML：导航栏 -> 各页面内容 -> 页脚
- 导航链接使用页面 slug 作为锚点（`<a href="#about">`），**页面第一个 `<section>` 必须加 `id` 属性**，否则点击导航无反应
- CSS 中需加 `scroll-margin-top` 补偿固定导航栏：`section { scroll-margin-top: 70px; }`
- 响应式断点：768px
- **导航锚点**：每个页面的第一个 `<section>` 必须添加 `id="{slug}"`，导航栏 `<a href="#{slug}">` 才能正确跳转。CSS 需添加 `section { scroll-margin-top: 70px; }` 补偿固定导航栏遮挡。
- **渲染函数注册**：所有组件渲染函数必须在 `COMPONENT_RENDERERS` 字典中注册。`.format()` 调用必须包含所有模板变量（特别是 `btn`），否则 KeyError。

### 🔥 常见失败原因

1. **`conversations` API 缺少 `response` 字段** -> 预览页拿不到生成内容 -> 显示"暂无预览"
2. **`publish/preview` 截断 HTML** -> 返回 `html[:500] + '...'` -> 预览内容不完整。必须返回完整 HTML。
3. **对话记录未保存** -> 检查 `generate` 端点是否收到 `site_id`（不为 None 时才会 INSERT）
4. **f-string 反斜杠** -> Python f-string 中不能出现 `\`，用模板字符串或 `chr()` 替代
5. **render_hero 缺少 btn 参数** -> `.format()` 调用必须包含 `btn=btn`，否则 KeyError
6. **`before_request` 中访问 `request.json`** -> 会消费请求体，后续 `request.get_json()` 返回空。`before_request` 只处理安全头，不碰请求体。XSS 过滤在路由内按需调用。

### 完整 AI 建站参考

详见 `references/ai-build-engine-v2.md`（含完整组件渲染代码、CSS 框架、生成流程）。

## 安全组 / 防火墙

- Server A iptables 默认 DROP，需放行端口:
  ```bash
  sudo iptables -I INPUT -p tcp -s 82.157.202.24 --dport 5003 -j ACCEPT
  ```
- 腾讯云安全组也需放行 5003（如适用）

## 备份

- 独立备份脚本: `/opt/aiweb/daily_backup.sh`
- 每天 3:30 执行（错开 ttdazi 的 2:00）
- 保留 90 天，自动清理
- 存到 Server A 数据盘 `/root/data/disk/aiweb/`

## SEO 优化

- 品牌: **汇智云** — 零代码AI智能建站_商城/官网/小程序云端搭建服务商
- 网站标题: `汇智云AI建站 — 零代码生成官网/商城/小程序 | AI智能建站平台`
- 描述: 汇智云互联AI建站，零代码智能生成企业官网、商城网站、小程序
- 关键词: 汇智云互联,AI建站,智能建站,免费建站,商城网站建设,小程序开发,零代码建站
- 修改文件: `index.html`（title / description / keywords / og / JSON-LD）
- 页面内容: `Home.vue`（FAQs / 流程步骤 / 行业关键词矩阵）
- robots.txt + sitemap.xml 放在 `frontend/public/` 目录
- Nginx 需确保 dist 目录文件权限为 644（否则 403 Forbidden）
- 浏览器验证: open graph / canonical / 结构化数据一并配置

## 参考文档

- `references/space-theme-ui.md` — 蓝白太空星系风UI实现细节（3D卡片、粒子扩散、轨道环、页面配色）
- `references/scan-qr-register-pattern.md` — 扫码注册实现（自动注册、生成账号、PC端自动登录）
- `references/daily-backup-pattern.md` — 每日备份脚本
- `references/css-pitfalls.md` — CSS 陷阱集
- `references/security-hardening.md` — 安全加固完整配置（连接池、bcrypt、速率限制、安全头）

## 安全加固

完整的配置和代码变更记录在 `references/security-hardening.md`。

核心变更：DBUtils 连接池、bcrypt 密码哈希、Nginx 速率限制（API 30r/s）、6 项安全头、gunicorn 自动 worker 数。

### 铁律：before_request 中间件陷阱（★★★）

**症状:** 所有 POST 接口（注册、登录、生成、创建站点）在浏览器中无响应，但 curl 直接测试正常。

**根因:** 在 `@app.before_request` 中访问 `request.json` 会消费请求体，导致后续 `request.get_json()` 返回空。

**规则:** `before_request` 只处理安全头，不碰请求体。XSS 过滤在路由内按需调用。