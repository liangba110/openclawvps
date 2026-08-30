# 双重认证（游戏达人 + 旅游达人）

## 数据库

```sql
ALTER TABLE companion ADD COLUMN expires_at_game datetime DEFAULT NULL AFTER expires_at;
ALTER TABLE companion ADD COLUMN expires_at_travel datetime DEFAULT NULL AFTER expires_at_game;
```

## 后端逻辑

### 1. 订单支付时（order.py）

```python
if order_type == 'companion_activate' and days > 0:
    game_id = int(data.get('game_id', 1))
    cert_col = 'expires_at_travel' if game_id >= 8 else 'expires_at_game'
    cur.execute(f"UPDATE companion SET {cert_col} = DATE_ADD(NOW(), INTERVAL %s DAY) WHERE id=%s", (days, companion_id))
```

### 2. 列表过滤（companion.py）

```python
if service_type == 'travel':
    where.append("(c.expires_at_travel IS NOT NULL AND c.expires_at_travel > NOW())")
elif service_type == 'game':
    where.append("(c.expires_at_game IS NOT NULL AND c.expires_at_game > NOW())")
else:
    where.append("((c.expires_at_game IS NOT NULL AND c.expires_at_game > NOW()) OR (c.expires_at_travel IS NOT NULL AND c.expires_at_travel > NOW()))")
```

### 3. 到期查询（companion.py expiry 端点）

返回两个有效期字段：
```json
{"expires_at_game": "2027-01-11 03:18:06", "expires_at_travel": ""}
```

## 前端展示

PlaymateHome.vue 显示两行独立状态卡：

```
🎮 游戏达人 ✅ 展示中（剩余 180 天）    [续期 ›]
🏛️ 旅游达人 🔄 未开通（开通后用户才能找你） [去开通 ›]
```

通过 `goRenew(isTravel)` 控制跳转：
```js
router.push(`/order/create?companion_id=${cid}&owner=1&travel=${isTravel ? 1 : 0}`)
```

## 费用方案

| 类型 | 7天 | 包月(30天) | 包年(365天) |
|------|:---:|:---------:|:----------:|
| 🎮 游戏达人 | ¥19 | ¥69 | ¥369 |
| 🏛️ 旅游达人 | ¥69 | ¥199 | ¥899 |

数据源：`site_config` 表，key 为 `game_cert_7d` / `game_cert_30d` / `game_cert_365d` / `travel_cert_*`
