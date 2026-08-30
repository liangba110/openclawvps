# 价格设置约束 — ¥20~150 整数

## 规则

- 最低 **¥20/小时**
- 最高 **¥150/小时**（2小时最高¥300）
- **只能设置整数**（`step="1"`）

## 涉及页面

| 页面 | 文件 | 输入限制 | 提交校验 |
|------|------|:--------:|:--------:|
| 搭子资料编辑 | `PlaymateProfile.vue` | `min=20 max=150 step=1` | ✅ 提交时校验 |
| 搭子入驻注册 | `CompanionRegister.vue` | `min=20 max=150 step=1` | ✅ 提交时校验 |

## 实现方式

### HTML 输入限制（双层防护）

```html
<input type="number" v-model.number="..." placeholder="50"
       min="20" max="150" step="1" class="fc-input" />
```

`min`/`max`/`step` 提供浏览器原生限制，但可以被绕过，所以需要第二层 JS 校验。

### JS 提交校验

```javascript
for (const gid of selectedSubs.value) {
  const p = subPrices[gid] || 0
  if (p < 20 || p > 150) {
    safeToast('价格设置：最低¥20，最高¥150')
    return
  }
}
```

## 修改历史

- 2026-07-28: 设置价格限制，覆盖 PlaymateProfile.vue 和 CompanionRegister.vue
