# 游戏搭子 → 旅游搭子 数据库迁移参考

## 核心教训：用户说的"隐藏"=从数据库删除

当用户要求"隐藏游戏搭子"时，不是仅在 UI 层面隐藏，而是需要 **从 `game` 表中物理删除游戏分类记录**。仅在前端做 filter 不够——用户能感知到游戏分类仍然存在。

## game 表 ID 范围（删除前）

| 范围 | 类型 | 说明 |
|------|------|------|
| ID 1-7 | 电子游戏 | 王者荣耀、和平精英、LOL手游等 |
| ID 8-14 | 纯旅游分类 | 景点讲解、行程规划、美食向导等 |
| ID 15-22 | 电子游戏 | 金铲铲之战、英雄联盟、DNF手游等 |
| ID 23-40 | 体育/兴趣 | 台球、羽毛球、健身等（非旅游，也非电子游戏） |

## 删除步骤

### 第1步：检查关联表

```sql
SELECT game_id, COUNT(*) FROM companion GROUP BY game_id ORDER BY game_id;
SELECT game_id, COUNT(*) FROM companion_game GROUP BY game_id ORDER BY game_id;
SELECT game_id, COUNT(*) FROM demand_order GROUP BY game_id ORDER BY game_id;
```

### 第2步：清理 companion/companion_game

```sql
-- 清理 companion_game 关联表
DELETE FROM companion_game WHERE game_id NOT IN (SELECT id FROM game);

-- 将引用已删除游戏的搭子移到有效分类（8=景点讲解）
UPDATE companion SET game_id=8 WHERE game_id NOT IN (SELECT id FROM game);
```

### 第3步：处理 demand_order（重要）

`demand_order.game_id` 可能引用已删除的游戏 ID。**不要物理删除**这些需求记录，因为数据有业务价值。

前端通过 `validGameIds` computed 过滤无效 game_id 的需求：

```javascript
const validGameIds = computed(() => new Set(allGames.value.map(g => g.id)))
const filteredDemands = computed(() => {
  const valid = validGameIds.value
  let items = demands.value.filter(d => valid.has(d.game_id))
  // ... 后续过滤
  return items
})
```

❌ **不要用范围过滤**：`d.game_id >= 8` 会包含已删除的 ID 15-22

### 第4步：物理删除游戏分类

```sql
DELETE FROM game WHERE id IN (1,2,3,4,5,6,7,15,16,17,18,19,20,21,22);
```

## 后端同步修改

删除后，`companion.py` 中以下 SQL 不再匹配任何记录，需要同步更新：
- `companion/list` 的 `WHERE` 条件中 `((c.game_id>=8 AND c.game_id<=14) OR c.game_id>=23)` → 改为 `(c.game_id>=8 AND c.game_id<=14)`
- `companion/recommend` 和 `companion/nearby` 的 `AND (c.expires_at_game > NOW() OR c.expires_at_travel > NOW())` → 改为 `AND c.expires_at_travel > NOW()`

## 数据库 site_config 覆盖标题

`App.vue` 的 `loadSiteConfig()` 从数据库读取 `site_name` 并覆盖 `document.title`。所以改了 `index.html` 的 `<title>` 还不够，必须同步更新数据库：

```sql
UPDATE site_config SET value='同途搭子 - 旅游搭子,同城达人' WHERE `key`='site_name';
UPDATE site_config SET value='同途科技 · 旅游搭子，同城达人' WHERE `key`='site_subtitle';
```

## PWA 缓存陷阱

同途搭子是 PWA 网站，service worker 会缓存旧 JS 文件。部署后用户手机看到的可能还是旧版本，因为：
1. 浏览器从 SW 缓存读取旧的 `index.html` → 加载旧的 `index-xxx.js` → 加载旧的 `List-xxx.js`
2. 即使 Server B 上的文件已更新，用户也需要清除浏览器缓存或等 SW 自动更新

**调试方法**：在浏览器控制台检查加载的 chunk 名称：
```js
performance.getEntriesByType('resource').filter(r => r.name.includes('List-'))
```

如果 chunk 名与 Server B 上部署的最新文件不匹配，就是缓存问题。

**彻底解决**：禁用 SW（见 SKILL.md 中的 sw.js 透传模板）。

## 全栈迁移检查清单

- [ ] `game` 表：物理删除游戏分类记录
- [ ] `companion` 表：UPDATE 搭子的 game_id 到默认旅游分类
- [ ] `companion_game` 表：DELETE 引用已删除游戏的记录
- [ ] `demand_order` 表：不物理删除，前端用 validGameIds 过滤
- [ ] 前端 `List.vue`：游戏分类筛选条件 `g.id >= 8 && g.id <= 14`
- [ ] 前端 `DemandHall.vue`：subGames 和 filteredDemands 用 validGameIds
- [ ] 前端 `Home.vue`：热门分类网格用 allGames
- [ ] 后端 `companion.py`：SQL WHERE 条件改为只显示旅游
- [ ] 数据库 `site_config`：site_name、site_subtitle 更新
- [ ] PWA Service Worker：禁用或更新
