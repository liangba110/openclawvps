# 需求大厅双分类展示

## 结构
需求大厅顶部显示两个分类卡片：**游戏达人** 和 **同城达人**，点击后进入对应子分类Tab。

```
┌──────────────────┐
│  🎮 游戏达人     │  ← 点击进入游戏子分类
│  📍 同城达人     │  ← 点击进入同城子分类
└──────────────────┘

点击后显示子Tab:
  ‹ 全部  王者荣耀  和平精英  ...
```

## 状态变量
```js
const currentTab = ref('all')       // 'all' | 'game_tab' | 'travel_tab'
const currentGameId = ref(0)        // 选中的具体游戏ID，0=全部
const allGames = ref([])            // 从API获取的全部游戏列表
```

## 过滤逻辑

### subGames computed（子分类列表）
```js
const subGames = computed(() => {
  if (currentTab.value === 'game_tab') {
    return allGames.value.filter(g => g.id < 8 || (g.id >= 15 && g.id <= 22))
  }
  if (currentTab.value === 'travel_tab') {
    return allGames.value.filter(g => (g.id >= 8 && g.id <= 14) || g.id >= 23)
  }
  return []
})
```

### filteredDemands computed（需求列表过滤）
```js
const filteredDemands = computed(() => {
  if (currentTab.value === 'all') return demands.value
  if (currentTab.value === 'game_tab') {
    return demands.value.filter(d => d.game_id < 8 || (d.game_id >= 15 && d.game_id <= 22))
  }
  if (currentTab.value === 'travel_tab') {
    return demands.value.filter(d => (d.game_id >= 8 && d.game_id <= 14) || d.game_id >= 23)
  }
  if (currentGameId.value > 0) {
    return demands.value.filter(d => d.game_id === currentGameId.value)
  }
  return demands.value
})
```

## 注意事项
- 游戏/同城分类 ID 边界修改时，必须同步更新 DemandHall.vue 的这两个 computed
- 不要把所有游戏加到顶部 `tabs` 中（已注释掉），改为用子Tab展示
- `onMounted` 中 `allGames.value = games` 保存全量数据供 `subGames` 使用
