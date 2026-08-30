# 搭子(达人)显示和分页模式

## 搭子显示条件

后端 `companion/list` API 的 WHERE 条件：
```sql
c.status=1          -- 已审核通过
c.is_online=1       -- 上架状态
u.status=1          -- 用户账号正常
c.expires_at_travel > NOW()  -- 旅游有效期未过期
c.game_id >= 8      -- 有效游戏分类
```

常见排除原因：
1. **`expires_at_travel` 为 NULL** — 管理员升达人时没设有效期。修复：`UPDATE companion SET expires_at_travel = DATE_ADD(NOW(), INTERVAL 30 DAY) WHERE status=1 AND (expires_at_travel IS NULL OR expires_at_travel <= NOW())`
2. **`game_id` 不在有效范围** — 原过滤 `game_id>=8 AND game_id<=14` 太严格，扩展分类后应改为 `game_id>=8`
3. **`is_online=0`** — 被手动下架

## 管理员升达人（toggle-companion）

原 `toggle_companion` 只执行 `UPDATE user SET is_companion=1`，但不会：
- 创建 companion 记录（如果没有）
- 设置 `expires_at_travel`

修复后版本应自动：
```python
if new_val == 1:
    expires = datetime.now() + timedelta(days=30)
    # 检查companion记录是否存在
    cur.execute("SELECT id FROM companion WHERE user_id=%s", (uid,))
    existing = cur.fetchone()
    if existing:
        cur.execute("UPDATE companion SET status=1, is_online=1, expires_at_travel=%s WHERE user_id=%s", (expires, uid))
    else:
        cur.execute("INSERT INTO companion (user_id, game_id, price_1h, price_2h, status, is_online, expires_at_travel, created_at) VALUES (%s, 8, 50.00, 90.00, 1, 1, %s, NOW())", (uid, expires))
```

## 前端分页通用模式

所有列表页统一模式：

```vue
<script setup>
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

async function load(p) {
  if (p !== undefined) page.value = p
  const res = await api.get('/api/xxx', { params: { page: page.value, page_size: pageSize.value } })
  list.value = res.list || []
  total.value = res.total || 0
}
</script>

<template>
  <!-- 列表... -->
  <div class="pagination" v-if="total > pageSize">
    <button :disabled="page<=1" @click="page--; load()">‹ 上一页</button>
    <span>{{ page }} / {{ totalPages }}</span>
    <button :disabled="page>=totalPages" @click="page++; load()">下一页 ›</button>
  </div>
</template>

<style scoped>
.pagination { display: flex; justify-content: center; align-items: center; gap: 12px; padding: 16px 0 24px; }
.pagination button { padding: 6px 16px; border: 1px solid #ddd; border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; color: #666; }
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
.pagination span { font-size: 13px; color: #999; }
</style>
```

筛选/搜索切换时重置到第1页：`load(1)`
