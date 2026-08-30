# 实名认证双表同步机制

## 架构

用户实名认证涉及两张表：

| 表 | 用途 | 关键列 |
|----|------|--------|
| `user` | 用户主表 | `verify_status` (0=未认证, 1=已通过, 2=待审核, 3=已拒绝), `verify_reason` |
| `verify_application` | 审核明细表 | `status` (0=待审核, 1=已通过, 2=已拒绝), `id_card_front`, `id_card_back`, `reject_reason` |

## 数据流

```
用户提交 → user.verify_status=2 + INSERT verify_application
                  ↓
管理员查看 → 查询 verify_application JOIN user
                  + 补充查询 user 中 verify_status IN (1,2,3) 但不在 verify_application 中的记录
                  ↓
管理员审核通过 → UPDATE verify_application SET status=1 + UPDATE user SET verify_status=1
管理员审核拒绝 → UPDATE verify_application SET status=2 + UPDATE user SET verify_status=3
```

## 状态映射（前端显示）

```python
# verify_application.status → 显示文字
{0: '待审核', 1: '已通过', 2: '已拒绝'}

# user.verify_status → 显示文字（前端 status_code）
sc = 0 if s == 2 else (2 if s == 3 else s)
{0: '待审核', 1: '已通过', 2: '已拒绝', 3: '已拒绝'}.get(sc, '未知')
```

## backfill 记录（历史数据）

`user` 表中 `verify_status` 不为 0 但 `verify_application` 中无对应记录的数据通过补充查询展示。

### vid 计算

```python
# ✅ 正确：用 Python 三元表达式
'id': 0 if sc == 0 else -r['id']

# ❌ 错误：用 and/or 短路
'id': sc == 0 and 0 or -r['id']   # 当 sc=0 时，计算为 0 or -r['id'] = -r['id']
```

### approve（vid=0）

前端需额外发送 user_id：
```js
const body = v.id === 0 ? { user_id: v.user_id } : {}
await api.post(`/admin/verify/${v.id}/approve`, body)
```

后端直接用 user_id 更新 user 表：
```python
cur.execute("UPDATE user SET verify_status=1 WHERE id=%s", (uid,))
```

### reject（vid=0）

前端同样需要发送 user_id + reason：
```js
const body = { reason: rejectReason.value }
if (v.id === 0) body.user_id = v.user_id
await api.post(`/admin/verify/${v.id}/reject`, body)
```

后端更新 user 表 + 保存拒绝原因：
```python
cur.execute("UPDATE user SET verify_status=3, verify_reason=%s WHERE id=%s", (reason, uid))
```

## 常见问题

### 后台「通过/拒绝」无响应（500 Internal Error）

**排查**：查看后端日志 `sudo journalctl -u ttdazi --no-pager -n 10 | grep -i "error\\|traceback"`

**常见原因**：`audit_log` 函数不存在（admin.py 中既无 import 也无定义）。修复：删除函数调用，替换为直接 SQL INSERT。

### 后台「待审核」不显示任何记录

**排查**：
1. 直接测试 API：`curl -s -H "Authorization: Bearer $TOKEN" /api/admin/verifies`
2. 检查 user 表：`verify_status=2` 是否有记录
3. 检查 verify_application 表：status=0 是否有记录
4. 检查补充查询的 WHERE 条件是否覆盖了所有状态（`verify_status IN (1,2,3)`）

### 已通过/拒绝的记录不显示

**检查补充查询的 WHERE 子句**是否包含 `verify_status=1`（通过）和 `verify_status=3`（拒绝）。
