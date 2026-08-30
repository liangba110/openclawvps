# 需求订单号格式

## 生成规则

```python
# backend/app/demand.py — create() 函数中
order_no = datetime.now().strftime('%Y%m%d%H%M') + ''.join(__import__('random').choices('0123456789', k=4))
# 示例: "2026070703385642"
```

- 14 位纯数字：`YYYYMMDDHHmm` + `RRRR`（4位随机）
- 无业务含义前缀字母
- 数据库列 `order_no VARCHAR(32) DEFAULT ''`，用 ALTER TABLE 后加

## 新旧数据兼容

旧数据（添加列前创建的）order_no 为空字符串 `''`。补回脚本：

```python
cur.execute("SELECT id, created_at FROM demand_order WHERE order_no IS NULL OR order_no=''")
for r in rows:
    ts = r['created_at'].strftime('%Y%m%d%H%M')
    rand = ''.join(random.choices('0123456789', k=4))
    cur.execute("UPDATE demand_order SET order_no=%s WHERE id=%s", (f"{ts}{rand}", r['id']))
```

## 前端显示

两个页面的底部（demand-foot）都显示 `订单号 xxxxxxxxxxxx`：

```vue
<!-- DemandHall.vue -->
<div class="demand-foot">
  <span>{{ formatTime(d.created_at) }}</span>
  <span v-if="d.order_no" class="order-no-text">订单号 {{ d.order_no }}</span>
  <span v-if="d.status === 0" class="action-btn primary" @click.stop="acceptDemand(d)">📩 接单</span>
</div>

<!-- MyDemands.vue → 同样在 demand-foot 中 -->
<span v-if="d.order_no" class="order-no-text">订单号 {{ d.order_no }}</span>
```

CSS：
```css
.order-no-text { font-size: 10px; color: #999; margin-right: 12px; }
```

**注意：** 不在卡片顶部用户头像下单独显示 order_no。统一放在底部日期后方。
