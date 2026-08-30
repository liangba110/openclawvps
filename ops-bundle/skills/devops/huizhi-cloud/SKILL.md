---
name: huizhi-cloud
description: 汇智云AI智能建站系统项目技能。Vue3+Flask+MySQL双服务器架构，AI建站引擎，扫码登录，腾讯云风格UI。触发词：汇智云、aiweb、AI建站、智能建站、huizhi-cloud。
---

# 汇智云AI智能建站系统

## 项目架构

```
用户浏览器 → https://aiweb.openai2000.cn
                  │
          Server B (82.157.202.24 — Nginx 443)
           ├── 前端静态文件 /var/www/aiweb/frontend/dist/
           └── /api/* → Server A :5003 (gunicorn)
                              │
                      Server A (42.193.113.230)
                       ├── gunicorn :5003 (systemd aiweb.service)
                       ├── MySQL aiweb 库（7张表）
                       └── venv /opt/aiweb/venv/
```

- 前端: `/opt/aiweb/frontend` (Vue3 + Vite + vue-router 4)
- 后端: `/opt/aiweb/backend` (Flask + PyMySQL + gunicorn)
- 部署: `bash /opt/aiweb/deploy.sh`（构建→同步Server B→重启后端）
- 服务: `sudo systemctl restart aiweb`

## 域名与SSL

| 域名 | 用途 | SSL |
|:----|:-----|:---:|
| `aiweb.openai2000.cn` | 主站 | Let's Encrypt（自动续期） |

## 核心功能

### 用户系统
- 手机号注册/登录 + JWT认证
- **扫码登录**（移植自ttdazi项目）
  - `POST /api/login/scan/create` — 创建二维码
  - `GET /api/login/scan/status` — 轮询状态
  - `POST /api/login/scan/confirm` — 手机确认
  - 前端: `Login.vue` + `ScanConfirm.vue`
- **扫码注册**（两步流程：手机授权 → PC绑定）
  - `POST /api/register/scan/create` — 创建二维码
  - `GET /api/register/scan/status` — 轮询（status=1时返回nickname）
  - `POST /api/register/scan/authorize` — 手机授权，传递昵称
  - `POST /api/register/scan/bind` — PC绑定手机号+密码完成注册
  - 前端: `Register.vue` + `ScanRegister.vue`
  - 流程: PC显示二维码 → 手机扫码授权 → PC检测到status=1显示绑定表单 → 用户填手机密码 → 调用bind → 自动登录

### AI建站引擎
- `POST /api/ai/generate` — 输入需求，AI生成网站结构JSON
- 无API Key时自动降级到模拟模式（mock_generate）
- 组件库: hero/about/services/gallery/contact/footer/features/cta/team/testimonials/pricing
- 渲染: 后端generate_site_html() 生成完整HTML，前端iframe预览

### 发布系统
- `POST /api/publish/deploy` — 一键发布到子域名
- 生成静态HTML，保存到 `/opt/aiweb/published/<subdomain>/`
- 预览: `POST /api/publish/preview`

### 管理后台
- 路由: `/#/admin/`
- 功能: 用户管理 / 站点管理 / 模板管理（未实现）

## 数据库（aiweb库）

| 表 | 说明 |
|:---|:------|
| `users` | 用户（含admin角色） |
| `sites` | 站点（子域名/状态/主题） |
| `pages` | 页面（slug/排序/是否首页） |
| `components` | 组件（type/props JSON/排序） |
| `templates` | 行业模板 |
| `ai_conversations` | AI对话记录 |
| `deployments` | 发布记录 |
| `scan_login` | 扫码登录/注册会话（extra字段存昵称等JSON） |

## 关键接口

| 前端调用 | 后端路由 | 方法 |
|----------|----------|:----:|
| `/auth/register` | `auth_bp /register` | POST |
| `/auth/login` | `auth_bp /login` | POST |
| `/auth/profile` | `auth_bp /profile` | GET |
| `/sites/list` | `sites_bp /list` | GET |
| `/sites/create` | `sites_bp /create` | POST |
| `/sites/detail` | `sites_bp /detail` | GET |
| `/ai/generate` | `ai_bp /generate` | POST |
| `/login/scan/create` | `scan_bp /scan/create` | POST |
| `/login/scan/status` | `scan_bp /scan/status` | GET |
| `/login/scan/confirm` | `scan_bp /scan/confirm` | POST |
| `/register/scan/create` | `scan_reg_bp /scan/create` | POST |
| `/register/scan/status` | `scan_reg_bp /scan/status` | GET |
| `/register/scan/authorize` | `scan_reg_bp /scan/authorize` | POST |
| `/register/scan/bind` | `scan_reg_bp /scan/bind` | POST |
| `/publish/preview` | `publish_bp /preview` | POST |
| `/publish/deploy` | `publish_bp /deploy` | POST |
| `/admin/users` | `admin_bp /users` | GET |
| `/admin/stats` | `admin_bp /stats` | GET |

## Logo 品牌规范

汇智云正式Logo: 蓝紫渐变云朵+AI纯图标，无底框。

**6款Logo：**

| # | 文件 | 尺寸 | 用途 |
|:-:|:----|:----:|:----|
| ① | `logo-horizontal.svg` | 200×52 | 横版主Logo（导航栏） |
| ② | `logo-app.svg` | 200×200 | 方形App图标 |
| ③ | `logo-favicon.svg` | 64×64 | Favicon |
| ④ | `logo-dark.svg` | 200×52 | 深色版 |
| ⑤ | `logo-badge.svg` | 80×80 | 徽章图标 |
| ⑥ | `logo-social.svg` | 1200×630 | 社交分享图 |

**配色：**
- 主色: #0052D9（腾讯云蓝）
- 辅色: #3B82F6 / #06B6D4 / #7C3AED
- 图标渐变: #2563EB → #7C3AED

**源文件位置：** `/opt/aiweb/logo/`
**下载包：** http://42.193.113.230/hui-zhi-cloud-logo.zip

## UI 主题规范

当前使用**深空蓝白科技主题**：
- 导航: 黑色(#0d0d0d) + 白色logo（使用logo-dark.svg或CSS filter亮度反转）
- 背景: 蓝白渐变 + 动态网格 + 80个扩散粒子 + 科技轨道环
- 繁星: 15颗闪烁星点，透明度0.45~0.7
- 连接线: SVG实线网络，节点脉冲动画，数据流动光点
- 卡片: 白色半透明玻璃 + 3D旋转变换(rotateX/translateZ) + 多层阴影
- 按钮: 蓝渐变(#0052D9→#2563EB) + hover光晕阴影
- 文字: 深色文本用var(--text)，浅色背景上用CSS变量体系

### 3D卡片效果（全局style.css）

```css
.card {
  transform-style: preserve-3d;
  transform: perspective(1000px);
  transition: all 0.5s cubic-bezier(...);
}
.card:hover {
  transform: perspective(1000px) rotateX(-3deg) rotateY(1deg) translateY(-6px) scale(1.02);
}
.card .f-icon { transform: translateZ(25px); }
.card:hover .f-icon { transform: translateZ(50px) scale(1.15); }
.card h3 { transform: translateZ(15px); }
.card:hover h3 { transform: translateZ(30px); }
.card p { transform: translateZ(5px); }
.card:hover p { transform: translateZ(15px); }
```

## 前端路由

| 路径 | 视图 | 说明 |
|:-----|:-----|:------|
| `/` | Home | 首页 |
| `/login` | Login | 登录（扫码+密码Tab） |
| `/register` | Register | 注册 |
| `/dashboard` | Dashboard | 我的站点 |
| `/builder/:id` | Builder | AI建站对话+预览 |
| `/preview/:id` | Preview | 站点预览 |
| `/publish/:id` | Publish | 发布配置 |
| `/scan-confirm` | ScanConfirm | 扫码确认页 |
| `/scan-register` | ScanRegister | 扫码注册确认页 |
| `/admin` | admin/Layout | 管理后台 |

## SEO 配置

- 标题: `汇智云AI建站 — 零代码生成官网/商城/小程序 | AI智能建站平台`
- 关键词: 汇智云,AI建站,智能建站,免费建站,企业网站制作,商城网站建设,小程序开发
- robots.txt: ✔
- sitemap.xml: ✔
- 结构化数据 (JSON-LD): ✔ SoftwareApplication
- Open Graph: ✔ 微信/社交分享
- Canonical: ✔
- 备注: 百度站长验证码待替换

## 备份配置

- 位置: Server A 数据盘 `/root/data/disk/aiweb/`
- 频率: 每日凌晨 3:30（cron）
- 保留: **90天**，超过自动删除
- 脚本: `/opt/aiweb/daily_backup.sh`
- 内容: aiweb数据库 + 项目源码 + 前端dist + 用户数据

## 部署流程

```bash
# 一键部署
bash /opt/aiweb/deploy.sh

# 或手动分步
cd /opt/aiweb/frontend && npm run build
rsync -avz --delete /opt/aiweb/frontend/dist/ ubuntu@82.157.202.24:/var/www/aiweb/frontend/dist/
ssh ubuntu@82.157.202.24 "sudo chmod 644 /var/www/aiweb/frontend/dist/logo.svg /var/www/aiweb/frontend/dist/favicon.svg"
sudo systemctl restart aiweb
```

## 注意事项

### 文件权限（★★★ 常见低级错误）
- `cp` 复制的SVG/新文件默认权限可能为600，Nginx无法读取
- 部署后必须执行 `chmod 644 <file>` 或 `sudo chmod 644`
- 建议在deploy.sh中加入权限修复步骤
- **部署后必须curl验证**：`curl -sk -o /dev/null -w "%{http_code}" https://aiweb.openai2000.cn/logo.svg` — 返回200才算成功
- 用户极度反感此类低级错误，交付前必须端到端验证文件可访问

### CSS 陷阱
- `overflow: hidden` 在父元素上会破坏 `position: sticky` — 导致导航栏不固定
- Vue组件中 `.nav` 同时用 `position: sticky` 和 `transform: translateZ()` 时，sticky优先，3D效果不生效
- CSS custom properties 在 `@keyframes` 中使用时，必须在每个关键帧都写全 `transform` 属性（不能省略translate只写scale）
- 闪烁粒子用 `calc(var(--x) * 0.2)` 实现分阶段移动，避免直接跳到终点
- **输入框抖动（★★ 常见）**：`.input { transition: all 0.3s }` 是元凶。当页面因轮询/动画重渲染时，`transition: all` 会动画所有属性变化，导致输入框抖动。**修复：** 改为只过渡需要变化的属性
  ```css
  /* ❌ 错误：导致输入框抖动 */
  transition: all 0.3s;
  /* ✅ 正确：只过渡实际变化的属性 */
  transition: border-color 0.2s, box-shadow 0.2s;
  ```
- **同样问题存在于** `.card { transition: all ... }` 和 `.btn { transition: all ... }` — 都应改为只过渡 `border-color, box-shadow, transform`
- **按钮背景动画**：`transition: all` 会让按钮hover时所有属性变化产生动画，改为具体属性可减少重绘
- 页面背景动画（80个粒子 + 轨道环 + SVG动画）会持续消耗GPU。在表单页面可通过 `isolation: isolate` 隔离影响

### JS/前端陷阱
- `catch {}`（无参数）语法在某些Vite/esbuild配置下可能不兼容，导致 `finally` 块不执行。**修复：** 始终使用 `catch(e) { ... }` 显式写法
- **轮询定时器必须严格管理**：切换Tab时用 `switchToForm/switchToScan` 函数而非直接改 `mode`，确保 `clearInterval(timer)` 被调用。后台定时器每1.5秒触发API请求→状态更新→Vue重渲染→页面抖动
- `showToast()` 创建临时DOM元素可能不显示，导致用户以为按钮没反应。**修复：** 关键操作（注册/登录失败）用 `alert()` 或明确的UI反馈
- **所有页面Logo必须用 `<router-link to="/">` 包裹**，且需加 `position:relative; z-index:2` 避免被 `page-header::before` 伪元素（inset:0 + position:absolute）遮住点击事件

### 文件权限（★★★ 常见低级错误）
- Server A 的 iptables 默认策略为 DROP
- 新开端口必须在 iptables 中添加 ACCEPT 规则
- 同时需要在腾讯云控制台安全组中放行端口

### 端口分配
| 端口 | 服务 | 项目 |
|:----:|:-----|:----:|
| 5002 | gunicorn | 同途搭子 |
| 5003 | gunicorn | 汇智云AI建站 |
| 5005 | gunicorn | 支付服务 |
| 8080 | http.server | 临时文件服务 |

### before_request 中间件陷阱（★★★ 非常隐蔽的错误）

**症状：** 所有 POST 接口（注册、登录、生成、创建站点）在浏览器中无响应，但 curl 直接测试正常。点击"生成"按钮毫无反应，按钮保持在"⏳ 生成中..."状态不消失。同时页面上的"返回"按钮也失效。

**根因：** 在 `@app.before_request` 中访问 `request.json` 会**消费请求体**，导致后续路由中 `request.get_json()` 返回空或抛出异常。Flask 的 `request.json` 和 `request.get_json()` 共享同一个流解析器——第一次调用即锁定。请使用 `before_request` 仅处理安全头，不碰请求体。

**错误写法（不要这样做）：**
```python
@app.before_request
def before_request():
    if request.json:  # ← 这行消费了请求体！
        request.json_data = sanitize_dict(request.json)
```

**正确做法：**
```python
@app.before_request
def before_request():
    # 仅处理安全头，不碰请求体
    pass
```

如果需要 XSS 过滤，请在路由处理函数中按需调用 `sanitize_dict(request.get_json() or {})`，不在中间件中处理。

### 安全头补丁（上线前必须检查）

详细安全配置见 `references/security-checklist.md`

### 安全头（Nginx）
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```
**注意:** `limit_req_zone` 必须在 `http {}` 块中定义（nginx.conf），不能在 `server {}` 中。

### 速率限制（Nginx）
```nginx
# 在 nginx.conf 的 http {} 块中
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_req_status 429;

# 在 server {} 的 location 中引用
location /api/ {
    limit_req zone=api burst=50 nodelay;
}
```

### 后端安全加固

| 项目 | 做法 | 文件 |
|:----|:-----|:-----|
| **数据库连接池** | DBUtils PooledDB，mincached=2, maxcached=10, maxconnections=20 | `backend/db.py` |
| **密码哈希** | bcrypt（兼容旧SHA256）| `backend/utils.py` |
| **XSS过滤** | 路由内按需调用 sanitize_dict(request.get_json() or {})，**不在 before_request 中处理** | `backend/main.py` |
| **输入类型强转** | 所有API用 `str(data.get('key', ''))` 而非 `data.get('key')` | 各蓝图 |
| **速率限制** | 注册接口5次/分钟/IP（Flask端） | `backend/main.py` `rate_limit()` |
| **gunicorn** | workers = cpu_count*2+1, max_requests=1000 | `backend/gunicorn.conf.py` |

**XSS过滤实现（不要在before_request中处理，见上方陷阱说明）：**
```python
# main.py 中定义过滤函数
_XSS_PATTERN = re.compile(r'<[^>]*script[^>]*>|<[^>]*on\w+\s*=|javascript\s*:|<iframe|<embed|<object', re.I)

def sanitize_dict(d):
    if isinstance(d, dict):
        return {k: sanitize_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [sanitize_dict(i) for i in d]
    if isinstance(d, str):
        return _XSS_PATTERN.sub('', d)
    return d

# 在路由中调用（每个接收用户输入的蓝图）：
data = sanitize_dict(request.get_json() or {})
```

**密码升级（bcrypt + SHA256兼容）：**
```python
def make_password(password):
    import bcrypt as _bcrypt
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def check_password(password, hashed):
    import bcrypt as _bcrypt
    try:
        return _bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        # 兼容旧版SHA256哈希
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest() == hashed
```
