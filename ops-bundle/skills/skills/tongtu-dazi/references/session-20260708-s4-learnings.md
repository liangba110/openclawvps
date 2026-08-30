# Session 2026-07-08 关键修复模式

## 1. `playmate_audit()` Cursor closed 500

**位置:** `admin.py` → `playmate_audit()`

**错误日志:** `pymysql.err.ProgrammingError: Cursor closed`

**修复:** 将 `cur.execute("SELECT user_id FROM companion...")` 移到 `with conn.cursor() as cur:` 块内，在 `conn.commit()` 之前完成。将结果存入变量后退出 with 块再使用。

## 2. `companion` 表没有 `nickname` 列

**错误日志:** `pymysql.err.OperationalError: (1054, "Unknown column 'nickname' in 'field list'")`

**位置:** `admin.py` → `playmate_audit()`

**修复:** `SELECT user_id, nickname FROM companion` → `SELECT user_id FROM companion`（`nickname` 在 user 表）

## 3. `audit_log` 函数不存在

**错误日志:** `NameError: name 'audit_log' is not defined`

**定位:** `from app.utils import audit_log` 不存在（utils.py 没有此函数）

**修复:** 改用原生 `INSERT INTO audit_log` 替代 `audit_log()` 函数调用。

## 4. Backfill vid=0 审批流程

**问题:** `verify_application` 表中无记录的用户（历史数据），前端用 `vid=0` 表示。审批时需要从请求体获取 `user_id`。

**前端修复:**
```javascript
// vid=0 时发送 user_id
const body = v.id === 0 ? { user_id: v.user_id } : {}
await api.post(`/admin/verify/${v.id}/approve`, body)
```

**后端修复 (approve):**
```python
if cur.rowcount == 0:
    if vid == 0:
        uid = (request.get_json() or {}).get('user_id', 0)
        cur.execute("UPDATE user SET verify_status=1 WHERE id=%s", (uid,))
```

**后端修复 (reject):** 同理，增加 `vid == 0` 分支 + `verify_reason` 列（需 ALTER TABLE user ADD COLUMN verify_reason）。

## 5. 邮箱注册 `phone` = `email` 导致手机号显示邮箱

**根因:** user.py `register_by_email()` 中 `INSERT INTO user (..., phone, ...) VALUES (..., email, ...)`

**修复:** `phone=email` → `phone=''`

**数据库修复:** `UPDATE user SET phone = CONCAT('email_user_', id) WHERE phone=email AND email!=''`

## 6. CompanionRegister 重复申请拦截

**前端 onMounted 拦截:**
```javascript
onMounted(async () => {
  try {
    const prof = await api.get('/companion/my')
    if (prof && prof.id && prof.status === 1) {
      safeToast('您已通过陪玩师审核，无需重复申请')
      router.replace('/')
      return
    }
  } catch(e) { /* 不是陪玩师，正常继续 */ }
  // ...load games...
})
```

**后端拦截:** `companion.py register()` 中已有 `status=1 → fail('您已通过审核')`

**API 响应未检查** — `api.post('/companion/register')` 后加 `if (!res || res.code !== 0)` 检查。

## 7. Companion `is_online` 默认全为 1

**根因:** `companion` 表 `is_online` DEFAULT=1，且从未更新过。

**修复:** 不用 `c.is_online`，改用 `login_log` 实时判断：
```sql
CASE WHEN ll.last_active > NOW() - INTERVAL 5 MINUTE THEN 1 ELSE 0 END as online_status
LEFT JOIN (
    SELECT user_id, MAX(created_at) as last_active FROM login_log GROUP BY user_id
) ll ON ll.user_id = c.user_id
```

## 8. `.admin-main { margin-left: 220px }` 残留

**根因:** `global.css` 全局定义 + 个别页面 scoped CSS 中残留此样式。在 flex 布局下导致内容偏移 220px。

**扫描命令:**
```bash
grep -rn "margin-left.*220" /opt/ttdazi/frontend/src/ --include="*.vue" --include="*.css"
```
