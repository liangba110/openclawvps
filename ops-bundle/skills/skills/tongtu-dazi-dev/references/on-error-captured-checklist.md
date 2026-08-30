# "页面加载出错，建议刷新" 完整诊断流程

## 来源
`App.vue` 第26-30行:
```js
onErrorCaptured((err, instance, info) => {
  console.error('子组件渲染错误:', err)
  console.error('错误详情:', {
    message: err?.message || String(err),
    component: instance?.$?.type?.__name || '未知组件',
    info: info
  })
  safeToast('页面加载出错，建议刷新')
  return false
})
```

任何子组件的渲染期错误都会触发此 toast。它是全局捕获，不指向具体组件。

## 诊断步骤

### Step 1: 定位触发页面
- 用户描述出现在哪个页面
- 如果多个页面都出现，优先查首次访问的页面

### Step 2: 检查 Vue 响应式陷阱
在对应组件的 `<script setup>` 中查找：
- `function user() { return ... }` → 模板访问 `user.nickname` 实际是读函数对象属性，永远 `undefined`
- **修复**: 改为 `const user = computed(() => ...)` 或 `const user = ref(...)`

### Step 3: 检查不安全的模板表达式

按概率排序：

| 模式 | 风险 | 修复 |
|------|------|------|
| `'★'.repeat(score)` | **MOST COMMON** — score 为 undefined/null → NaN → RangeError | `Number(score)||0` 或模板中 `(rv.rating||0)` |
| `{{ x.toFixed(n) }}` | x 是 string/null | `typeof x==='number'?x.toFixed(1):(x||'5.0')` |
| `{{ x.startsWith('...') }}` | x 是 null/undefined | `x && typeof x==='string' && x.startsWith(...)` |
| `v-for="x in item.tags"` | tags 是 undefined/non-array | `v-for="x in (item.tags||[])"` |
| `{{ a.b.c }}` | API 返回扁平结构，c 不存在 | curl API 确认结构，对齐模板 |
| `{{ x.slice(0,10) }}` | x 是 null | `(x||'').slice(0,10)` |
| `{{ x.charAt(0) }}` | x 是 undefined | `(x||'').charAt(0)` |

### Step 4: 检查 API 响应结构
```bash
TOKEN=$(curl -s .../login -d '{"phone":"...","password":"..."}' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['token'])")
curl -s .../api/xxx -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
对比模板中的字段路径与 API 实际返回的 JSON 结构。

### Step 5: 检查 v-for 安全性
```js
// ❌ 可能赋值非数组
list.value = res || []

// ✅ 安全
list.value = Array.isArray(res) ? res : []
```

## 本项目历史案例

| 页面 | 根因 | 修复 |
|------|------|------|
| 列表页 | `renderStars(score)` → `Math.floor(undefined)` → `repeat(NaN)` RangeError | `Number(score)||0` |
| 详情页 | `'★'.repeat(rv.rating)` — rating undefined | `(rv.rating||0)` + `Math.max(0,5-rating)` |
| 设置页 | `user()` 普通函数，模板 `user.id` 为 undefined | → `computed()` |
| 订单页 | `order.companion.nickname`，API 返回 flat `nickname` | → `order.nickname` |
| 收藏页 | `item.rating.toFixed(1)`，rating 为 string/null | → typeof guard |
| 陪玩师注册 | `url.startsWith('http')`，url 为 null | → 先判类型 |
