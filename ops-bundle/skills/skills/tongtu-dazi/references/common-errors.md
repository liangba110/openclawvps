# 常见错误速查（更新至 2026-07-09）

## 502 Bad Gateway（后端崩溃）
**原因：** Python 模块加载失败（import 错误）
```bash
cd /opt/ttdazi/backend && python3.12 -c "from main import app; print('OK')"
sudo journalctl -u ttdazi --no-pager -n 30 | grep -i 'error\|traceback'
```

### ⚠️ admin_required 导入（发生 3 次！）
```python
# ❌ from app.utils import admin_required  → ImportError
# ✅ from app.admin import admin_required
```
> config_api.py, customer_service.py 等都中过这个坑。

### View function overwriting
```
AssertionError: View function mapping is overwriting an existing endpoint function
```
不要在同文件中定义两个同名的路由函数。

### cur 在 with 块外使用 → Cursor closed
**症状：** `pymysql.err.ProgrammingError: Cursor closed`
**根因：** `with conn.cursor() as cur:` 块结束后 cur 关闭，后续还在用。
**修复：** 所有 SQL 放到 `with` 块内，commit 之前完成。

### companion 表没有 nickname 列
**症状：** `Unknown column 'nickname' in 'field list'`（500）
**根因：** nickname 在 user 表，companion 表只有 id, user_id, game_id, rank_title, price_1h/2h/night, intro, is_online, status, tags, life_photos, max_hours_per_day, alipay_account, account_name。

### get_site_config 未导入
**症状：** `NameError: name 'get_site_config' is not defined`
**根因：** `get_site_config` 在 `app/utils.py` 中，用 `from app.utils import ... get_site_config` 导入（不是 `from app.config`）。
**排查：** grep 确认 import 行包含 get_site_config。

### sibling subagent 覆盖 + __pycache__ 缓存
**症状：** 修改了文件，重启后仍运行旧逻辑。
**修复：** `find /opt/ttdazi/backend -name "__pycache__" -type d -exec rm -rf {} +` 然后重启。

### audit_log 函数不存在
**症状：** `NameError: name 'audit_log' is not defined`
**根因：** admin.py 内部没有可引用的 audit_log 函数。改用 `INSERT INTO audit_log` 原生 SQL。

### conn 定义在 if 块内
**症状：** 只改昵称时 500，改手机号时正常。
**根因：** conn = get_connection() 写在 `if 'phone' in data:` 块内。
**修复：** 数据库连接统一在函数顶部获取，不在 if 块内定义。

### withdraw.history API 缺 fee 字段
**症状：** 前端提现记录显示申请总额而非净额。
**根因：** SELECT 漏了 fee 列。
**修复：** `SELECT id, amount, fee, status, created_at, updated_at FROM withdraw`

### and/or 不是三元表达式
**问题：** `sc == 0 and 0 or -r['id']` → Python 中 `0 or X` 返回 X。
**修复：** 用 `0 if sc == 0 else -r['id']`。

## 前端 Vue

### Vue 3 模板中无法访问 sessionStorage / window
**症状：** 渲染报 `Cannot read properties of undefined (reading 'getItem')`
**根因：** sessionStorage 不在 Vue 模板白名单内。
**修复：** 在 `<script setup>` 中定义变量，模板只引用变量名。

### computed / watch 未导入
**症状：** 构建通过，运行时报 `ReferenceError: computed is not defined`
**修复：** 检查 import 行是否包含 computed, watch, onMounted 等。

### Build 失败但 tail -5 显示正常
**症状：** 功能不生效，dist 是旧版本。
**根因：** Vite 构建中途失败不生成新 dist。
**预防：** 构建后确认输出包含 `✓ built in Xs`。

### `<script setup>` TDZ（暂时性死区）
**症状：** `ReferenceError: Cannot access 'X' before initialization`
**修复顺序：** useXxx() → ref/reactive → computed → onMounted/watch

### withdraw.status 映射错误
**症状：** 被拒绝的提现显示为"已到账"。
**正确映射：** `{0:'审核中',1:'已通过',2:'已拒绝',3:'已到账'}`

## 前端 JS 类型错误

### Cannot create property '_slow' on number
```javascript
// ❌ setInterval 返回数字ID, 不能挂属性
timer._slow = slowTimer
// ✅ 用独立变量
let timer = null, slowTimer = null
```

### .map is not a function
原因：后端返回 `{list: [...], total: N}`，axios 拦截器 unwrap 为对象，前端误当数组
```javascript
// ✅ 取 .list
allOrders.value = ((res && res.list) || []).map(...)
```

### navigate.clipboard 在 HTTP 下 undefined
```javascript
// ✅ 降级方案
if (navigator.clipboard) { ... }
else {
  const ta = document.createElement('textarea')
  ta.value = url; document.body.appendChild(ta)
  ta.select(); document.execCommand('copy')
  document.body.removeChild(ta)
}
```

## 前后端字段不匹配

| 场景 | 前端期望 | 后端返回 | 修复 |
|------|---------|---------|------|
| 订单客户名 | customer_nickname | user_nickname | 后端 pop → 重命名 |
| 订单陪玩师 | playmate_nickname | companion_nickname | 同上 |
| 订单状态 | 'pending'/'paid' 字符串 | 0/1/2 整数 | 后端 status_map |
| 用户列表 | .list 数组 | {list:[]} 对象 | 前端 res.list |
| 下载token | data.token | token(顶级) | 后端用 data 包裹 |
| 实名认证 | u.verified | u.verify_status | 列名修正 |
| gender | 男/女 字符串 | 0/1/2 整数 | 后端映射 |
| audit_status | 'pending' 字符串 | status 0/1/2 整数 | 后端映射 |
| verify_codes | phone 列存邮箱 | VARCHAR(100) | 查询时 WHERE phone=%s 传入邮箱 |
| verify_codes.verified | 未标记 verified=1 | 注册时报"请先验证验证码" | register-by-email 中自动标记 verified=1 |

## SMTP 邮件发送失败

**错误：** `550, 'The recipient may contain a non-existent account'`

**原因：** QQ邮箱 SMTP 会校验收件人是否存在，对不存在的邮箱地址返回 550 拒绝发送。

**影响：** 仅影响测试阶段使用虚构邮箱地址的用户。真实用户使用本人邮箱时正常。

**验证：** 测试阶段可在页面底部查看 `devCode`（API 返回 `_dev_code` 字段时自动显示）。

## Favicon SVG viewBox 裁剪

**症状：** 浏览器 tab 图标被切边，显示不完整。

**修复：** 加大 SVG viewBox 和 font-size：
```html
<!-- ❌ viewBox=100 太窄，🎮 emoji 被裁切 -->
<link rel="icon" href="data:image/svg+xml,<svg viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎮</text></svg>">
<!-- ✅ viewBox=120 留足空间 -->
<link rel="icon" href="data:image/svg+xml,<svg viewBox='0 0 120 120'><text y='.95em' font-size='100'>🎮</text></svg>">
```

> Emoji favicon 的 viewBox 需要比实际字体大 15-20%，否则会被各浏览器以不同方式裁剪。

## 前端 404（页面空白）
**原因：** 路由指向了不存在的 `.vue` 文件
- 检查 `router/index.js` 中 `import('@/views/XXX.vue')` 的文件名与实际文件名完全一致
- 大小写敏感！`Verification.vue` ≠ `VerifyIdentity.vue`

## 请求方法不匹配
| 错误 | 原因 | 修复 |
|------|------|------|
| 405 on favorite/check | 前端 POST → 后端 GET | 改 api.get() |
| 405 on user/profile | 前端 POST → 后端 GET/PUT | 改 api.put('/user/update') |

## 数据库列名陷阱
```sql
-- user 表实名列是 verify_status 不是 verified
SELECT u.verify_status FROM user;
```

## Nginx 缓存问题
- `expires 7d` 会让旧响应被浏览器长期缓存，文件删了客户端还能"看到"
- 备份文件改用 `app/backups/` 私有目录 + token 验证
- uploads 路由需检查文件存在性，不存在返回真 404（非 SPA 兜底 HTML）
