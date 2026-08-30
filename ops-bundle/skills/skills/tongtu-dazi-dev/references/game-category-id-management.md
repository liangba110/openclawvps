# 游戏/同城分类 ID 管理

## ID 区间分配（2026-07-17 最新）

| 区间 | 类型 | 示例 |
|------|------|------|
| 1~7 | 🎮 游戏 | 王者荣耀、和平精英、LOL手游等 |
| 8~14 | 📍 同城（原旅游） | 景点讲解、行程规划、美食向导等 |
| 15~22 | 🎮 游戏（新增） | 金铲铲之战、英雄联盟、DNF手游等 |
| 23~32 | 📍 同城（新增） | 出行翻译、包车向导、户外跟拍等 |
| 33~40 | 📍 同城（技能兴趣类） | 台球交流、羽毛球交流、声乐交流、健身指导等 |

## 前后端过滤条件

添加新分类后，必须同步更新 **4 处**过滤逻辑：

### 1. List.vue（前端分类栏）

```javascript
// 📍 同城：g.id 8~14 + 23~40
games.value = (allGames || []).filter(g => (g.id >= 8 && g.id <= 14) || (g.id >= 23 && g.id <= 32) || (g.id >= 33 && g.id <= 40))

// 🎮 游戏：g.id 1~7 + 15~22
games.value = (allGames || []).filter(g => g.id < 8 || (g.id >= 15 && g.id <= 22))
```

### 2. Home.vue（首页搜索跳转）

```javascript
if ((game.id >= 8 && game.id <= 14) || (game.id >= 23 && game.id <= 32) || (game.id >= 33 && game.id <= 40)) query.type = 'travel'
```

### 3. DemandHall.vue（需求大厅分类）

```javascript
// game_tab 子分类
return allGames.value.filter(g => g.id < 8 || (g.id >= 15 && g.id <= 22))
// travel_tab 子分类
return allGames.value.filter(g => (g.id >= 8 && g.id <= 14) || (g.id >= 23 && g.id <= 32) || (g.id >= 33 && g.id <= 40))
```

### 4. Backend companion.py（后端列表查询）

```python
# travel 类型
where.append("(c.game_id>=8 AND c.game_id<=14) OR (c.game_id>=23 AND c.game_id<=32) OR (c.game_id>=33 AND c.game_id<=40)")
# game 类型
where.append("c.game_id<8 OR (c.game_id>=15 AND c.game_id<=22)")
```

## 规则

- 同城（原旅游）ID 区间：8~14 + 23~32 + 33~40
- 游戏 ID 区间：1~7 + 15~22
- 新增技能兴趣类（33~40）归入同城达人区
- 添加新分类后，必须同步更新上述4个文件的过滤条件
- 同时更新本文件中的 ID 区间表
