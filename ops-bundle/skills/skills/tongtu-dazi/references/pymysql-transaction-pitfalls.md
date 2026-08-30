# PyMySQL 事务陷阱

## 1. `SELECT ... FOR UPDATE` 在 autocommit 下无效

### 问题

PyMySQL 默认 `autocommit=True`。此时每个 SQL 语句立即自动提交，`FOR UPDATE` 的行锁在SELECT执行完瞬间释放，**等于没加锁**。

```python
# ❌ 错误 — FOR UPDATE 在 autocommit 下完全无效
conn = get_connection()  # autocommit=True（默认）
with conn.cursor() as cur:
    cur.execute("SELECT total_count, used_count FROM coupon WHERE id=%s FOR UPDATE", (cid,))
    # ← 锁在此行执行完就释放了！
    c = cur.fetchone()
    if c['used_count'] >= c['total_count']:
        return fail('已领完')
    # 另一个并发请求此时可以同时执行下面的 INSERT
    cur.execute("INSERT INTO user_coupon ...")  # → 超发！
    conn.commit()
```

### 修复

`FOR UPDATE` 必须在非自动提交模式下使用：

```python
# ✅ 正确 — 关闭 autocommit
conn = get_connection()
conn.autocommit(False)  # ← 必须！
try:
    with conn.cursor() as cur:
        cur.execute("SELECT total_count, used_count FROM coupon WHERE id=%s FOR UPDATE", (cid,))
        c = cur.fetchone()
        if not c:
            conn.rollback()
            return fail('优惠券不存在')
        if c['used_count'] >= c['total_count']:
            conn.rollback()
            return fail('已领完')
        cur.execute("INSERT INTO user_coupon ...")
        conn.commit()
        return True, ''
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
```

**关键点：**
- `conn.autocommit(False)` 必须在 `try` 之前设置
- 所有失败路径必须 `conn.rollback()`
- 成功路径必须 `conn.commit()`
- 异常路径必须 `conn.rollback()` + `raise`

### 2026-07-09 修复案例

**risk_control.py check_coupon_limit()：** 原代码使用 `FOR UPDATE` 但未设置 `autocommit=False`，行锁从未生效。在并发场景下多个用户可同时领取最后一张优惠券，导致超发。已修复为手动管理事务。

---

## 2. `cur.lastrowid` 在 `with` 块外使用

详见 `references/backend-query-optimization.md` 的对应章节。

```python
# ❌ 错误
with conn.cursor() as cur:
    cur.execute("INSERT INTO orders ...")
    conn.commit()
order_id = cur.lastrowid  # ← cur 已关闭！

# ✅ 正确
with conn.cursor() as cur:
    cur.execute("INSERT INTO orders ...")
    order_id = cur.lastrowid or 0  # ← 块内读取
    conn.commit()
```

---

## 3. `conn` 定义在 `if` 块内导致外部引用 NameError

详见主 SKILL.md 的「Flask 变量作用域陷阱：conn 定义在 if 块内」章节。

---

## 4. `get_connection()` 未配对 `close()`（连接泄漏）

详见 `references/backend-query-optimization.md` 的「安全审计：conn 连接泄漏检查」章节。
