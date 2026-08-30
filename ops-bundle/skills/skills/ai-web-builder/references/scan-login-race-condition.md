# 扫码登录竞态条件修复

## 问题

扫码确认接口 `scan/confirm` 存在竞态条件：

```python
# ❌ 旧代码：两步提交，中间有空窗
cur.execute("UPDATE scan_login SET status=1 WHERE id=%s", (row['id'],))
conn.commit()  # ← 此时 PC 轮询到 status=1，无 token，显示"等待确认"
pc_token = gen_token(user_id)
cur.execute("UPDATE scan_login SET status=2, user_id=%s, token=%s WHERE id=%s",
            (user_id, pc_token, row['id']))
conn.commit()
```

PC 端每 1.5s 轮询一次 `GET /api/login/scan/status`。当手机确认后，PC 可能恰好在这一小段空窗期轮询到 `status=1`（无 token），导致界面状态混乱。

## 修复

一步到位：直接设置 `status=2` + `token`，单次提交，原子操作：

```python
# ✅ 新代码：一次提交，原子操作
pc_token = gen_token(user_id)
cur.execute(
    "UPDATE scan_login SET status=2, user_id=%s, token=%s WHERE id=%s",
    (user_id, pc_token, row['id']))
conn.commit()
```

## 影响范围

- 后端文件：`/opt/aiweb/backend/app/scan_login.py`（`scan_confirm` 函数）
- 同理检查 `scan_register.py` 的 `bind` 端点是否也有同样问题
