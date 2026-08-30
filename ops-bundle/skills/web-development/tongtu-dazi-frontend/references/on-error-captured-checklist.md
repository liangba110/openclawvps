# "页面加载出错，建议刷新" 完整排查清单

## 消息来源
`App.vue` line 26-30: `onErrorCaptured` 捕获任何子组件渲染错误

## 排查步骤（按频率排序）

### 1. String.repeat(NaN) RangeError (最高频 ⭐⭐⭐)
**搜索**: `'★'.repeat(` `'⭐'.repeat(` `'☆'.repeat(`
**原因**: `Math.floor(undefined)` → `NaN` → `String.repeat(NaN)` → RangeError
**修复**: `Number(score) || 0` / `(rating || 0)` / `Math.max(0, 5 - (rating || 0))`

### 2. 模板字段名与API结构不匹配
**搜索**: `order.companion.xxx` `item.xxx.yyy` 等嵌套访问
**排查**: curl API → 对比模板字段路径 → 对齐
**修复**: 扁平化访问或加 `?` 可选链

### 3. 普通函数当 computed 用
**搜索**: `function user()` 但模板用 `user.nickname`
**原因**: 函数上没有 `.nickname` 属性 → `undefined` → 连锁渲染错误
**修复**: `const user = computed(() => ...)` 

### 4. Number方法在非number上
**搜索**: `.toFixed(` `.toPrecision(`
**修复**: `typeof x === 'number' ? x.toFixed(1) : fallback`

### 5. String方法在null/undefined上
**搜索**: `.startsWith(` `.charAt(` `.slice(` 在模板中
**修复**: `(str || '').slice(...)` 或 `typeof str === 'string' && str.startsWith(...)`

### 6. v-for 无数组守卫
**搜索**: `v-for="x in item.tags"` 
**修复**: `v-for="x in (item.tags || [])"` 或 `Array.isArray(res) ? res : []`

### 7. JSON.parse 无 try/catch
**搜索**: `JSON.parse(localStorage.getItem(` 
**修复**: `try { ... } catch { return {} }`

### 8. 增强日志定位
在 `App.vue` 的 `onErrorCaptured` 中加:
```js
onErrorCaptured((err, instance, info) => {
  console.error('错误详情:', {
    message: err?.message || String(err),
    component: instance?.$?.type?.__name || '未知组件',
    info
  })
  safeToast('页面加载出错，建议刷新')
  return false
})
```
