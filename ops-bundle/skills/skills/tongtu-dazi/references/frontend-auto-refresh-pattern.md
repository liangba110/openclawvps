# 前端自动刷新模式

陪玩师端页面使用 `setInterval` + `onUnmounted` 自动刷新数据，确保新订单/收入变化实时显示。

## 标准模式

```javascript
import { ref, onMounted, onUnmounted } from 'vue'

const data = ref([])
let refreshTimer = null

async function loadData() {
  try {
    const res = await api.get('/some/api')
    data.value = res || []
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadData()
  // 每N秒自动刷新
  refreshTimer = setInterval(loadData, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
```

## 各页面刷新频率

| 页面 | 频率 | 原因 |
|------|------|------|
| `PlaymateHome.vue` | 30秒 | 新待接单+收入统计 |
| `PlaymateIncome.vue` | 30秒 | 提现记录+可提现金额 |
| `PlaymateOrders.vue` | 15秒 | 新待接单需快速响应 |

## 注意事项

1. **必须清除定时器** — `onUnmounted` 中必须 `clearInterval`，否则页面切换后定时器继续运行，造成冗余请求和内存泄漏
2. **catch 静默** — 自动刷新失败用 `console.error` 而非 `safeToast`，避免频繁弹窗打扰用户
3. **不干扰用户操作** — 用户手动点击「接单」等操作后，自动触发 `loadData()` 立即刷新，不等定时器
4. **避免重复请求** — `loadData()` 内部不设 `loading` 状态（静默刷新），不影响当前页面交互
