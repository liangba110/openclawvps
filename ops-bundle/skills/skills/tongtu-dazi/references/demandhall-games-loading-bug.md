# 需求大厅游戏分类加载Bug

## 问题

点击需求大厅的"同城达人"卡片后，子分类（sub-tabs）不显示。此外，"全部"和"同城达人"标签下都混入了已删除游戏的需求。

## 根因

### Bug 1: allGames 条件加载

`DemandHall.vue` 的 `load()` 函数中，游戏分类列表（`allGames`）只在需求列表为空时才加载：

```javascript
// ❌ 错误写法
async function load() {
  const res = await api.get('/demand/list')
  demands.value = res.list || []
  if (!demands.value.length) {  // ← 只有没需求时才加载分类
    const gamesRes = await api.get('/game/list')
    allGames.value = gamesRes || []
  }
}
```

当数据库中有需求数据时，`demands.value` 不为空，`allGames` 永远不会被赋值，导致 `subGames` 计算属性返回空数组。

### Bug 2: 过滤条件不够精确

使用 `d.game_id >= 8` 作为过滤条件，但已从 game 表删除的 ID 15-22 也满足该条件，导致已删除游戏的需求仍然显示（分类显示为"未指定"）。

## 修复

### Fix 1: 始终加载游戏分类

```javascript
// ✅ 正确写法
async function load() {
  const res = await api.get('/demand/list')
  demands.value = res.list || []
  // 始终加载分类，不依赖 if 条件
  const gamesRes = await api.get('/game/list')
  allGames.value = gamesRes || []
}
```

### Fix 2: 用 validGameIds 集合作过滤

不要用区间范围过滤，而是基于实际存在的游戏 ID 集合：

```javascript
const validGameIds = computed(() => new Set(allGames.value.map(g => g.id)))

const filteredDemands = computed(() => {
  const valid = validGameIds.value
  let items = demands.value.filter(d => valid.has(d.game_id))
  if (currentTab.value === 'all') return items
  if (currentTab.value === 'travel_tab') return items
  if (currentGameId.value > 0) {
    return items.filter(d => d.game_id === currentGameId.value)
  }
  return items
})
```

## 同类风险

检查所有组件中是否有类似模式：某个数据加载依赖于另一个数据的条件判断。应优先并行加载独立数据。以及所有 `game_id` 过滤条件应基于 `allGames` 而不是硬编码的范围。
