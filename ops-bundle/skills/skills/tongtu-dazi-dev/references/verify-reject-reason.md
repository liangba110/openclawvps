# 实名认证拒绝原因与图片显示

## 拒绝原因保存路径

| 记录类型 | 原因存储位置 |
|---------|-------------|
| 正常（有 verify_application 记录） | `verify_application.reject_reason` |
| backfill（vid=0，仅 user 表有记录） | `user.verify_reason`（需手动 ALTER TABLE 添加） |

## backfill 拒绝流程

1. 前端发送 `{ reason, user_id }` 到 `POST /admin/verify/0/reject`
2. 后端：`UPDATE user SET verify_status=3, verify_reason=%s WHERE id=%s`
3. 管理端查询时：`SELECT ..., verify_reason FROM user WHERE verify_status IN (1,2,3) ...`
4. 返回 `reject_reason: r['verify_reason']`

## 图片不显示排查清单

- [ ] `INSERT INTO verify_application` 是否包含 `id_card_front`, `id_card_back` 列
- [ ] 图片文件是否存在 `/opt/ttdazi/backend/app/uploads/` 下（注意区分 `id_cards` vs `idcards` 子目录名）
- [ ] 图片 URL 能否通过 HTTP 直接访问（`curl -sI /uploads/id_cards/xxx.jpg`）
- [ ] 管理端 API 查询是否 SELECT 了 `id_card_front`, `id_card_back`
- [ ] 前端模板 `v-if="v.id_card_front"` 检查的是空字符串还是 false

## Python 条件表达式陷阱

**错误**：
```python
'id': sc == 0 and 0 or -r['id']
# 当 sc=0: True and 0 → 0, 0 or -10046 → -10046 ❌
```

**正确**：
```python
'id': 0 if sc == 0 else -r['id']
# 当 sc=0: 0 ✅
```
