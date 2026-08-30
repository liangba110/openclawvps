# game_id 过滤范围：隐藏「游戏搭子」时容易遗漏的类别

## 问题

将平台从「游戏搭子+旅游搭子」改为纯「旅游搭子」时，SQL 过滤条件 `(c.game_id>=8 AND c.game_id<=14) OR c.game_id>=23` 会保留 game_id >= 23 的类别。

但实际上 game_id >= 23 包含的是**体育/兴趣交流类**（台球、羽毛球、乒乓球、声乐、绘画、舞蹈、健身指导等），在用户眼里仍然是"游戏搭子"类内容，不是旅游。

## 正确的旅游分类范围

| game_id 范围 | 类别 | 备注 |
|-------------|------|------|
| 8-14 | 纯旅游（景点讲解、行程规划、美食向导、结伴徒步、旅拍、自驾带路、景区协助） | ✅ 保留 |
| >= 23 | 体育/兴趣类（台球、羽毛球、乒乓球、声乐、绘画、舞蹈、健身等） | ❌ 排除 |

## 需要同步修改的地方

### 1. 后端 SQL（companion.py）

```python
# ❌ 错误：保留了 ≥23 的类别
where.append("((c.game_id>=8 AND c.game_id<=14) OR c.game_id>=23)")

# ✅ 正确：只保留纯旅游
where.append("(c.game_id>=8 AND c.game_id<=14)")
```

### 2. 前端分类筛选（List.vue）

```javascript
// ❌ 错误
games.value = (allGames || []).filter(g => (g.id >= 8 && g.id <= 14) || g.id >= 23)

// ✅ 正确
games.value = (allGames || []).filter(g => g.id >= 8 && g.id <= 14)
```

### 3. Home.vue 搜索逻辑（旧版） 

```javascript
// ❌ 错误
if ((game.id >= 8 && game.id <= 14) || game.id >= 23) query.type = 'travel'

// ✅ 正确（但整段移除更干净）
```

## 验证方法

部署后用浏览器查看 List 页面的 filter-bar，确认只有旅游分类：

```text
全部 | 🏛️ 景点讲解 | 🗺️ 行程规划 | 🍜 美食向导 | 🥾 结伴徒步 | 📷 旅拍 | 🚗 自驾带路 | 🎫 景区协助
```

不应出现：台球、羽毛球、乒乓球、声乐、绘画、舞蹈、健身等。
