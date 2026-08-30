# 全栈审计检查清单

## 1. 后端路由全量扫描

```bash
cd /opt/ttdazi/backend && PYTHONPATH="/home/ubuntu/.local/lib/python3.12/site-packages" python3.12 << 'PYEOF'
import re, os

app_dir = '/opt/ttdazi/backend/app'
for f in sorted(os.listdir(app_dir)):
    if not f.endswith('.py') or f.startswith('__'): continue
    path = os.path.join(app_dir, f)
    with open(path) as fh: content = fh.read()
    bp = re.search(r"Blueprint\('(\w+)',\s*__name__,\s*url_prefix='(/api/\w+)'\)", content)
    if not bp: continue
    prefix = bp.group(2)
    for m in re.finditer(r"@\w+_bp\.route\('([^']+)',\s*methods=\[([^\]]+)\]", content):
        methods = [x.strip().strip("'\"") for x in m.group(2).split(',')]
        print(f"  [{','.join(methods):<10}] {prefix}{m.group(1)}")
PYEOF
```

## 2. 前端→后端 API 映射完整性（404 端点发现）

**核心方法：** 正则扫描前端所有 `api.get/post/put('xxx')`，对比后端路由：

```bash
PYTHONPATH="/home/ubuntu/.local/lib/python3.12/site-packages" python3.12 << 'PYEOF'
import re, os

# 后端路由集
backend_routes = set()
app_dir = '/opt/ttdazi/backend/app'
for f in sorted(os.listdir(app_dir)):
    if not f.endswith('.py') or f.startswith('__'): continue
    with open(os.path.join(app_dir, f)) as fh: content = fh.read()
    bp = re.search(r"Blueprint\('(\w+)',\s*__name__,\s*url_prefix='(/api/\w+)'\)", content)
    if not bp: continue
    prefix = bp.group(2)
    for m in re.finditer(r"@\w+_bp\.route\('([^']+)',\s*methods=\[([^\]]+)\]", content):
        route = re.sub(r'<int:(\w+)>', r':\1', m.group(1))
        backend_routes.add(prefix + route)

# Also add main.py direct routes (with methods — don't hardcode GET!)
with open('/opt/ttdazi/backend/main.py') as fh: main_content = fh.read()
for m in re.finditer(r"@app\.route\('([^']+)',\s*methods=\[([^\]]+)\]", main_content):
    methods = [x.strip().strip("'\"") for x in m.group(2).split(',')]
    for method in methods:
        backend_routes.add((m.group(1), method))

# 前端 API 调用
frontend_calls = []
for root, dirs, files in os.walk('/opt/ttdazi/frontend/src/views'):
    for f in files:
        if not f.endswith('.vue'): continue
        vpath = os.path.relpath(os.path.join(root, f), '/opt/ttdazi/frontend/src/views')
        with open(os.path.join(root, f)) as fh: content = fh.read()
        for a in re.finditer(r"api\.(get|post|put|delete)\('/([^']+)'", content):
            frontend_calls.append((vpath, a.group(1).upper(), '/api/' + a.group(2)))

# 查找缺失（支持 tuple 格式的 backend_routes）
missing = []
# 将 backend_routes 转回纯路径集合（方法已内联到 path 中，或直接比对路径）
backend_paths = {br[0] if isinstance(br, tuple) else br for br in backend_routes}
for vue_file, method, path in frontend_calls:
    matched = False
    for br in backend_paths:
        pattern = br.replace(':id', r'\\d+').replace(':uid', r'\\d+').replace(':cid', r'\\d+')
        pattern = pattern.replace(':gid', r'\\d+').replace(':bid', r'\\d+').replace(':vid', r'\\d+')
        pattern = pattern.replace(':wid', r'\\d+').replace(':order_id', r'\\d+').replace(':faq_id', r'\\d+')
        pattern = pattern.replace(':filename', r'.+')
        if re.match(f'^{pattern}$', path): matched = True; break
    if not matched:
        missing.append((vue_file, method, path))

for v, m, p in sorted(missing):
    print(f"  ❌ {v:30s} [{m:<4}] {p}")
PYEOF
```

## 3. `@admin_required` 覆盖率检查

```bash
grep -n '@admin_bp.route' /opt/ttdazi/backend/app/admin.py | while read line; do
  lineno=$(echo "$line" | cut -d: -f1)
  nextline=$((lineno + 1))
  sed -n "${nextline}p" /opt/ttdazi/backend/app/admin.py | grep -q 'admin_required' || echo "  ❌ 缺少装饰器: $line"
done
```

**本期发现：** 3 个端点缺失 `@admin_required`：`security-alert`, `recent-anomalies`, `ban-ip`。全部修复。

## 4. 多方法路由漏扫

扫描器默认只捕获第一个方法。多方法路由（如 `['GET', 'PUT']`）可能被漏记：

```bash
python3 -c "
import re, os
app_dir = '/opt/ttdazi/backend/app'
for f in sorted(os.listdir(app_dir)):
    if not f.endswith('.py') or f.startswith('__'): continue
    with open(os.path.join(app_dir, f)) as fh: content = fh.read()
    for m in re.finditer(r\"@\w+_bp\.route\('([^']+)',\s*methods=\[([^\]]+)\]", content):
        methods = [x.strip().strip(\"'\\\"\") for x in m.group(2).split(',')]
        if len(methods) > 1:
            print(f'  {m.group(1)} methods={methods}')
"
```

## 5. 管理员账号状态

```sql
SELECT id, username, nickname, role, status FROM user WHERE role='admin';
-- status=0 → UPDATE user SET status=1 WHERE role='admin' AND status=0;
```

**本期发现：** admin/admin888 账号 status=0（被禁用），所有admin API返回401。已修复。

## 6. 全局变量作用域审查（conn 定义在 if 块内）

**扫描模式：** 搜索所有 `conn = get_connection()` 是否定义在 `if` 块内。如果在 if 外引用 → 不进入 if 时 NameError。

**检查命令：**
```bash
grep -n "conn = get_connection" /opt/ttdazi/backend/app/*.py
```
然后对每个结果检查前后缩进——如果在 `if` 块缩进下，确认后续是否有跨 if 引用。

**本期发现：** `user.py` `update_profile()` 中 `conn` 定义在 `if 'phone' in data:` 块内，但后续在外引用 `conn.cursor()` → 改昵称时不进 if 块 → NameError 500。

**典型修复：** SQL 执行前统一 `get_connection()`，不在 if 块内定义。

## 7. 前端发送字段 vs 后端 ALLOWED_FIELDS

```bash
# 后端 PlaymateProfile allowed_fields
grep -A5 "allowed_fields" /opt/ttdazi/backend/app/playmate_api.py

# 前端 PlaymateProfile 发送的字段  
grep -o "form\.value\.\w\+" /opt/ttdazi/frontend/src/views/playmate/PlaymateProfile.vue | sort -u
```

**本期发现：** `nickname` 不在 allowed_fields 中，前端发的昵称被丢弃。已修复。

## 8. 前端-后端字段映射错误

**本期发现：**

| 前端文件 | 前端字段 | 期望后端字段 | 影响 |
|---------|---------|-------------|------|
| VerifyIdentity.vue | `id_card` | `id_number` | 实名认证提交易名不匹配 → 后端读不到身份证号 |
| PlaymateProfile.vue | `bio` | `intro` | 简介字段名不匹配 → 保存不生效 |

## 9. 前端 Method 不匹配

**本期发现：**

| 前端文件 | 前端方法 | 后端方法 | 路径 | 影响 |
|---------|---------|---------|------|------|
| AdminContent.vue | POST update | PUT | `/admin/banners/<id>` | 404 方法不允许 |
| AdminContent.vue | POST delete | DELETE | `/admin/banners/<id>` | 404 |
| PlaymateHome.vue | POST | PUT | `/playmate/status` | 404 |

## 10. SELECT 漏列检查

新增字段到数据库后，检查 4 个关键 SELECT 是否同步更新：

| 文件 | SQL 位置 | 关键字段 |
|------|---------|---------|
| `user.py` login() | `SELECT ... FROM user WHERE phone=%s OR username=%s` | phone, email, phone_bound, verify_status |
| `user.py` get_user_info() | `SELECT ... FROM user WHERE id=%s` | verify_status, phone, phone_bound, email |
| `admin.py` user_list | `SELECT ... FROM user` | phone_bound, email |
| `companion.py` detail | `SELECT ... FROM companion c JOIN user u` | verify_status, gender |

## 11. 管理端功能镜像检查（admin-mirror-rule）

每个用户端功能必须有对应管理后台页面。本期验证17管理页 ↔ 38 admin路由，全部匹配。

| 用户端功能 | 管理后台页面 | 管理端路由 |
|-----------|------------|-----------|
| 用户注册/管理 | AdminUsers | `/admin/users` |
| 陪玩师列表/注册 | AdminPlaymates + Detail | `/admin/playmates` |
| 订单管理 | AdminOrders | `/admin/orders` |
| 评价管理 | AdminReviews | `/admin/reviews` |
| 实名认证 | AdminVerify | `/admin/verifies` |
| 提现 | AdminWithdrawals | `/admin/withdrawals` |
| 优惠券 | AdminCoupons | `/api/coupon/admin/*` |
| 协议 | AdminAgreements | `/api/agreement/admin/*` |
| 内容(Banner/游戏) | AdminContent | `/admin/banners` + `/admin/games` |
| 客服 | AdminService | `/api/cs/admin/*` |
| 消息通知 | AdminMessages | `/admin/messages` |
| FAQ学习 | AdminFaq | `/api/cs/admin/faq/*` |
| 系统配置 | AdminConfig | `/api/config/admin/*` |
| 安全监控 | AdminMonitor | `/stats/monitor` |
| 财务明细 | AdminFinance | `/admin/finance` |
| 代码编辑 | AdminCode | `/admin/code/*` |
| 意见反馈 | AdminFeedback | `/api/feedback/admin/*` |
| 仪表盘 | AdminDashboard | `/admin/dashboard` |
