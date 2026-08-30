---
name: ttdazi
description: 同途搭子游戏陪玩平台项目技能。Flask+Vue3+Vant+MySQL双服务器架构。触发词：同途搭子、陪玩、ttdazi、汇智云。
---

# 同途搭子 项目开发规范

## 项目架构

```
Server A (42.193.113.230) — Flask 后端 + MySQL
Server B (82.157.202.24)   — Nginx 反向代理 + 前端静态文件
```

- 前端: `/opt/ttdazi/frontend` (Vue3 + Vant4 + Vite)
- 后端: `/opt/ttdazi/backend` (Flask + PyMySQL + gunicorn)
- 部署: `bash /opt/ttdazi/deploy.sh`
- 服务重启: `ssh ubuntu@42.193.113.230 "sudo systemctl restart ttdazi"`
- Git: `/opt/ttdazi` (master)

## 关键接口

> 📋 上线运营参考（含服务器/Cron/凭证/紧急排错）：`references/launch-2026-07-06.md`

| 前端调用 | 后端路由 | 方法 |
|----------|----------|------|
| `/user/login` | `user_bp /login` | POST |
| `/user/register` | `user_bp /register` | POST |
| `/user/profile` | `user_bp /profile` | GET |
| `/user/update` | `user_bp /update` | **PUT** |
| `/user/avatar/upload` | `user_bp /avatar/upload` | POST (multipart) |
| `/message/list` | `msg_bp /list` | GET |
| `/message/count` | `msg_bp /count` | GET |
| `/message/read-all` | `msg_bp /read-all` | POST |
| `/message/delete` | `msg_bp /delete` | POST |
| `/order/list` | `order_bp /list` | GET |
| `/order/create` | `order_bp /create` | POST |
| `/order/pay` | `order_bp /pay` | POST |
| `/order/confirm` | `order_bp /confirm` | POST |
| `/order/complete` | `order_bp /complete` | POST |
| `/companion/register` | `companion_bp /register` | POST |
| `/companion/list` | `companion_bp /list` | GET |
| `/companion/detail` | `companion_bp /detail` | GET |
| `/companion/photos/upload` | `companion_bp /photos/upload` | POST (multipart) |
| `/admin/playmates` | `admin_bp /playmates` | GET |
| `/admin/playmate/<id>/audit` | `admin_bp /playmate/<id>/audit` | PUT+POST |
| `/admin/playmate/<id>/toggle` | `admin_bp /playmate/<id>/toggle` | **PUT** |
| `/security/devices` | `security_bp /devices` | GET |
| `/security/device/revoke` | `security_bp /device/revoke` | POST |
| `/security/change-password` | `security_bp /change-password` | POST |
| `/review/v2/verify/upload-id` | `platform_review_bp /verify/upload-id` | POST |
| `/review/v2/verify/submit` | `platform_review_bp /verify/submit` | POST |
| `/report/create` | `report_bp /create` | POST |
| `/report/list` | `report_bp /list` | GET |
| `/report/process` | `report_bp /process` | POST |
| `/notify/list` | `notify_bp /list` | GET |
| `/notify/unread` | `notify_bp /unread` | GET |
| `/notify/read` | `notify_bp /read` | POST |
| `/companion/expiry` | `companion_bp /expiry` | GET |

## 常见 Bug 模式

### 1. Token 刷新竞态条件（重要）

**现象**: token 过期后不自动刷新，直接跳登录弹"登录已过期"
**根因**: 后端返回 HTTP 401（状态码在响应头），axios 将其路由到 `err` 回调（第二个参数），但 refresh 逻辑写在 `res` 回调（第一个参数）中——**永远不执行**。
```javascript
// ❌ 错误：HTTP 401 走 err 回调，res 里的 refresh 代码是死代码
api.interceptors.response.use(
  res => { if (res.data.code === 401) { /* 从未被触发 */ } },
  err => { if (err.response.status === 401) { /* 只清理不刷新 */ } }
)
```
**修复**: 
- refresh 逻辑必须写在 **错误回调（第二个参数）** 中
- 使用 `return axios.post(...).then(...)` 异步等待 refresh 结果后再决定是否跳登录
- refresh 成功 → 更新 token → 重试原请求 `api(origReq)`
- refresh 失败 → 清理 + 跳登录
- 参考: `frontend/src/api/index.js`

### 2. Vue `<script setup>` TDZ 陷阱

**现象**: `ReferenceError: Cannot access 'X' before initialization`
**根因**: 在 `<script setup>` 中，`watch` / `computed` / `onMounted` 等回调中引用响应式变量时，变量必须**先声明后使用**。Vue `setup()` 按顺序执行，const 声明前访问会触发 TDZ。
**修复**: 
```javascript
// ✅ 正确：route/router 先声明，再使用
const route = useRoute()
const router = useRouter()
watch(() => route.path, () => { ... })  // route 已声明
onMounted(() => { ... })  // OK
// ❌ 错误：watch 引用未声明的 route
watch(() => route.path, () => { ... })
const route = useRoute()  // TDZ！
```
- `import` 中需要显式包含被 `setup()` 调用的所有函数：`ref, computed, onMounted, onUnmounted, watch, onErrorCaptured`

### 3. 消息通知系统

**数据库**: `message` 表结构：
```sql
id, from_id, to_id, companion_id, content, is_read, 
created_at, type(VARCHAR 20), title(VARCHAR 200), icon(VARCHAR 10), data_id(INT)
```

**后端通知函数** (`app/utils.py`):
```python
send_notification(to_id, content, companion_id=0, from_id=0, 
                  ntype='system', title='', icon='', data_id=0)
```

**订单通知覆盖**:
| 事件 | 通知谁 | type | title | icon |
|------|--------|------|-------|------|
| 下单 | 用户 | order | 订单已创建 | 📝 |
| 下单 | 陪玩师 | order | 新待付订单 | 📋 |
| 支付 | 用户 | order | 支付成功 | 💚 |
| 支付 | 陪玩师 | order | 新订单通知 | 📋 |
| 确认开始 | 陪玩师 | order | 服务已开始 | ▶️ |
| 完成 | 用户 | order | 订单已完成 | ✅ |
| 实名通过 | 用户 | system | 实名认证通过 | ✅ |
| 实名拒绝 | 用户 | system | 实名认证未通过 | ❌ |
| 陪玩师审核通过 | 用户 | system | 陪玩师审核通过 | 🎉 |
| 陪玩师审核拒绝 | 用户 | system | 陪玩师审核未通过 | 📋 |
| 提现提交 | 用户 | system | 提现申请已提交 | 💰 |
| 提现通过 | 用户 | system | 提现审核通过 | ✅ |
| 提现拒绝 | 用户 | system | 提现审核未通过 | ❌ |

**API 返回结构** (`/api/message/list`):
```json
{
  "id": 5, "type": "order", "icon": "📋", "title": "新待付订单",
  "content": "您有一个新订单(#152 ¥25.0)待支付",
  "time": "2026-07-05 13:41:49", "unread": true, "data_id": 152
}
```

**前端底部导航未读红点** (`App.vue`):
- `unreadCount` ref，每30秒 `setInterval` 轮询 `/api/message/count`
- `watch(() => route.path, ...)` 在离开 `/messages` 时刷新
- 红点 CSS: `.badge` 绝对定位在消息图标右上角

### 4. 订单状态显示

**前端 Orders.vue** 需要注意：
- **status=0（待支付）** 必须包含在 `statusText` 和 `tabs` 中
- 需要添加"去支付"按钮（`payOrder` 函数）
- 缺少任何 status 映射都会导致显示"未知"
```javascript
const statusText = { 0: '待支付', 1: '进行中', 2: '待确认', 3: '已完成', 4: '已取消' }
const tabs = [
  { label: '全部', value: 'all' },
  { label: '待支付', value: '0' },  // 容易被遗漏
  ...
]
```

### 5. secureToast 模板（去 Vant showToast）

参考文件: `frontend/src/utils/toast.js`
```javascript
let toastEl = null
let toastTimer = null
function removeToast() { /* 清除定时器 + 移除 DOM */ }
export function safeToast(input, duration = 2000) {
  let msg = typeof input === 'object' ? (input.message ?? '') : String(input)
  msg = msg.trim() || '操作完成'
  removeToast()
  // 创建 div，设置样式，appendChild
  toastTimer = setTimeout(() => removeToast(), duration)
}
```
- **不要用 Promise 包裹** — 同步创建 DOM 避免空白 toast
- `removeToast` 必须清除定时器后再移除 DOM
- 输入为空/undefined 时兜底为 '操作完成'

### 6. 图片上传 — JPEG 文件头检测

**后端 `app/platform_review.py` 中的文件头检查**：
```python
# ❌ 错误：只认 JFIF(\xff\xd8\xff\xe0) 和 Exif(\xff\xd8\xff\xe1)
if img_data[:8] not in (b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1'):
    return fail('请上传JPG或PNG格式图片')

# ✅ 正确：放宽到任何以 \xff\xd8 开头的 JPEG 变体
if img_data[:8] == b'\x89PNG\r\n\x1a\n':
    pass  # PNG
elif img_data[:2] == b'\xff\xd8':
    pass  # JPEG（任何变体）
else:
    return fail('请上传JPG或PNG格式图片')
```
很多手机/相机拍摄的 JPEG 使用 `\xff\xd8\xff\xdb` 或其他 APP 标记，会被误判。PIL 兜底校验已足够。

### 7. Vant Loading 遮罩残留（最频繁）

**现象**: 页面背景变暗，半透明遮罩不消失
**根因**: `showLoadingToast` + `closeToast` 有退出动画，`closeToast()` 不立即移除 DOM。接口响应快时，自定义 toast 与 Vant loading 叠加。
**修复**: 
- 完全移除 `showLoadingToast`/`closeToast` 依赖
- 用自定义 `v-if="overlay"` 控制遮罩
- `finally` 块中确保关闭 + `onUnmounted` 兜底
- 参考文件: Login.vue, Profile.vue, Settings.vue, Verification.vue, Orders.vue

### 8. Vue computed 读取 localStorage 不响应

**现象**: `updateLocalUser()` 后 UI 不更新
**根因**: `computed(() => JSON.parse(localStorage...))` 中 localStorage 不是 Vue 响应式依赖
**修复**: 加 `userVer` ref 作 cache-buster，每次 updateLocal 后 `userVer.value++`。参考: Settings.vue

### 9. `'★'.repeat(score)` RangeError

**现象**: 页面报错"页面加载出错，建议刷新"，控制台 RangeError: Invalid count value
**根因**: `score` 为 undefined/null → `Math.floor(undefined)` = NaN → `repeat(NaN)` 抛异常
**修复**: `Number(score)||0` 守卫。影响文件: List.vue, Detail.vue

### 10. MySQL 字段类型不匹配

**现象**: 500 Internal Server Error, pymysql DataError
**根因**: DB 字段是 TINYINT/INT，后端传了字符串
**常见**: `gender` 是 TINYINT(0/1/2)，不能存 'male'/'female'/'secret'
**修复**: 后端做映射 `{'male': 1, 'female': 2, 'secret': 0}`，返回时反向映射

### 11. axios FormData Content-Type 覆盖

**现象**: 文件上传失败
**根因**: axios 默认 `Content-Type: application/json` 覆盖了 FormData 的 `multipart/form-data`
**修复**: 请求拦截器中 `config.data instanceof FormData → delete config.headers['Content-Type']`

### 12. 管理端前后端字段名不匹配

**常见不匹配**:
- 后端返回 `audit_status: 0` (int) → 前端期望 `audit_status: 'pending'` (string)
- 前端传 `{status: 'approved'}` → 后端期望 `{action: 'approve'}`
- 前端 `POST /toggle-online` → 后端 `PUT /toggle`
- 后端 toggle 操作 `status` 字段 → 前端期望操作 `is_online`
**修复**: 后端做兼容映射，或对齐字段名

### 13. 数据库查询缺少过滤条件

**现象**: 下架的陪玩师仍出现在前端
**根因**: SQL WHERE 只有 `c.status=1`(审核通过)，缺 `c.is_online=1`(在线)
**修复**: 所有前端展示列表的查询加 `c.is_online=1`

### 14. admin.py user_operate 字段白名单被覆盖（复制粘贴陷阱）
**症状**: 封禁/解封用户返回 "没有允许更新的字段"。
**根因**: `user_operate` 函数的白名单逻辑后**意外保留**了从 banner/game 粘贴过来的逻辑，新 ALLOWED 覆盖了正确 ALLOWED，导致 status/role 字段被过滤为空。
**修复**: 只保留一套 ALLOWED + 检查 `safe_updates` 是否为空 + 用正确的 `user_id` 参数。
```python
# ✅ 正确（不要重复声明 ALLOWED）
ALLOWED = {'nickname','phone','email','gender','city','status','phone_bound','avatar'}
safe_updates = {k: v for k, v in updates.items() if k in ALLOWED}
if not safe_updates:
    return fail('没有允许更新的字段')
set_clause = ', '.join([f"`{k}`=%s" for k in safe_updates])
cur.execute(f"UPDATE `user` SET {set_clause} WHERE id=%s",
            list(safe_updates.values()) + [user_id])
```

### 15. 登录路由在重置后缓存旧 token
**症状**: 重置用户密码后，用户端刷新仍提示旧密码错误。
**根因**: bcrypt 校验通过后才返回 token；但若前端 localStorage 有旧 token + refresh_token，在新密码生效前 refresh 仍能拿到新 token。
**修复**: 改密码时同步清除该用户所有 `refresh_token`：
```python
cur.execute("DELETE FROM refresh_token WHERE user_id=%s", (user_id,))
```

### 16. 后端端口不可达时 Nginx 返回 503（不是 504）
**症状**: Nginx 504 Gateway Timeout 是上游超时；503 是上游连接被拒/被限流。
**判断**: `ss -tlnp | grep :5002` 在服务器A 检查监听；curl `http://127.0.0.1:5002/api/health` 在服务器A 测本地连通。
**修复路径**: 看 gunicorn 进程是否启动、是否有 worker 崩溃、Nginx limit_req 是否拦截。

### 17. bcrypt 不在系统 Python 默认包路径
**症状**: gunicorn 启动报 `ModuleNotFoundError: No module named 'bcrypt'`。
**修复**:
```bash
# gunicorn 用的是 /usr/bin/python3.12
/usr/bin/python3.12 -m pip install bcrypt --break-system-packages -q
# 或 apt 装
sudo apt-get install -y python3-bcrypt
```

### 18. 验证码 OCR 自动化登录
tesseract 对算术验证码识别率低（`×` 容易识别成 `x`）。正确做法：
```python
import re
out = subprocess.run(['tesseract', '/tmp/cap.png', '-', '-l', 'eng', '--psm', '7',
                      '-c', 'tessedit_char_whitelist=0123456789+-*xX= ?'],
                     capture_output=True, text=True)
m = re.search(r'(\d+)\s*([+\-*xX])\s*(\d+)\s*=\s*\?', out.stdout.strip())
if m:
    a, op, b = m.groups()
    op = '*' if op in ('x', 'X') else op
    return data['key'], eval(f'{a}{op}{b}')
```

## 用户偏好（沟通与操作）

- 回复要**简洁直接**，不要长篇分析或理论阐述
- **批量操作**，减少来回沟通，一步到位给结果
- 不要展示中间调试步骤，修正后直接给可用的 URL/结果
- 代码修改后必须从安全+功能两方面**自测再交付**
- 网站不能因为部署导致打不开，交付前做端到端验证
- 发现问题直接给结果，不要展示中间调试过程
- 重要操作（如备份、部署）完成后用 ✅/❌ 标记状态

## 用户偏好（样式与交互）

- 所有提示信息必须显示有意义的文字，不能出现空白 toast
- 后端 `msg` 不能为空字符串，前端需 `'请求失败'.trim() || '操作异常'` 兜底
- 优先使用自定义 `safeToast`，不用 Vant 的 `showToast`
- 错误提示要包含实际错误原因，不显示无意义的"请求失败"
- 优先去 Vant 化：遮罩用 `v-if` + `finally` 必关 + `onUnmounted` 兜底
- 删 UI 项时先用 `v-if="false"` 保留代码，等用户确认再彻底删除（方便恢复）

## 部署流程

```bash
# 构建前端
cd /opt/ttdazi/frontend && npm run build
# 重启后端（Server A）
ssh ubuntu@42.193.113.230 "sudo systemctl restart ttdazi"
# 一键部署（构建+重启+同步到Server B）
bash /opt/ttdazi/deploy.sh
```

## 安全加固清单（必须同步）

| 项 | 配置位置 | 关键值 |
|---|---------|--------|
| 后端路径每日轮换 | cron + `/opt/ttdazi/rotate_admin_path.sh` | 0 3 * * * |
| QQ 推送当日地址 | cron | 0 7 * * * |
| WAF ModSecurity | `/etc/nginx/modsecurity.conf` | SQL注入/XSS/路径遍历/扫描器 |
| Nginx 限流 | `ttdazi.conf` | login_limit 10r/m, api_limit 30r/s |
| 安全响应头 | ttdazi.conf | X-Frame/X-XSS/X-Content-Type |
| 后台 IP 白名单 | ttdazi.conf | 42.193.113.230 + 用户IP |
| JWT 过期 | config.py | 24小时 |
| 密码强度 | utils.py validate_password_strength | ≥16位+大小写+数字+特殊符号 |
| 密码 90 天 | utils.py check_password_expired | role=admin 强制 |
| 验证码 | captcha.py | 强制所有登录 |
| 5次锁定 15分钟 | ratelimit.py | 同phone |
| 封禁踢下线 | utils.py login_required | 检查 status=1 |
| 字段白名单 | admin.py user_operate | 防止 SQL 注入 |
| 文件魔数校验 | companion.py/platform_review.py | 双重校验扩展名 |
| bcrypt 环境变量 | config.py | JWT_SECRET/MYSQL_PASSWORD |
| 备份到下载页 | backup | ttdazi_db.sql.gz |

## 新项目隔离规范（铁律）

用户要求：**开发新项目时，严禁修改已有的支付系统、网站系统和数据库。** 每个新项目必须完全独立，零影响现有系统。

### 新项目隔离清单

| 维度 | 要求 | 示例（aiweb项目） |
|:----|:------|:-----------------|
| 📁 **代码目录** | 全新目录，不与旧项目混放 | `/opt/aiweb/` 而非 `/opt/ttdazi/` |
| 🗄️ **数据库** | 新数据库，独立 schema | `aiweb` 库，非 `huizhiyun` |
| 🔌 **后端端口** | 新端口，不与旧项目冲突 | `5003`（ttdazi 用 `5002`） |
| 🌐 **域名** | 新域名或子域名 | `aiweb.openai2000.cn` |
| 📄 **Nginx配置** | 独立 server block | `/etc/nginx/sites-available/aiweb` |
| ⚙️ **systemd服务** | 独立 service | `aiweb.service`（ttdazi 是 `ttdazi.service`） |
| 🔐 **SSL证书** | 独立申请 | `certbot -d aiweb.openai2000.cn` |
| 🚀 **部署脚本** | 独立 deploy.sh | `/opt/aiweb/deploy.sh` |
| 📦 **Python venv** | 独立虚拟环境 | `/opt/aiweb/venv/` |
| 💾 **备份脚本** | 独立备份 | `/opt/aiweb/daily_backup.sh` |

### 已有项目列表

| 项目 | 目录 | 数据库 | 端口 | 域名 |
|:----|:-----|:------|:----|:-----|
| 🎮 同途搭子 | `/opt/ttdazi/` | `huizhiyun` | `5002` | `dazi.openai2000.cn` |
| 🤖 AI建站 | `/opt/aiweb/` | `aiweb` | `5003` | `aiweb.openai2000.cn` |

> ⚠️ 遇到新项目需求时，先查阅此清单，分配新端口和数据库，确保不冲突。

## 部署完成度检查清单（运营前必跑）

```bash
# 1. 后端健康
curl -s http://82.157.202.24/api/health

# 2. 数据库统计
mysql -u root -phuizhiyun2026 huizhiyun -e "
  SELECT TABLE_NAME, TABLE_ROWS 
  FROM information_schema.TABLES 
  WHERE TABLE_SCHEMA='huizhiyun' ORDER BY TABLE_ROWS DESC;
"

# 3. 清理测试账号（保留 admin/ops_admin）
mysql -u root -phuizhiyun2026 huizhiyun -e "
  DELETE FROM user WHERE status=0 AND username NOT IN ('admin', 'ops_admin');
"

# 4. 全链路API测试
python3 -c "
import requests
for ep in ['/api/health', '/api/captcha/get', '/api/companion/list',
          '/api/review/list', '/api/agreement/get?type=user']:
    print(ep, '->', requests.get(f'http://82.157.202.24{ep}').status_code)
"

# 5. 关键索引存在性
mysql -u root -phuizhiyun2026 huizhiyun -e "SHOW INDEX FROM orders WHERE Key_name LIKE 'idx_%';"
```

## 关键运营参数

### 认证价格（从 site_config/cert_config 动态读取）
| 类型 | 7天 | 包月 | 包年 |
|:----:|:---:|:----:|:----:|
| 游戏搭子 | ¥19 | ¥69 | ¥369 |
| 旅游搭子 | ¥69 | ¥199 | ¥899 |

### 游戏/旅游分类ID映射

**游戏达人**（电子游戏）: id<8（原始7个游戏）+ 15-22（金铲铲/英雄联盟/DNF/梦幻/蛋仔/无畏契约/光遇/永劫无间手游）+ 33-40（台球/羽毛球/声乐/乒乓球/乐器/绘画/舞蹈/健身交流）

**同城达人**（技能/运动/生活）: id 8-14（原旅游7个）+ 23-32（出行翻译/包车/跟拍/露营/出海/文化/骑行/滑雪/徒步/探店）

**双重认证**: companion表有 `expires_at_game` 和 `expires_at_travel` 两个字段，支付时按 game_id 更新对应字段。添加新分类后必须同步修改 List.vue / Home.vue / companion.py 三处的过滤范围。

### 管理后台
- 路径格式: `/#/op-xxx/xxx`（hash模式）
- rotate_admin_path.sh 已知Bug: router/index.js的defaultPrefix不自动更新，需手动补修后重新部署

### 白屏修复（qrcodejs2 不兼容 Vite）
- **根因**: `qrcodejs2` 中 `_android` 变量在 Vite 打包时未定义 → vendor 崩溃 → Vue 不挂载
- **修复**: 改用 `qrcode` 包（`qrcode@1.5.4`）
- Vite 构建后自动加 `crossorigin` 属性到所有 script/link 标签，必须移除：
  ```bash
  sed -i 's/ crossorigin//g' dist/index.html
  ```
- Nginx assets location 需加 `add_header Access-Control-Allow-Origin '*' always;`
- `deploy.sh` 需先清理旧 assets 再拷贝

### 服务器B OOM 预防
- Chrome renderer/GPU 进程占满 CPU/RAM 导致 SSH 超时
- cron 每30分钟清理一次
- 如出现需 VNC 登录或重启

### 备份配置
- 位置: Server A 数据盘 `/data/disk/`（20G，2026-08-28 清理后剩 13G/33%）
- 频率: 每日凌晨 2:00（cron）
- 保留: **15天**（2026-08-28 用户从 90 天改为 15 天，`daily_backup.sh` 的 `RETENTION_DAYS=15` 已同步；每日约 410M，15 天 ≈ 6G）
- 内容: huizhiyun + aiweb 双库 + 源码 + 上传文件 + Nginx配置 + **Hermes 记忆（AES 加密，密钥 `hzy_mem_2026_<hostname>`，文件 `hermes_memory.tar.gz.enc`）**
- 额外: 同步一份到 Server B 密码保护下载页 `https://dazi.openai2000.cn/backup/`
- 脚本: `/opt/ttdazi/daily_backup.sh`；另有 `/opt/ttdazi/backup_hermes.sh`（每日4:00，Hermes skills/memories/workspace/config → AES 加密 → 邮件）
- ⚠️ 清理逻辑：`find $BACKUP_BASE -maxdepth 1 -name "daily_*" -type d -mtime +15 -exec rm -rf`（sudo 执行，`/data/disk` 属 root，普通用户 rm 会 Permission denied）

### 备份下载
- 地址: `https://dazi.openai2000.cn/backup/`（需密码）
- 用户名: backup，密码由生成时记录
- htpasswd文件: Server B `/etc/nginx/backup-auth/.htpasswd`
- 每日备份脚本 `daily_backup.sh` 已集成自动同步

### 同途搭子路由
- 使用 `createWebHashHistory`（hash模式），URL 带 `#/`
- Server B 禁止IP直接访问: `/etc/nginx/sites-enabled/deny-ip.conf`（listen 80/443 default_server → return 444）

## 验证码 OCR 识别模式（自动化测试用）

```python
import requests, subprocess, base64, io, re
from PIL import Image

def solve_captcha(url='http://82.157.202.24'):
    r = requests.get(f'{url}/api/captcha/get')
    data = r.json().get('data', {})
    b64 = data.get('image', '').replace('data:image/png;base64,', '')
    Image.open(io.BytesIO(base64.b64decode(b64))).save('/tmp/cap.png')
    for psm in ['7', '8']:
        out = subprocess.run(['tesseract', '/tmp/cap.png', '-', '-l', 'eng',
                              '--psm', psm, '-c',
                              'tessedit_char_whitelist=0123456789+-*xX= ?'],
                             capture_output=True, text=True, timeout=5)
        m = re.search(r'(\d+)\s*([+\-*xX])\s*(\d+)\s*=\s*\?', out.stdout.strip())
        if m:
            a, op, b = m.groups()
            op = '*' if op in ('x', 'X') else op
            return data['key'], eval(f'{a}{op}{b}')
    return None, None
```

## 支付回调现状（2026-08-28 审计结论 ⚠️）

**同途搭子微信支付回调从未自动成功过**（历史订单全部 status=0，`huizhiyun.pay_order` 的 callback_status 全是 2=失败）：
- 下单链路正常：前端 → `/api/pay/wxpay/native`（`pay_api.py`，订单号前缀 `CZ`/`JS`/`DMD`）→ 网关 `pay.openai2000.cn/api/v1/wxpay/native` → 微信码
- 回调链路断：微信支付成功 → 微信回调网关 notify → 网关按前缀路由 → **dazi 回调从未收到**（根因：微信商户平台 APIv3 回调域名未配置/证书 ECDSA，详见 wechat-pay-gateway skill）
- **后果**：用户付了钱但 balance 不自动到账，需要**手动补单**（`UPDATE recharge SET status=1` + balance + money_log）
- 排查定式（钱付了不生效时）：①`/wxpay/query` 微信侧 SUCCESS？→ ②openssl 看 pay 证书 RSA？→ ③tcpdump 抓 443 看微信 IP 是否真的来连 → ④用户去商户平台核对回调 URL 配置
- 前端 `pay_api.py` 的 `notify_recharge`（`/api/pay/notify/recharge`）接收网关 JSON `{order_no, status}`，处理 CZ（充值 balance）+ DMD（需求单转可见）——**该接口本身可用，缺的是网关把回调送过来**

## 常见坑（运维期）

### WAF 拦截验证码 OCR 字符
ModSecurity 规则会被 `/api/captcha/get` 的算术字符触发（如 `<`、`?`）。  
**症状**: curl 返回 200 但 body 是空，JSON 解析失败。  
**修复**: WAF 规则只针对 SQL/XSS 关键词，避免 `.` `?` `+` `*` 命中；或对 `/api/captcha/*` 排除 modsecurity。

### Nginx 限流 burst 调试
**症状**: 自动化测试连续返回 503。  
**修复路径**:
1. 先 `burst=100` 跑通测试 → 验证是限流问题
2. 确认业务正常后改回 `burst=10`（login）/ `burst=20`（api）生产值
3. 同时调高 `limit_req_zone rate=`（如 `30r/s`）应对突发

### admin.py user_operate 函数混入 banner/game 逻辑（复制粘贴陷阱）
**症状**: 封禁/解封用户返回 "没有允许更新的字段"。  
**根因**: `user_operate` 函数的白名单后**重复出现** banner/game 的更新逻辑（变量名是 `gid` 而非 `user_id`）。  
**修复**: 只保留一套 `ALLOWED = {...}` + `if not safe_updates: return fail(...)` + `cur.execute(...user_id)`。  
**预防**: 类似的「按 ID 更新表」函数必须独立成函数，不要跨模块复用。

### bcrypt 在系统 Python 不可用
**症状**: gunicorn worker 启动失败 / pip 安装时 `externally-managed-environment`。  
**修复**:
```bash
# 系统 Python (python3.12) 安装
/usr/bin/python3.12 -m pip install bcrypt --break-system-packages -q
# 或 apt 安装
sudo apt-get install -y python3-bcrypt
# 生成 hash 用 dev / Python 3.12
PYTHONPATH=/usr/lib/python3/dist-packages python3 -c "import bcrypt; print(bcrypt.hashpw(b'pwd', bcrypt.gensalt()).decode())"
```

### 后端端口必须双向可达
服务器A 后端监听 `0.0.0.0:5002`，服务器B Nginx 才能 `proxy_pass http://42.193.113.230:5002`。  
**症状**: Nginx 返回 504 Gateway Timeout。  
**检查**: `ss -tlnp | grep :5002` 在服务器A 上看。

### 重置 bcrypt 密码的 SQL
```sql
-- 用生成的 hash 替换
UPDATE `user` SET password='$2b$12$...', pwd_changed_at=NOW() 
WHERE phone='13800138000' OR username='964539086@qq.com';
```

### `/api/admin/user/{id}` PUT 字段白名单
`user_operate` 函数必须在 `safe_updates = {k: v for k, v in updates.items() if k in ALLOWED}` 后立即 `if not safe_updates: return fail('没有允许更新的字段')`，**不要再声明新的 ALLOWED 覆盖**，否则 status/role 等字段会被过滤掉。

### 字段名一致性陷阱（v-if="false" 用户偏好）
用户偏好：用 `v-if="false"` **保留**旧代码，方便以后恢复，而不是直接删除。  
典型例子: 设置页删除「手机号」时，先尝试 `v-if="false"`，等用户确认才彻底删。  
同样适用于:
- 后端字段加白名单时「保留旧字段为 deprecated」而不是 drop
- 配置项删除时「保留配置 key 默认空」而不是 unset

## 全链路测试覆盖（运营前必跑）

| 模块 | 必测端点 |
|------|---------|
| 公开 | `/api/companion/list`, `/api/review/list`, `/api/agreement/get` |
| 用户 | `/api/user/login`, `/api/user/info`, `/api/order/list`, `/api/message/list`, `/api/favorite/list` |
| 管理 | `/api/admin/users`, `/api/admin/finance`, `/api/admin/verifies`, `/api/admin/orders`, `/api/admin/messages`, `/api/admin/playmates` |
| 公开页面 | `/`, `/login`, `/register`, `/playmate/login`, `/profile`, `/orders`, `/messages`, `/download`, `/agreement/*` |
