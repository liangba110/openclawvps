# 数据库唯一索引 + UPDATE 冲突陷阱

## 问题

清理陪玩师重复数据后添加防重索引：
```sql
CREATE UNIQUE INDEX idx_user_status ON companion(user_id, status)
```

后续审核接口报 500：
```python
cur.execute("UPDATE `companion` SET status=%s WHERE id=%s", (status, cid))
# pymysql.err.IntegrityError: (1062, "Duplicate entry '10042-1' for key 'companion.idx_user_status'")
```

## 根因

| 用户 10042 的 companion 记录 | 状态 |
|----|----|
| ID 7 | status=1 (approved) |
| ID 19 | status=1 (approved) |

`UPDATE companion SET status=1 WHERE id=19` 触发了 InnoDB 唯一约束检测，发现已经有同 (user_id=10042, status=1) 的其他记录 → IntegrityError → 500。

## 解决

审核前先删除同用户的同状态重复记录：
```python
@admin_bp.route('/playmate/<int:cid>/audit', methods=['PUT', 'POST'])
def playmate_audit(cid):
    ...
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 关键：先清理冲突的同状态记录
            cur.execute(
                "DELETE FROM `companion` "
                "WHERE user_id=(SELECT user_id FROM (SELECT user_id FROM `companion` WHERE id=%s) AS t) "
                "AND id!=%s AND status=%s",
                (cid, cid, status)
            )
            cur.execute("UPDATE `companion` SET status=%s WHERE id=%s", (status, cid))
            if status == 1:
                cur.execute(
                    "UPDATE `user` u JOIN `companion` c ON u.id=c.user_id "
                    "SET u.is_companion=1 WHERE c.id=%s", (cid,)
                )
            conn.commit()
```

**为什么用嵌套 SELECT：** 避免 `Can't specify target table for update in FROM clause` 错误（MySQL 限制同一表 SELECT + UPDATE）。

## 前端对应：catch {} 吞掉错误

```js
// ❌ WRONG — 用户看到"没反应"，诊断时无任何线索
try {
  await api.post(`/admin/playmate/${id}/audit`, { status })
  safeToast('已通过')
} catch {}

// ✅ RIGHT — 暴露后端 500 真实原因
try {
  const r = await api.post(`/admin/playmate/${id}/audit`, { status })
  safeToast(r.msg || '已通过')
  info.value.audit_status = status
} catch(e) {
  safeToast(e.message || '操作失败')
}
```

## 经验教训

1. **添加唯一约束前先审视现有数据** — 用 `GROUP BY user_id, status HAVING COUNT(*) > 1` 找出可能冲突的记录
2. **添加唯一约束后所有相关 UPDATE 都要审计** — 不仅是审核接口，任何修改 status 的逻辑都要考虑
3. **admin 前端不要 catch {} 静默吞错** — 这是双倍坑：前端不知道失败原因，后端 500 在生产环境更难发现

## Server B assets 同步陷阱

部署后用户看到 `Failed to fetch dynamically imported module`：
```
GET /assets/Home-Bb9jYW9N.js 404
```

**根因：** Server B 的 `assets/` 目录累积了之前所有 deploy 的 hash 文件，但 `scp -r dist/*` 不删除旧文件。Nginx 提供最新的 `index.html` 引用新 hash，但浏览器可能因缓存命中旧 hash，请求 `404`。

**修复 — 手动清理同步：**
```bash
ssh ubuntu@82.157.202.24 "rm -rf /home/ubuntu/ttdazi-frontend/assets/*"
cd /opt/ttdazi/frontend/dist
sshpass -p 'wll16562341@' scp index.html ubuntu@82.157.202.24:/home/ubuntu/ttdazi-frontend/
sshpass -p 'wll16562341@' scp -r assets ubuntu@82.157.202.24:/home/ubuntu/ttdazi-frontend/
```

**deploy.sh 改进建议：**
```bash
sshpass -p "$SERVER_B_PASS" ssh ... "rm -rf $SERVER_B_PATH/assets && mkdir -p $SERVER_B_PATH/assets"
# 然后再 scp -r dist/*
```

## deploy.sh 验证步骤

部署后立即验证 hash 一致：
```bash
NEW=$(grep -o 'index-[A-Za-z0-9_-]*\.js' /opt/ttdazi/frontend/dist/index.html | head -1)
REMOTE=$(ssh ubuntu@82.157.202.24 "grep -o 'index-[A-Za-z0-9_-]*\.js' /home/ubuntu/ttdazi-frontend/index.html | head -1")
[ "$NEW" = "$REMOTE" ] && echo "✓ synced" || echo "✗ MISMATCH — manual sync required"
```

## 路由文件名必须匹配组件文件

**问题：** 路由 `/verify` 指向 `/views/Verification.vue`，但实际文件是 `VerifyIdentity.vue` → 加载失败，页面空白。

**检查：**
```bash
ls /opt/ttdazi/frontend/src/views/*.vue | grep -i verify
grep -E "/verify|VerifyIdentity|Verification" /opt/ttdazi/frontend/src/router/index.js
```

**修复：** 路由路径必须与 component import 路径精确匹配：
```js
{ path: '/verify', name: 'VerifyIdentity', component: () => import('@/views/VerifyIdentity.vue') }
```