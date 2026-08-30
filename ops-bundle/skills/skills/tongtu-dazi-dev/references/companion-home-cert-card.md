# 搭子认证状态与我的搭子页面

## 认证状态卡片（PlaymateHome.vue）

搭子端的首页顶部显示认证状态卡片，根据 `companion.expires_at` 计算状态：

| 状态 | CSS 类名 | 颜色 | 条件 |
|------|---------|------|------|
| ✅ 认证有效 | `active` | 绿色 | expires_at > 当前时间，且剩余 > 7天 |
| ⚠️ 即将到期 | `expiring` | 黄色 | expires_at > 当前时间，且剩余 ≤ 7天 |
| ❌ 已过期 | `expired` | 红色 | expires_at < 当前时间 |
| 🔄 未激活 | `pending` | 默认 | expires_at 为空/null |

### 计算逻辑

```js
const certClass = computed(() => {
  const c = companionInfo.value
  if (!c) return 'pending'
  if (!c.expires_at) return 'inactive'
  const now = new Date()
  const exp = new Date(c.expires_at)
  if (exp < now) return 'expired'
  const days = Math.ceil((exp - now) / (1000*60*60*24))
  if (days <= 7) return 'expiring'
  return 'active'
})
```

### 跳转续费

点击认证状态卡跳转到续费页面：
```js
router.push(`/order/create?companion_id=${cid}&owner=1&travel=${isTravel}`)
```

## 在线状态切换

`PlaymateHome.vue` 有三个在线状态选项（在线/忙碌/下线）。

**注意**：状态切换的 CSS 和 JS 功能已定义但之前模板中**未渲染**——`<div class="status-bar">` 在旧版模板中缺失。新版已补上。

## 加载数据

```js
async function loadStats() {
  const [incomeRes, ordersRes, companionRes] = await Promise.all([
    api.get('/companion/my/income'),
    api.get('/companion/my/orders'),
    api.get('/companion/my'),
  ])
  // 设置 stats, pendingOrders, companionInfo, companionStatus
}
```

## 通用搭子命名

平台统一使用「搭子」而非「游戏搭子」：
- 页面标题：`{{ user.nickname || '我的搭子' }}`
- 认证描述：不硬编码「游戏」，从 `companion.game_name` 动态获取
- 旅游搭子和游戏搭子共用同一套 UI（通过 `game_id >= 8` 区分）
