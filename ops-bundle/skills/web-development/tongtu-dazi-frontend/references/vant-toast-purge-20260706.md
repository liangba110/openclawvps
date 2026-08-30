# Vant Toast/Dialog 全量清理记录（2026-07-06）

## 扫描命令

```bash
grep -rn "from 'vant'" src/ --include="*.vue" --include="*.js"
grep -rn "showToast\|showLoadingToast\|closeToast\|showConfirmDialog\|showDialog" src/ --include="*.vue"
```

## 最终结果

```
showToast()         → 0 处
showLoadingToast()  → 0 处
closeToast()        → 0 处
showConfirmDialog() → 0 处
showDialog()        → 0 处
```

保留 `import Vant from 'vant'` 于 `main.js`（用于其他 UI 组件，非 Toast）。

## 涉及文件（26 个）

### 核心工具
| 文件 | 操作 |
|------|------|
| `utils/toast.js` | 已存在，确认修复：定时器清理+空值兜底 |
| `utils/confirm.js` | **新建** — 自定义确认弹窗（无 Vant 依赖） |
| `global.css` | 追加 `.custom-loading-overlay` + `.custom-confirm-overlay` |

### 第一批（手动）
| 文件 | 替换内容 |
|------|---------|
| `main.js` | `closeToast` → DOM querySelector 清理（含自定义弹窗类名） |
| `List.vue` | showToast/safeToast + 自定义 showLoading/hideLoading |
| `TeamBoard.vue` | showToast → safeToast |
| `Detail.vue` | showToast → safeToast + 自定义 showLoading |
| `Orders.vue` | 已用 safeToast（确认无误） |
| `CustomerService.vue` | 已用 safeToast（确认无误） |

### 第二批（19 个文件，批量 import 替换 + 逐个修复函数调用）
| 文件 | 特殊问题 |
|------|---------|
| `AdminAgreements.vue` | 无 |
| `AdminWithdrawals.vue` | 替换后 `await` 在非 `async` 函数中 → 加 async |
| `AdminDashboard.vue` | 无 |
| `AdminOrders.vue` | 无 |
| `AdminPlaymates.vue` | 无 |
| `AdminContent.vue` | 已自含 showLoading/hideLoading，delete 误用 safeToast 替代 confirm → 改 safeConfirm |
| `AdminCoupons.vue` | 已自含 showLoading/hideLoading |
| `AdminPlaymateDetail.vue` | audit 函数 safeToast(确定?) 代替 confirm → 改 safeConfirm |
| `FollowRegister.vue` | 无 |
| `Messages.vue` | 无 |
| `Coupons.vue` | showToast → safeToast |
| `EmailRegister.vue` | showLoadingToast/closeToast → 移除 |
| `Agreement.vue` | 已自含 showLoading/hideLoading |
| `MessageDetail.vue` | 无 |
| `PlaymateLogin.vue` | showLoadingToast/closeToast → 移除 |
| `PlaymateHome.vue` | showConfirmDialog → safeConfirm |
| `PlaymateOrders.vue` | showConfirmDialog → safeConfirm |
| `PlaymateIncome.vue` | showConfirmDialog → safeConfirm |
| `PlaymateProfile.vue` | showLoadingToast/closeToast → 自定义 showLoading |

### 第三批（6 个文件，扫尾）
| 文件 | 特殊问题 |
|------|---------|
| `Register.vue` | 重复 import safeToast → 去重 |
| `Home.vue` | 仍从 Vant import → 替换为自定义 showLoading；patch 过宽误改了 API endpoint → 修复 |
| `CompanionRegister.vue` | import 替换误删 `useRouter/useRoute` → 补回 |
| `EmailRegister.vue` | 已处理（与第二批重叠）|
| `Agreement.vue` | 已处理 |
| `Coupons.vue` | 已处理 |

## 构建期错误及修复

### 1. 重复 import
```
[vue/compiler-sfc] Identifier 'safeToast' has already been declared.
Register.vue 69-70: import safeToast (两次)
```
**修复**: 删掉一个。

### 2. await 在非 async 函数
```
[vue/compiler-sfc] Unexpected reserved word 'await'.
AdminWithdrawals.vue 102: await api.post(...)
```
**根因**: `showConfirmDialog({...}).then(async () => {...})` 替换为 `safeConfirm` 后，外层函数还是 `function` 不是 `async function`。
**修复**: `function audit(id, status)` → `async function audit(id, status)`

### 3. patch 过宽误改业务逻辑
Home.vue 中替换 showLoadingToast 时，old_string 包含了 API 路径：
- `/companion/recommend` → `/companion/list`（误改）
- `/companion/nearby` → `/companion/list`（误改）
- 数据解包 `r || []` → `(r && r.list) || []`（误改）

**修复**: 重新 patch 还原 API 端点。

### 4. import 批量替换误删
CompanionRegister.vue 中，`import { showConfirmDialog } from 'vant'` 替换为 `import safeToast from '@/utils/toast'\nimport safeConfirm from '@/utils/confirm'` 时，下行的 `import { useRouter, useRoute } from 'vue-router'` 被覆盖删除。

**修复**: 重新加回 `useRouter/useRoute` import。

## 关键模式总结

### safeConfirm 替换 showConfirmDialog
```js
// 旧模式（Promise chain）
showConfirmDialog({...}).then(async () => {
  await api.post(...)
  showToast('成功')
}).catch(() => {})

// 新模式（async/await）
const ok = await safeConfirm({...})
if (!ok) return
await api.post(...)
safeToast('成功')
```

### 移除 loading 遮罩
```js
// 旧
const toast = showLoadingToast('加载中...')
try { ... } finally { closeToast() }

// 新（三种方式按优先级）
// 方式1: 直接移除（后台加载，无需用户等待）
try { ... } catch(e) { console.error(e) }

// 方式2: 自定义 showLoading/hideLoading
showLoading('加载中...')
try { ... } finally { hideLoading() }

// 方式3: 按钮 loading 态
loading.value = true
try { ... } finally { loading.value = false }
```
