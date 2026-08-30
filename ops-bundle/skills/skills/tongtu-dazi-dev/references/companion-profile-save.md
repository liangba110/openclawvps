# 陪玩师资料编辑保存（PUT /api/companion/profile）

## 常见错误排查清单

### 1. 前端 404 / 500（路由路径不匹配）
```
前端: api.put('/playmate/profile', payload)  →  /api/playmate/profile
后端: @companion_bp.route('/profile', methods=['PUT'])  →  /api/companion/profile
```
**修复**：前端改为 `api.put('/companion/profile', payload)`

### 2. 后端报 "Unknown column 'nickname'"
```
UPDATE companion SET nickname=%s, ... WHERE id=%s
```
**原因**：`nickname` 在 `user` 表不在 `companion` 表。但代码本应只更新 `rank_title/intro/max_hours_per_day/tags` 到 companion 表，`nickname`/`avatar` 应更新 `user` 表。

**排查**：检查 `update_profile()` 函数中字段循环列表是否包含了 `nickname`。常见的错误：循环遍历了 `data.keys()` 而不是白名单字段。

**修复**：只处理白名单字段：
```python
for field in ['rank_title', 'intro', 'max_hours_per_day', 'tags']:
    field_key = {'intro': 'bio', 'max_hours_per_day': 'max_hours'}.get(field, field)
    val = data.get(field_key) or data.get(field)
    if val is not None:
        updates.append(f"{field}=%s")
        params.append(val)
```

### 3. 前端提交成功但后端无日志
检查 `api.put()` 的 URL 是否匹配到正确的蓝图路由。用浏览器开发者工具 Network tab 查看实际请求的完整 URL。

### 4. 调试方法

在后端添加日志：
```python
import logging
logging.warning(f"DATA: {json.dumps({k:v for k,v in data.items() if k != 'password'}, ensure_ascii=False)[:500]}")
logging.warning(f"UPDATES: updates={updates} params={params}")
```

查看日志：
```bash
sudo journalctl -u ttdazi --no-pager -n 20 | grep "DATA\|UPDATES"
```

### 5. 旧 gunicorn worker 缓存
修改代码后必须重启：
```bash
sudo systemctl restart ttdazi
sleep 5  # 等所有 worker 重启完
```
重启后即时测试，避免旧 worker 仍然响应。

## 完整保存流程

### 前端发送
```js
await api.put('/companion/profile', {
    nickname: '...',
    avatar: '...',
    bio: '...',           // → backend: intro
    rank_title: '...',    // → backend: rank_title
    max_hours: 8,         // → backend: max_hours_per_day
    tags: ['tag1', 'tag2'],
    games: [
        { game_id: 1, price_1h: 30, price_2h: 50, price_night: 80 },
        { game_id: 2, price_1h: 25, price_2h: 45, price_night: 70 },
    ],
    photos: ['/uploads/life/xxx.jpg'],
})
```

### 后端处理
```python
# 1. 检查 companion 是否存在
# 2. 更新 companion 表字段
# 3. 更新 user 表 (nickname, avatar)
# 4. 删除旧 companion_game 记录 + 批量插入新记录
# 5. 用第一个游戏更新 companion 主表
```

### 前端加载
```js
const [glist, prof] = await Promise.all([
    api.get('/game/list'),                   // 游戏列表
    api.get('/companion/my').catch(() => null),  // 当前陪玩师资料
])
```
