# Vue 3 模板全局变量白名单

## 问题：模板中使用 `sessionStorage` / `window` 报 `undefined`

Vue 3 SFC 模板编译后，模板表达式中的变量名在渲染时按以下顺序查找：

1. 组件 `setup()` 返回的绑定（refs, reactive, 函数）
2. 组件 props
3. 组件 emits
4. App 级别的 `config.globalProperties`
5. **内置全局白名单**

## Vue 3 内置模板全局白名单

以下变量可直接在模板中使用（Vue 3.3+）：

```
Infinity, undefined, NaN, isFinite, isNaN, parseFloat, parseInt, 
decodeURI, decodeURIComponent, encodeURI, encodeURIComponent, 
Math, Date, Array, Object, Boolean, String, RegExp, Map, Set, 
JSON, Intl, BigInt, console, clearInterval, clearTimeout, 
setInterval, setTimeout
```

**不在白名单中**（模板中直接使用会报 `undefined`）：

| 变量 | 替代方案 |
|------|---------|
| `sessionStorage` | 在 `<script setup>` 中定义 `const adminPath = sessionStorage.getItem(...)`，模板用 `adminPath` |
| `localStorage` | 同上，在 script 中读取 |
| `window` | 同上 |
| `location` | 使用 Vue Router 的 `useRoute()` / `useRouter()` |
| `navigator` | 在 script 中读取 |
| `document` | 在 script 中操作，或用 `ref` 模板引用 |

## 正确做法

```html
<template>
  <!-- ❌ 错误：模板中直接使用 -->
  <div @click="$router.push('/' + sessionStorage.getItem('path'))">

  <!-- ✅ 正确：script 中读取，模板中引用变量 -->
  <div @click="$router.push('/' + adminPath)">
</template>

<script setup>
const adminPath = sessionStorage.getItem('admin_route_path') || 'op-ztHWaT-0706'
</script>
```

## 注意事项

1. **变量在组件创建时读取**：`const adminPath = ...` 在 `setup()` 阶段执行一次。如果值后续会变化（如管理后台路径轮换），需要组件销毁重建或刷新页面。
2. **计算属性中读取**：如需响应式读取 `sessionStorage`，用 `computed` 或 `watch`。
3. **`$router` 和 `$route`**：是组件实例属性（通过 `app.config.globalProperties` 注入），可在模板中直接使用。
4. **测试方法**：在浏览器 DevTools 中查看 Vue 组件，检查是否有 `vue` 相关错误。
