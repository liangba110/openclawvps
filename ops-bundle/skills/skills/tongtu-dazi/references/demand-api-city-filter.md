# 需求大厅城市过滤 API

## 问题

2026-07-28 用户要求在需求大厅支持「同城」筛选：点击「同城」只显示同城市的需求。

## 后端改动（demand.py）

### API: `GET /api/demand/list`

**新增参数：**
- `city` (string, optional) — 城市名称，模糊匹配 `u.city LIKE '%city%'`

**新增返回字段：**
- `city` — 需求发布者的城市（来自 `user.city`）

### 代码变更

```python
# demand.py -> demand_list()

# 1. 读取 city 参数
city = request.args.get('city', '', type=str).strip()

# 2. 加入 WHERE 条件
if city:
    where.append("u.city LIKE %s")
    params.append(f"%{city}%")

# 3. SELECT 增加 city 字段
SELECT d.*, u.nickname, u.avatar, u.score, u.city,
       g.name as game_name, g.icon as game_icon
```

## 前端改动（DemandHall.vue）

### 排序栏 HTML

```html
<div class="sort-bar">
  <span :class="{ active: sortBy === 'default' }" @click="sortBy = 'default'">综合</span>
  <span :class="{ active: sameCity }" @click="toggleSameCity">同城</span>
  <span :class="{ active: sortBy === 'score' }" @click="sortBy = 'score'">好评</span>
  <span :class="{ active: sortBy === 'orders' }" @click="sortBy = 'orders'">人气</span>
  <span class="filter-city" @click="showCityPicker = true">📍 {{ cityName }}</span>
</div>
```

### load() 函数改动

```javascript
async function load() {
  const params = {}
  if (sameCity.value && userCity.value) params.city = userCity.value
  else if (selectedCity.value) params.city = selectedCity.value
  const res = await api.get('/demand/list', { params })
}
```

### selectCity() 保存城市到 localStorage

```javascript
function selectCity(c) {
  if (c) {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    user.city = c
    localStorage.setItem('user', JSON.stringify(user))
  }
  userCity.value = c
  load()
}
```

## 关键

- 城市选择后必须**保存到 localStorage**，否则「同城」按钮无法知道用户的城市
- `toggleSameCity` 首次点击时从 localStorage 读取城市，没有则弹出城市选择器
