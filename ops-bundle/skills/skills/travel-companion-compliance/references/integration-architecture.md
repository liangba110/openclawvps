# 旅游搭子与游戏搭子集成架构

## 数据层约定

| 类型 | game_id 范围 | 数据表 |
|------|-------------|--------|
| 🎮 游戏搭子 | `game_id < 8` | `companion` + `user` |
| 🏛️ 旅游搭子 | `game_id >= 8` | `companion` + `user` |

两套共用同一张 `companion` 表，通过 `game_id` 区分。

## 后端筛选

`/api/companion/list` 接受 `type` 参数：

```python
if service_type == 'travel':
    where.append("c.game_id>=8")
elif service_type == 'game':
    where.append("c.game_id<8")
```

## 前端列表页

`/list?type=travel` → 只加载旅游分类（game_id ≥ 8）
`/list?type=game` → 只加载游戏分类（game_id < 8）

`List.vue` 根据 `route.query.type` 判断：
- `isTravel = computed(() => route.query.type === 'travel')`
- 加载分类时根据 `isTravel` 过滤
- 旅行搭子头部用绿色渐变（区别于游戏搭子的紫色渐变）

## 首页入口

Home.vue 入口栏增加「旅游搭子」按钮，点击跳转到 `/list?type=travel`。

## 敏感词差异化

- `word_type='travel'` — 旅游搭子专用敏感词
- `word_type='block'` / `'warn'` / `'profile_block'` — 全平台通用

## 分支管理

- 主分支 `master`：游戏搭子
- 新分支 `feature/travel-companion`：旅游搭子（独立开发，不合并）
