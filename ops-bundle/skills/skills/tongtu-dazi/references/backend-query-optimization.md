# 后端查询优化 & 安全审计模式

## 数据库查询优化：JOIN 替代 N+1

### 典型模式：重复查询同一订单/用户

**反面模式——多次独立查询同一数据：**

```python
# ❌ N+1 模式：pay() 函数对同一订单查询了 5 次
cur.execute("SELECT id, status FROM orders WHERE id=%s AND user_id=%s", ...)  # 1
cur.execute("SELECT companion_id, amount FROM orders WHERE id=%s", ...)        # 2
cur.execute("SELECT c.user_id FROM orders o JOIN companion c ... WHERE o.id=%s", ...)  # 3
cur.execute("SELECT companion_id, amount FROM orders WHERE id=%s", ...)        # 4 — 重复2！
get_site_config('commission_rate', 20)                                         # 外部调用
# 然后又重复计算了同一笔金额
```

**优化方案——一次 JOIN 获取全部所需字段：**

```python
# ✅ JOIN 优化：一次查询带回订单+关联数据
cur.execute("""
    SELECT o.id, o.status, o.amount, o.companion_id, o.game_id,
           c.user_id as companion_user_id
    FROM `orders` o
    JOIN `companion` c ON c.id = o.companion_id
    WHERE o.id=%s AND o.user_id=%s
""", (order_id, user_id))
oinfo = cur.fetchone()
# 一次查询拿到：订单状态 + 金额 + 陪玩师ID + 陪玩师 user_id
# 后续只需计算并更新，无需再查
```

### 检查清单

每次新增或修改数据库函数时，检查以下模式：

| 模式 | 问题 | 修复 |
|------|------|------|
| `SELECT ... WHERE id=%s` 后跟另一个同表 `SELECT` | 重复查询 | 合并为一次 JOIN 或加列 |
| 循环内 `cur.execute()` | N+1 查询 | JOIN + GROUP_CONCAT 或子查询 |
| `get_site_config()` 在热点路径调用 | 每次查表 | 缓存或函数内批量读取 |

### 2026-07-09 修复案例

**order.py pay() 函数：** 优化前 5 次查询（3 次查同一订单 + 2 次查陪玩师）→ 优化后 1 次 JOIN 查询。同时修复了重复计算 `companion_income` 的问题（原代码计算了 2 次）。

**order.py confirm() 函数：** 优化前 2 次查询（查订单 + 查陪玩师 user_id）→ 优化后 1 次 JOIN。

---

## `cursor.lastrowid` 在 `with` 块外使用

### 问题

`with conn.cursor() as cur:` 块结束后，`cur` 游标已被 PyMySQL 的上下文管理器关闭。此时访问 `cur.lastrowid` 可能返回 `None`、抛 `AttributeError` 或读到不可预测的值。

```python
# ❌ 错误 — cur 在 with 块外使用
with conn.cursor() as cur:
    cur.execute("INSERT INTO orders (...) VALUES (...)")
    conn.commit()
# 此时 cur 已关闭！
order_id = cur.lastrowid  # → 可能为 None 或抛异常
send_notification(..., data_id=cur.lastrowid)  # → 通知发到错误 ID
```

### 修复

在 `with` 块内、`commit()` 之前读取 `lastrowid`：

```python
# ✅ 正确 — 在 with 块内读取
with conn.cursor() as cur:
    cur.execute("INSERT INTO orders (...) VALUES (...)")
    order_id = cur.lastrowid or 0  # 块内读取！安全
    conn.commit()
# 此时 cur 已关闭，但 order_id 已保存
send_notification(..., data_id=order_id)
```

### 2026-07-09 修复案例

**order.py create()：** `cur.lastrowid` 在 `with` 块外被赋值给 `order_id`，同时被 `audit_log()` 和 `send_notification()` 引用。已修复为块内读取。

---

## 安全审计：admin 路由认证检查

### 每次上线前必须检查

```bash
# 列出所有 admin 路由，检查是否都有 @admin_required
grep -n "@admin_bp.route" backend/app/admin.py
# 对照 grep -B1 "def " 检查每个路由上方是否有 @admin_required
```

### 2026-07-09 发现的安全漏洞

| 路由 | 问题 | 修复 |
|------|------|------|
| `POST /api/admin/register` | 无任何认证装饰器 | ✅ 加 `@admin_required` |

**影响：** 任何人知道此端点即可创建管理员账号，获得完全管理权限。

### 常见遗漏模式

- `admin/register` / `admin/setup` 等初始化类路由 — 开发者认为"只有初始化时用"而忘记加认证
- `admin/health` / `admin/status` 等监控类路由 — 认为"只是状态查询"而忽略
- Blueprint 新增路由时忘记装饰器

---

## 安全审计：conn 连接泄漏检查

### 检查方法

```bash
# 统计 get_connection() 调用次数与 conn.close() 次数
grep -c "get_connection()" backend/app/*.py
grep -c "conn.close()" backend/app/*.py
# 预期：次数应一致（少说明有泄漏）
```

### 常见泄漏模式

```python
# ❌ conn 在 if 块内赋值但未在 finally 中关闭
if 'avatar' in data:
    conn2 = get_connection()   # ← 泄漏！从未 close
    # ... 但后续代码用了 conn（不是 conn2）

# ✅ 如果确实需要额外连接，必须配对 close
if 'avatar' in data:
    conn2 = get_connection()
    try:
        # ... 使用 conn2
    finally:
        conn2.close()
```

### 2026-07-09 修复案例

**playmate_api.py update_profile()：** `conn2 = get_connection()` 在第 442 行赋值，但代码从未使用 `conn2`，也未在任何地方 `conn2.close()`。已在修复中删除该无用连接。
