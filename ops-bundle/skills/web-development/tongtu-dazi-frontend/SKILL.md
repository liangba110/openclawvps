---
name: tongtu-dazi-frontend
description: >
  同途搭子游戏陪玩平台前端修复模式。Vue3+Vant+Vite+Vue Router项目，
  覆盖Toast遮罩残留、computed响应式、模板渲染崩溃、API映射等高频bug的修复模式。
  当需要修复该项目的Vant弹窗、加载遮罩、渲染错误、后端500等问题时触发。
---

# 同途搭子 前端修复模式

## 模式57: API 响应数据结构兼容（高频！）

**场景**: Detail.vue / CreateOrder.vue 中调用 `api.get('/companion/detail')` 后访问 `.id` 永远为 undefined，触发"不存在"错误。

**根因**: 后端响应嵌套在 `data.info` 而非直接返回：
```json
{"code":0,"data":{"info":{"id":23,"nickname":"小甜心",...}}}
```
拦截器返回 `res.data.data` → `{"info":{...}}`，所以 `r.id` 是 undefined。

**通用修复**: 用 `?.info || r` 兼容两种结构
```javascript
// ✅ 兼容 info 嵌套和扁平两种结构
const r = await api.get(`/companion/detail?id=${id}`)
const d = r?.info || r
if (!d || !d.id) { safeToast('不存在'); return }
info.value = d

// ⚠️ 不要只检查 r.id（永远为 undefined）
```

**检查点**: 所有调用 `/companion/detail` 的地方必须用此模式。当前影响 Detail.vue、CreateOrder.vue。

## 模式58: 底部操作栏固定定位（Vue scoped CSS + 移动端兼容）

**场景**: 详情页底部「聊一聊」「立即对接」按钮条不显示。

**根因**: 多层问题叠加：
1. Vue scoped CSS 对模板根元素的兄弟元素不生效 → 底部栏必须在同一个根元素内
2. 微信内置浏览器对 `position: fixed` 渲染异常 → 加 `-webkit-transform: translateZ(0)`
3. 应用底部导航栏（App.vue 的 `.bottom-nav`，height: 64px）与详情页底部栏重叠 → `bottom: 64px`

**修复模板**:
```vue
<template>
  <div class="detail-page">     ← 唯一根元素
    <!-- 页面内容 -->
    <div class="bottom-actions" v-if="info">   ← 底部栏在根元素内
      <div class="btn-chat" @click="goChat">💬 聊一聊</div>
      <button class="btn-match" @click="goOrder">立即对接</button>
    </div>
  </div>
</template>

<style scoped>
.detail-page { min-height: 100vh; background: #f5f6fa; position: relative; }
.bottom-actions {
  position: fixed; bottom: 64px;   /* 在 app 导航栏(64px)上方 */
  left: 0; right: 0; z-index: 99;
  display: flex; align-items: center; gap: 10px;
  padding: 10px 16px;
  background: #fff; border-top: 1px solid #eee;
  -webkit-transform: translateZ(0);  /* 微信浏览器兼容 */
}
</style>
```

**检查清单**:
- [ ] 底部栏是根元素的子元素（不是兄弟元素）
- [ ] `position: fixed` 用 scoped CSS
- [ ] `z-index` 高于页面内容
- [ ] `bottom` 值 + 应用导航栏高度 ≤ 100vh
- [ ] `-webkit-transform: translateZ(0)`（微信兼容）

## 项目信息
- 前端: Vue3 + Vant4 + Vite + Vue Router (Hash模式)
- 后端: Flask + PyMySQL + gunicorn
- 服务器: A(42.193.113.230) DB+API, B(82.157.202.24) Nginx公网入口
- 部署: `/opt/ttdazi/deploy.sh` (build + sync)

## 用户偏好
- 中文交流，简洁务实
- **执行命令模式：** 用户给 5-10 字指令，直接执行不废话。改完 → 构建 → 部署 → 一句话汇报。
- 所有错误/成功提示必须有意义的文字，拒绝空白toast
- 优先去Vant化，自定义弹窗替代Vant弹窗组件

---

## 模式S: 系统性 Vant 弹窗替换（大规模重构）

**场景**: 批量移除项目中所有 Vant Toast/Confirm/Dialog 调用，替换为自定义 safeToast/safeConfirm

**全量扫描**:
```bash
grep -rn "from 'vant'" src/ --include="*.vue" --include="*.js"
grep -rn "showToast\|showLoadingToast\|closeToast\|showConfirmDialog\|showDialog" src/ --include="*.vue"
```

### 替换清单

| Vant 函数 | 替代 | 说明 |
|-----------|------|------|
| `import { showToast, ... } from 'vant'` | `import safeToast from '@/utils/toast'` | 替换 import |
| `import { showConfirmDialog } from 'vant'` | `import safeConfirm from '@/utils/confirm'` | 替换 import |
| `showToast('xxx')` | `safeToast('xxx')` | 直接替换 |
| `showToast(e.message \|\| 'xxx')` | `safeToast(e.message \|\| 'xxx')` | 修复空catch吞错 |
| `showLoadingToast('xxx')` | `showLoading('xxx')` | 自定义函数 |
| `closeToast()` | `hideLoading()` | 配套清理 |
| `showConfirmDialog({...}).then(()=>{}).catch(()=>{})` | `const ok = await safeConfirm({...}); if (!ok) return` | Promise → async/await |

### ⚠️ 陷阱1: 多代理并行编辑冲突

多 agent 并行修改同一批文件时，工具会报 `was modified by sibling subagent` 警告。

**表现**：文件已部分修改但未同步——import 已被替换但调用未改，或出现重复 import。

**处理流程**：
1. 先 `re-read` 文件（用 read_file），确认当前实际内容
2. 如已有 `safeToast` import → 移除重复的（保留1个）→ 继续替换剩下的 `showToast()` 等调用
3. 作业结束后 `grep -rn "from 'vant'" src/views/` 和 `grep "import.*from.*vant"` 确认无残留

### ⚠️ 陷阱2: replace_all 是参数不是模式

`patch` 工具参数：
- `mode='replace'`（默认）
- `replace_all=true|false`（**布尔参数**，不是 mode 值）

```js
// ✅ 正确
patch(mode='replace', path=..., old_string='showToast(', new_string='safeToast(', replace_all=true)

// ❌ 错误
patch(mode='replace_all', path=..., ...)  // Unknown mode: replace_all
```
```js
let loadingEl = null
function showLoading(msg) {
  loadingEl = document.createElement('div')
  loadingEl.className = 'custom-loading-overlay'
  loadingEl.innerHTML = '<div class="custom-loading-box"><div class="custom-loading-spinner"></div><div class="custom-loading-text">' + (msg || '加载中...') + '</div></div>'
  document.body.appendChild(loadingEl)
}
function hideLoading() {
  if (loadingEl && document.body.contains(loadingEl)) {
    document.body.removeChild(loadingEl)
    loadingEl = null
  }
}
```
CSS 已预置在 `src/assets/global.css` 中（`.custom-loading-overlay`, `.custom-confirm-overlay`）。

### 已移除Vant Toast的文件清单（完整扫描）
- `utils/toast.js` — 核心工具（同步DOM+定时器清理+空文本兜底）
- `utils/confirm.js` — 自定义确认弹窗（Promise，无Vant依赖）
- `main.js` — 路由清理不用 Vant closeToast

**第一批**: `List.vue`, `TeamBoard.vue`, `Detail.vue`, `Orders.vue`, `CustomerService.vue`

**第二批 (2026-07-06 批量 19 文件)**:
- Admin: `AdminAgreements`, `AdminWithdrawals`, `AdminDashboard`, `AdminOrders`, `AdminPlaymates`, `AdminContent`, `AdminCoupons`, `AdminPlaymateDetail`
- Views: `FollowRegister`, `Messages`, `Coupons`, `EmailRegister`, `Agreement`, `MessageDetail`
- Playmate: `PlaymateLogin`, `PlaymateHome`, `PlaymateOrders`, `PlaymateIncome`, `PlaymateProfile`

### 已全部修复（2026-07-06 第三轮扫尾）
`Register.vue`, `Home.vue`, `CompanionRegister.vue`, `EmailRegister.vue`, `Agreement.vue`, `Coupons.vue` — 全部 Vant Toast/Dialog 调用已替换为 safeToast/safeConfirm。

当前全量扫描结果：
- `showToast()` — 0 处残留
- `showLoadingToast()` — 0 处残留  
- `closeToast()` — 0 处残留
- `showConfirmDialog()` — 0 处残留
- `showDialog()` — 0 处残留

### ⚠️ 陷阱4: `showConfirmDialog().then(async) → safeConfirm()` 需加 async

`showConfirmDialog` 返回 Promise，可以 `.then(async () => {...})` 中直接用 `await`。
但 `safeConfirm` 返回 Promise\<boolean\>，需要外层函数是 `async`：

```js
// ❌ 错误 — await 在非 async 函数中
function audit(id, status) {
  const ok = await safeConfirm({...})  // SyntaxError: await is only valid in async function
}

// ✅ 正确 — 加 async
async function audit(id, status) {
  const ok = await safeConfirm({...})
  if (!ok) return
  await api.post(...)
  safeToast('操作成功')
}
```

**检查点**: 所有 `showConfirmDialog({...}).then(() => {...}).catch(() => {})` 被替换后，检查原函数声明是否补了 `async`。

### ⚠️ 陷阱5: import 批量替换误删无关 import

批量替换 `from 'vant'` import 时，如果用整行替换模式，可能误删同一文件的其他 import：

```js
// 原始
import { showConfirmDialog } from 'vant'
import { useRouter, useRoute } from 'vue-router'

// ❌ 错误替换 — useRouter/useRoute 被整行覆盖掉
import safeToast from '@/utils/toast'  // useRouter, useRoute 丢失！

// ✅ 正确
import { useRouter, useRoute } from 'vue-router'
import safeToast from '@/utils/toast'
import safeConfirm from '@/utils/confirm'
```

**规则**: 永远不要用 `import { X } from 'vant'` 整行替换成 `import safeToast`。会丢失同文件其他 import。确认所有 import 行是独立的再用 patch。

### ⚠️ 陷阱6: patch old_string 过宽误改业务逻辑

当 `patch()` 的 `old_string` 包含了 showLoadingToast/closeToast 之外的上下文，可能意外修改 API endpoint 等业务代码：

```js
// 原始
const toast = showLoadingToast('加载中...')
try {
  const r = await api.get('/companion/recommend')
  recommends.value = r || []

// ❌ 如果 old_string 从 `const toast =` 到 `closeToast()`，
// 中间包含了 api.get 路径，也被匹配替换掉
```

**规则**: `old_string` 只包含要替换的最小上下文。showLoadingToast 改为 showLoading（仅改函数名），closeToast 改为 hideLoading（仅改位置）。不要将整个 try/catch 块作为替换范围。

### ⚠️ 陷阱7: 全局替换后检查重复 import

批量替换后同一个文件可能出现两次 `import safeToast`：

```js
import safeToast from '@/utils/toast'  // 第一次替换
import safeToast from '@/utils/toast'  // 第二次替换（重复！）
```

`npm run build` 时报 `[vue/compiler-sfc] Identifier 'safeToast' has already been declared`。

**检查方式**:
```bash
grep -c "import safeToast" src/views/*.vue | grep -v ":1$"
# 输出 ":2" 或 ":3" 的就是重复的文件
```

> 本次全量清理详细记录见 `references/vant-toast-purge-20260706.md` — 涵盖 26 个文件的逐个修复记录、构建期 4 个错误的根因和修复、替换模式详解。

---

## 模式1: Vant加载遮罩残留（最高频）

**现象**: 页面背景发暗，半透明遮罩不消失，"页面加载出错，建议刷新"

**根因**: `showLoadingToast()` 的 DOM 在 `closeToast()` 后有退出动画，
异步未完成时自定义 Toast 已渲染，两层叠加→遮罩残留。

**修复**（优先级从高到低）:

### 方案A: 砍掉Vant loading（推荐）
```js
// ❌ 旧
import { showLoadingToast, closeToast } from 'vant'
showLoadingToast('登录中...')
// ... closeToast()

// ✅ 新 - 按钮loading态
loading.value = true  // 按钮文字: loading ? '登录中...' : '登录'
// ... finally { loading.value = false }
```

### 方案B: 自定义v-if遮罩
```html
<div v-if="overlay" class="modal-overlay" @click.stop>
  <div class="overlay-spinner"></div>
  <div>{{ overlayText }}</div>
</div>
```
```js
const overlay = ref(false)
// try { ... } finally { overlay.value = false }
// onUnmounted(() => { overlay.value = false })
```

### 方案C: 实例.close() + requestAnimationFrame（备选）
```js
const t = showLoadingToast('...')
// ...
t.close()
await new Promise(r => requestAnimationFrame(r))
safeToast('操作完成')
```

**关键**: 无论哪个方案，`finally` 块必须关闭遮罩，`onUnmounted` 兜底。

---

## 模式2: Vue computed 读 localStorage 不刷新

**现象**: 更新localStorage后UI不刷新

**根因**: `computed(() => JSON.parse(localStorage.getItem(...)))` — localStorage不是响应式数据源，Vue无法追踪变化。

**修复**: 加版本号ref作cache-buster
```js
const userVer = ref(0)
const user = computed(() => {
  void userVer.value  // 依赖版本号
  return JSON.parse(localStorage.getItem('user') || 'null') || {}
})
function updateLocal(obj) {
  // ... localStorage.setItem(...)
  userVer.value++  // 触发computed重算
}
```

---

## 模式3: String.repeat() RangeError

**现象**: 模板渲染崩溃→`onErrorCaptured` 触发"页面加载出错"

**根因**: `'★'.repeat(score)` — score为undefined/null时 `repeat(NaN)` 抛RangeError

**高危文件**: List.vue (renderStars), Detail.vue (评论星星), Reviews.vue

**修复**:
```js
// ❌ 旧
function renderStars(score) {
  return '★'.repeat(Math.floor(score))
}

// ✅ 新
function renderStars(score) {
  const s = Number(score) || 0
  return '★'.repeat(Math.floor(s))
}
```
```html
<!-- 模板中 -->
{{ '★'.repeat(rv.rating || 0) }}
```

---

## 模式4: 模板字段名与API返回不匹配

**现象**: `v-if="order.companion"` 永远为false，数据不显示或渲染错误

**根因**: API返回扁平结构 `{nickname, avatar}`，模板用 `order.companion.nickname`

**排查**: 
1. curl API看实际返回JSON结构
2. 对比模板中的字段路径
3. 用 `??` 和 `||` 兜底

---

## 模式5: 后端字段类型不匹配

**现象**: API 500 Internal Server Error

**排查流程**:
1. `sudo journalctl -u ttdazi --no-pager -n 30` 看日志
2. 常见: `pymysql.err.DataError: (1366, "Incorrect integer value")`
3. 检查 `DESCRIBE table` 的列类型
4. 后端做映射: 前端字符串↔DB整数

**例**: gender列是TINYINT(0/1/2)，前端传'male'/'female'/'secret'
```python
GENDER_MAP = {'male': 1, 'female': 2, 'secret': 0}
if field == 'gender':
    val = GENDER_MAP.get(data['gender'])
```

---

## 模式6: 双重 conn.close() 崩溃

**现象**: `pymysql.err.Error: Already closed`

**根因**: 函数中两个 `try/finally` 块都关了同一个连接

**修复**: 第二个数据库操作块用 `db = get_connection()` 获取新连接

---

## 模式7: FormData 上传失败

**现象**: 文件上传接口返回错误

**排查**:
1. axios默认 `Content-Type: application/json` 会覆盖 FormData 的 multipart
2. 请求拦截器需检测 FormData 并删除 Content-Type
```js
api.interceptors.request.use(config => {
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  } else {
    config.headers['Content-Type'] = 'application/json'
  }
  return config
})
```

---

---

## 模式8: 陪玩师照片上传403 → 先注册后上传

**现象**: 选生活照时立即调 `/companion/photos/upload` 返回403

**根因**: 照片上传接口要求陪玩师记录已存在，但用户在Step3选照片时还没提交注册

**修复**: 
1. `addPhoto()` 只压缩+本地预览，不上传（保存 `file` 对象到 `lifePhotos`）
2. `submitApply()`: 先 POST `/companion/register` → 成功后 `for` 循环逐个上传
3. `removePhoto()` 加 `URL.revokeObjectURL(p.localUrl)` 释放内存

```js
// addPhoto - 只存文件，不上传
lifePhotos.value.push({
  file: compressed,    // 待注册后上传
  localUrl: URL.createObjectURL(compressed)  // 预览
})

// submitApply - 先注册，后逐张上传
await api.post('/companion/register', { game_ids, intro, price, max_hours })
for (const p of lifePhotos.value) {
  if (!p.file) continue
  const fd = new FormData(); fd.append('photo', await compressImage(p.file))
  await api.post('/companion/photos/upload', fd)
}
```

---

## 模式9: 管理端审核字段4重不匹配

**现象**: 待审核列表不显示、点通过提示"已拒绝"、审核后状态不更新

**根因**: 前后端 `audit_status` 类型/方法/字段名/值全不匹配
- `audit_status`: DB整数0/1/2 ↔ 前端期望字符串pending/approved/rejected
- 方法: 前端POST ↔ 后端PUT
- 字段: 前端`{status:'approved'}` ↔ 后端`{action:'approve'}`  
- is_companion更新: 判断`action=='approve'`而非`status==1`

**修复** (后端):
```python
# API返回时转换
STATUS_MAP = {0: 'pending', 1: 'approved', 2: 'rejected'}
item['audit_status'] = STATUS_MAP.get(item['audit_status'], 'pending')

# 审核接口兼容
action = data.get('action') or data.get('status') or ''
if action in ('approve', 'approved'): status = 1
elif action in ('reject', 'rejected'): status = 2

# is_companion用status判断
if status == 1:
    cur.execute("UPDATE user u JOIN companion c ... SET u.is_companion=1")
msg = '审核通过' if status == 1 else '已拒绝'
```

---

## 模式10: 陪玩师多游戏认证（DB关联表）

**场景**: 陪玩师需要认证多个游戏类型（最多5个）

**步骤**:
1. 新建 `companion_game` 表: `(id, companion_id, game_id, UNIQUE(companion_id,game_id))`
2. 迁移现有 `companion.game_id` → `INSERT IGNORE INTO companion_game`
3. 后端 accept `game_ids` 数组，兼容旧 `game_id` 单值
4. 前端多选 + toggle + `✓` 标记 + `0/5` 计数
5. detail返回 `games: [{id,name,icon}]`

---

## 模式11: 生活照相册不显示

**现象**: 陪玩详情页没有生活照模块

**根因**: 后端 `detail` API 返回了 `life_photos` 数组，但 `Detail.vue` 模板缺了相册展示

**修复**: 在「关于我」和「用户评价」之间加3列网格相册
```js
const lifePhotos = computed(() => {
  const photos = info.value?.life_photos
  if (!photos) return []
  if (Array.isArray(photos)) return photos
  try { return JSON.parse(photos) } catch { return [] }
})
function getPhotoUrl(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return location.origin + (url.startsWith('/') ? url : '/' + url)
}
```

---

## 模式12: 页面初始化检查认证状态

**现象**: 已认证用户访问实名认证页看不到"已认证"状态

**根因**: 页面 `verified` ref 初始化为 `false`，未调 API 检查

**修复**: `onMounted` 中调 `/api/user/profile` 检查 `res.verified`
```js
onMounted(async () => {
  try {
    const res = await api.get('/user/profile')
    if (res?.verified) { verified.value = true; userName.value = res.nickname }
  } catch {}
  loading.value = false
})
```

## 模式13: 前后端HTTP方法/URL/字段三联不匹配

**现象**: 按钮点击无反应、network显示404/405、报错但不明确

**根因**: 前端调 `POST /admin/playmate/:id/toggle-online`，后端是 `PUT /admin/playmate/:id/toggle`

**高频错误**: URL路径不匹配、GET/POST/PUT混用、字段名不一致

**修复**: 前后端对齐三步走:
1. `curl -sI -X METHOD URL` 测试后端实际路由+方法
2. 对比前端 `api.get/post/put/delete` 调用的URL
3. 统一：优选改前端匹配后端（后端可能多处调用）

**已知不匹配**:
| 前端 | 后端 |
|------|------|
| `POST /admin/playmate/:id/toggle-online` | `PUT /admin/playmate/:id/toggle` |
| `api.post(...)` 发送 `{status}` | 后端读 `{action}` |

---

## 模式14: 上下架与列表显示的字段分离

**现象**: 下架后前端仍能看到陪玩师

**根因**: 下架操作改了 `is_online` 字段，但列表查询 WHERE 只过滤了 `status=1`（审核状态），未加 `is_online=1`

**修复**: 所有面向用户的列表查询补 `c.is_online=1`
```python
where = ["c.status=1", "c.is_online=1", "u.status=1"]
```

**检查点**: `companion/list`, 首页推荐/热门, 搜索接口 — 全部3+处

---

## 模式15: WebSocket 替代轮询（客服系统）

**场景**: 实时聊天、消息推送

**架构**: Flask-REDACTED + socket.io-client + Nginx代理
1. `pip install flask-REDACTED --break-system-packages`
2. `main.py`: `SocketIO(app, async_mode='threading')` + `register_socket_events(socketio)`
3. Nginx: 独立 `location /socket.io/` 块，`proxy_http_version 1.1` + `Upgrade/Connection` 头
4. 前端: `import { io } from 'socket.io-client'` → `io('/', { query: {token}, transports:['websocket','polling'], reconnection:true })`
5. 事件分离: `user_send/user_join/new_message` (用户) vs `admin_join/admin_reply/admin_new_message` (管理)

**断线重连**: `reconnectionDelay: 1000, reconnectionDelayMax: 5000`
**离线消息**: connect时 `user_join` 事件推送全量历史

---

## 模式16: 管理端新增页面流程

**步骤**:
1. 后端: 新建Blueprint+路由 → `main.py` 注册
2. 前端: `AdminXxx.vue` → `router/index.js` 加路由 → `AdminSidebar.vue` 加菜单项（`isActive()` 匹配）
3. 构建部署

---

## 模式17: 多游戏独立定价（注册+下单联动）

**场景**: 陪玩师每游戏单独设价，下单时选游戏自动切换价格

**注册页 Step2**: 每游戏一个 `gamePrices[gid]` reactive 输入框，默认 ¥50
```js
const gamePrices = reactive({})
const allPricesValid = computed(() =>
  form.intro.trim() && selectedGames.value.length > 0 &&
  selectedGames.value.every(gid => (gamePrices[gid] || 0) >= 1)
)
```
提交: `games: selectedGames.value.map(gid => ({game_id: gid, price_1h: gamePrices[gid]}))`

**下单页 CreateOrder**: 游戏列表可切换 → `selectGame(g)` 更新 `price1h/price2h/priceNight`
```js
function selectGame(g) {
  selectedGameId.value = g.id
  price1h.value = g.price_1h || 0
  price2h.value = Math.round((g.price_1h || 0) * 1.8)
  priceNight.value = Math.round((g.price_1h || 0) * 3.5)
}
// Submit: { companion_id, game_id: selectedGameId, service_type }
```

## 模式18: 502排查 — 后端模块加载失败

**现象**: 前端所有请求 502，`curl /api/health` 返回 nginx 502 页面

**诊断**:
```bash
sudo journalctl -u ttdazi --no-pager -n 30
# 看到: HaltServer 'Worker failed to boot.'

cd /opt/ttdazi/backend && python3.12 -c "from main import app; print('OK')"
# 看到具体 ImportError
```

**常见**: `from app.utils import admin_required` → `admin_required` 在 `app.admin` 不在 `utils`
修复: `from app.admin import admin_required`

## 模式19: 密码保护下载页

```vue
<!-- Download.vue — 密码输入 → 验证通过 → 显示下载链接 -->
<input v-model="password" type="password" @keyup.enter="checkPassword" />
<!-- 验证: password === '...' → verified=true → 显示文件列表 -->
```
后端: `/api/downloads/<filename>?pwd=xxx` 返回 `send_from_directory(..., as_attachment=True)` 或 403。

## 模式20: axios拦截器unwrap后数据是对象不是数组

**症状**: `(res || []).map is not a function` — 控制台报 `.map is not a function`

**根因**: 拦截器 `return res.data.data`。后端 `success({list:[], total:N})` → 拦截器返回 `{list: [...], total: N}`，不是数组。

```js
// ❌ 错误
const res = await api.get('/admin/users')
list.value = res || []  // res = {list: [...], total: N}，不是数组！

// ✅ 正确
const res = await api.get('/admin/users')
list.value = (res && res.list) || []
allOrders.value = ((res && res.list) || []).map(o => ...)
```

**影响页面**: AdminUsers, AdminOrders — 所有管理端列表页。

## 模式21: 管理端401跳转到用户登录页

**症状**: 管理端 token 过期后页面白屏、跳转错误

**修复**: axios 拦截器根据当前路径判断
```js
const isAdmin = location.hash.includes('/admin')
router.push(isAdmin ? '/admin/login' : '/login')
```

## 模式22: setInterval 返回值不能挂属性

**症状**: `TypeError: Cannot create property '_slow' on number '10'`

**根因**: `setInterval` 返回 number（timer ID），不能挂 `._slow` 属性

```js
// ❌ 错误
timer._slow = slowTimer  // 数字不能挂属性

// ✅ 正确
let timer = null
let slowTimer = null
```

## 模式23: 管理端页面必须统一 admin-layout

**规则**: 所有 admin 页面统一使用：
```html
<div class="admin-layout">
  <AdminSidebar />
  <div class="admin-main">
    <!-- 内容 -->
  </div>
</div>
```
CSS 必须含 `margin-left: 220px` 避免被固定侧栏遮挡。禁止独立 `page-container` / `admin-page`。

## 模式24: Flask 视图函数名重复崩溃

**现象**: `AssertionError: View function mapping is overwriting an existing endpoint function`
gunicorn worker 无法启动

**根因**: 同一个蓝图内有两个同名函数（即使 route 不同），如 `admin.review_delete`

**排查**: `grep -n "def review_delete\|def review_status" admin.py`
删除重复函数，保留一个。或用不同函数名。

**注意**: 修改 blueprint 文件后必须重启: `sudo systemctl restart ttdazi`

---

---\n\n## 模式25: 移动端 WebView 弹窗\n\n## 模式26: CAPTCHA 验证码 `const` TDZ — 图片静默不显示\n\n**症状**: 验证码图片始终不显示，无 console 错误，无网络请求。\n\n**根因**: `<script setup>` 中 `const` 不会提升。`refreshCaptcha()` 调用在 `const captchaImage` 声明之前 → TDZ 错误被 `catch{}` 吞掉。\n\n**修复**: 将 `const captchaImage/Key/Answer` 声明移到 `refreshCaptcha()` 之前。\n\n**排查**: `grep -n 'refreshCaptcha\\|const captchaImage' <file>.vue`\n\n## 模式27: 多步表单模板分支遗漏\n\n加 UI 元素到多步表单 (`v-if=\"step===1/2/3\"`) 时，替换只命中第一个分支。必须检查所有分支。

见 `references/mobile-webview-pitfalls.md`：
- `showConfirmDialog` 替代原生 `confirm()`
- `navigator.clipboard` HTTP fallback (`textarea+execCommand`)
- fixed 定位 z-index 层级规则
- 底部栏独立于 v-if 渲染

---

## 模式27: 隐私协议弹窗 / VerifyIdentity 多步表单

**场景**: 实名认证 → 隐私弹窗 → 勾选同意 → 上传身份证 → 提交

### 弹窗必须独立于页面容器（关键!）
```html
<template>
  <div class="verify-page">
    <!-- 页面内容 -->
  </div>
  <!-- 隐私弹窗：OUTSIDE verify-page，否则 fixed 全屏失效 -->
  <div v-if="step === 1" class="privacy-overlay">
    <div class="privacy-dialog">...</div>
  </div>
</template>
```
verify-page 必须有 `</div>` 闭合，否则弹窗被嵌套在页面内→全屏遮罩不显示。

### 自定义 Checkbox + 按钮禁用态
```html
<label @click="agreed = !agreed">
  <span class="pd-check" :class="{checked: agreed}">{{ agreed ? '✓' : '' }}</span>
  <span>我已阅读并同意以上说明</span>
</label>
<button :disabled="!agreed" @click="step = 2">请先勾选同意</button>
```
- `:disabled="!agreed"` — 不勾选不可点击
- 按钮文字固定为"请先勾选同意"，勾选后无变化（简洁）
- 红字提示 `↑ 请先勾选上方同意条款` 仅在未勾选时显示

### 身份证上传 + OCR 自动回填
```js
const fileInput = ref(null)
function uploadId(side) { fileInput.value.click() }
const r = await api.post('/review/v2/verify/upload-id', form, {
  headers: { 'Content-Type': 'multipart/form-data' }
})
// OCR 回填
if (r.ocr.name) realName.value = r.ocr.name
if (r.ocr.id_card) idCard.value = r.ocr.id_card
```

---



## 模式28: 全局CSS类批量统一改造

**场景**: 将10+个页面的自定义scoped样式统一为`global.css`中定义的全局类（`.page`, `.header-bar`, `.card`, `.btn-primary`, `.input-field`, `.menu-item`, `.badge`）

### 完整设计系统（在 `src/assets/global.css` 中定义）

```css
.page            { min-height:100vh; background:#f5f6fa; padding-bottom:80px; }

.header-bar      { display:flex; align-items:center; padding:14px 16px;
                   background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; gap:12px; }
.header-bar .back   { font-size:22px; cursor:pointer; }
.header-bar .title  { font-size:17px; font-weight:700; flex:1; text-align:center; }
.header-bar .right  { width:28px; }

.card            { background:#fff; border-radius:12px; padding:16px;
                   margin:12px 16px; box-shadow:0 1px 6px rgba(0,0,0,0.04); }

.menu-item       { display:flex; align-items:center; padding:15px 16px;
                   background:#fff; border-radius:12px; margin-bottom:10px;
                   box-shadow:0 1px 6px rgba(0,0,0,0.04); cursor:pointer; }
.menu-item .mi-icon   { width:38px; height:38px; border-radius:10px;
                        display:flex; align-items:center; justify-content:center;
                        font-size:18px; margin-right:12px; flex-shrink:0; }
.menu-item .mi-info   { flex:1; min-width:0; }
.menu-item .mi-title  { font-size:14px; color:#333; font-weight:500; }
.menu-item .mi-desc   { font-size:11px; color:#bbb; margin-top:2px; }
.menu-item .mi-arrow  { font-size:20px; color:#ddd; margin-left:8px; flex-shrink:0; }

.btn-primary     { border:none; border-radius:10px; padding:12px 0;
                   background:linear-gradient(135deg,#667eea,#764ba2); color:#fff;
                   font-size:15px; font-weight:600; cursor:pointer; text-align:center; }
.btn-primary:active { opacity: 0.85; }

.input-field     { width:100%; padding:11px 14px; border:1px solid #eee;
                   border-radius:10px; font-size:14px; outline:none; box-sizing:border-box; }
.input-field:focus { border-color:#667eea; }

.badge           { display:inline-block; padding:2px 8px; border-radius:4px;
                   font-size:11px; font-weight:600; }
.badge-blue   { background:#e3f2fd; color:#1565c0; }
.badge-green  { background:#e8f5e9; color:#2e7d32; }
.badge-red    { background:#ffebee; color:#c62828; }
.badge-orange { background:#fff3e0; color:#e65100; }
.badge-purple { background:#f3e5f5; color:#7b1fa2; }

.empty-state     { text-align:center; padding:60px 20px; }
.empty-state .empty-icon { font-size:56px; opacity:0.4; margin-bottom:10px; }
.empty-state .empty-text { font-size:14px; color:#888; }

.section-label   { padding:4px 16px 8px; font-size:13px; color:#999; font-weight:600; }
.form-group      { margin-bottom:14px; }
.form-group label { display:block; font-size:13px; font-weight:600; color:#555; margin-bottom:4px; }
```

### 常用的全局类映射表

| 自定义类 (旧) | 全局类 (新) | 说明 |
|---------------|-------------|------|
| `page-container` | `page` | 页面容器 |
| `gradient-header` / `settings-header` / `page-header` / `msg-header` / `ps-header` / `ag-header` | `header-bar` + `back` + `title` + `right` | 渐变顶栏 |
| `order-card` / `review-card` / `detail-card` / `ag-card` | `card` | 白色卡片 |
| `fav-card` | `menu-item` + `mi-icon` / `mi-info` / `mi-title` / `mi-desc` | 菜单项 |
| `action-btn.primary` / `ps-btn` / `gradient-btn` / `modal-btn.confirm` | `btn-primary` | 渐变主按钮 |
| `wf-inp` / `dl-input` / `modal-input` | `input-field` | 输入框 |
| `coupon-badge` / `expired-badge` | `badge badge-orange` / `badge badge-red` | 状态标签 |
| `empty-state` / `empty-text` / `empty-icon` | 已在global.css中保留同名类 | 空状态 |
| `menu-label` | `section-label` | 分段标题 |

### 批量改造流程（10+ 页面）

```bash
# 1. 在 global.css 中定义完整设计系统类
# 2. 用 delegate_task 并行子代理处理多个页面（每个子代理处理 5-10 个）
# 3. 每个子代理：read_file → patch template (class引用) → patch style (删除重复定义) → 保留自定义样式
# 4. 全局 grep 确认无遗留自定义类
grep -rn "page-container\|gradient-header\|page-header" frontend/src/views/  # 期望: 0
grep -rn "header-bar\|class=\"page\"\|class=\"card\"" frontend/src/views/  # 期望: 多处
# 5. 构建部署验证
cd frontend && npm run build && bash /opt/ttdazi/deploy.sh
```

### 已改造的 14+ 个页面（2026-07-06）

Agreement, Orders, Settings, Security, Favorites, Reviews, Coupons, About, Download, Messages, MessageDetail, Profile, List, Detail, TeamBoard, AdminAgreements, AdminWithdrawals, AdminDashboard, AdminOrders, AdminPlaymates, AdminContent, AdminCoupons, AdminPlaymateDetail

### ⚠️ 陷阱: 子代理批量替换会误删独立 import

子代理批量替换 `from 'vant'` 时可能误删同一文件的其他 `import` 行：

```js
// 原始
import { showConfirmDialog } from 'vant'
import { useRouter, useRoute } from 'vue-router'  // ← 子代理替换时丢失！
import { smartBack } from '@/utils/nav'

// ❌ 子代理替换后
import safeToast from '@/utils/toast'  // useRouter/useRoute/smartBack 丢失！
```

**预防：**
1. 子代理处理前先 `read_file` 全文，确认所有 import 行
2. 替换时用 `patch` 工具的精确 old_string，仅替换要改的那一行
3. 构建报 `useRouter is not defined` 等错误 → `re-read` 文件，补回丢失的 import
4. **已发生**: `CompanionRegister.vue` 丢 `useRouter/useRoute`，`Agreement.vue` 丢 `smartBack`（后修复）

### ⚠️ 陷阱: patch old_string 过宽误改 API endpoint

详见模式6陷阱 — 子代理批量替换 loading 弹窗时若 old_string 包含上下文代码（如 API 调用），可能误改 endpoint 名称。

**已发生**: `Home.vue` 中 `showLoadingToast` 替换时，old_string 包含了 `/companion/recommend` 和 `/companion/nearby` 两个端点，被误改为 `/companion/list`。

---

## 模式32: `.menu-item-3d` 不要嵌套 `.mi-arrow-group`

**症状**: 设置页菜单项的箭头没有右对齐，文字和箭头挤在一起。

**根因**: `.mi-arrow-group` 是 `<div>` 包裹 `.mi-desc` + `.mi-arrow`，但 `.mi-arrow` 的 `margin-left: auto` 只在 flex 直接子元素中有效。嵌套在另一个 div 里时，箭头推不到右侧。

```vue
<!-- ❌ 嵌套导致 margin-left:auto 失效 -->
<div class="menu-item-3d">
  <div class="mi-icon">📋</div>
  <div class="mi-info"><div class="mi-title">标题</div></div>
  <div class="mi-arrow-group">            <!-- ← 冗余包装！ -->
    <span class="mi-desc">描述</span>
    <span class="mi-arrow">›</span>
  </div>
</div>

<!-- ✅ 直接放在 menu-item-3d 的 flex 下 -->
<div class="menu-item-3d">
  <div class="mi-icon">📋</div>
  <div class="mi-info"><div class="mi-title">标题</div></div>
  <span class="mi-desc">描述</span>
  <span class="mi-arrow">›</span>
</div>
```

**修复模式**: 删除所有 `.mi-arrow-group` 包裹，箭头/锁定/描述直接作为 `.menu-item-3d` 的 flex 子元素。

**检查**: 
```bash
grep -rn "mi-arrow-group" frontend/src/views/
# 期望: 0 处
```

---

## 模式33: 登录/注册页全局共享样式

Login, Register, EmailRegister, FollowRegister 四个页面共用同一套 `.login-page` / `.login-card` / `.login-logo` / `.login-tabs` / `.login-agreement` / `.login-footer` 类，定义在 `global.css` 的 `/* 登录/注册页面 */` 段。

**原则**: 登录注册页的 scoped style 只保留验证码图片、发送按钮等该页面特有的渲染样式。

---

## 模式39: 返回箭头统一风格

**场景**: 所有页面左上角的返回箭头样式和位置必须一致。

### 标准样式（已在 global.css 中定义）

```css
.header-bar .back { font-size: 22px; cursor: pointer; line-height: 1; color: #fff; }
```

### 标准用法（有 header-bar 的页面）

```html
<div class="header-bar">
  <span class="back" @click="smartBack(route.path)">‹</span>
  <span class="title">页面标题</span>
  <span class="right"></span>
</div>
```

用 `<span>` 不用 `<div>`，`font-size: 22px` 与全局统一。

### 特殊情况处理

| 页面布局 | 方案 |
|----------|------|
| 有 `.header-bar` | 直接用 `<span class="back">` |
| Profile（`.profile-header`） | absolute 定位，inline style: `position:absolute;top:10px;left:12px;font-size:22px;color:#fff;z-index:20;cursor:pointer;line-height:1` |
| Detail（`.hero-section`） | fixed 半透黑底圆标，`background:rgba(0,0,0,0.2);border-radius:50%;width:36px;height:36px;` |
| List（`.gradient-header`） | absolute 定位，`top:44px;left:14px;font-size:28px;color:#fff;` |
| Download（`.dl-page`） | fixed 顶栏内，半透黑底 |
| TeamBoard（无标准容器） | fixed 左上角 |

### ⚠️ 陷阱0：返回箭头符号不统一（← vs ‹）

**现象**：部分页面使用 `←`（普通左箭头）而非 `‹`（标准左单箭头）。

**检查命令**：
```bash
grep -rn "←</span>" src/views/ --include="*.vue"
# 期望：0 行
```

**批量修复**：
```bash
cd src/views
for f in ChatConversation.vue ChatList.vue CompanionRegister.vue \
  Coupon.vue CreateDemand.vue CreateOrder.vue \
  DemandHall.vue Favorites.vue MessageDetail.vue \
  Messages.vue MyDemands.vue MyFeedback.vue \
  Orders.vue Reviews.vue Security.vue VerifyIdentity.vue; do
  sed -i "s|←</span>|‹</span>|g" "$f"
done
sed -i "s|←|‹|g" List.vue  # inline style 版本
```

**已验证**：2026-07-09 修复了 16 个文件中的 `←`→`‹`。

### ⚠️ 陷阱1：必须导入 `useRoute` 并定义

```js
// ❌ 错误 — route 未定义
import { useRouter } from 'vue-router'
const router = useRouter()
// template: @click="smartBack(route.path)" — route 是 undefined！

// ✅ 正确
import { useRouter, useRoute } from 'vue-router'
const router = useRouter()
const route = useRoute()  // ← 漏了这一行！
```

**此错误曾导致 Profile.vue 返回箭头点击无反应**:
- DOM 中 `<span class="back">‹</span>` 正常渲染
- 但 `smartBack(undefined)` 无法判断返回路径
- 点击箭头没有任何响应

**排查方法**: 如果页面返回箭头已渲染(DOM中存在)但点击无效，首先检查 script 中是否有 `const route = useRoute()`。

### ⚠️ 陷阱2：改 header 结构后必须补 import

**场景**：将 `$router.back()` 或 `$router.push('/path')` 改为 `smartBack(route.path)` 后，编译通过但运行时报错。

**根因**：模板中使用了 `smartBack(route.path)` 但 `smartBack` 或 `route` 未导入/未定义。

**修复检查清单**（每次改 header 后必须检查）：
```js
// 检查以下三行是否都存在
import { smartBack } from '@/utils/nav'
import { useRoute } from 'vue-router'  // 或 useRouter, useRoute
const route = useRoute()
```

**本次修复影响文件**：PlaymateHome.vue, PlaymateProfile.vue, PlaymateOrders.vue, Recharge.vue, VerifyIdentity.vue

### ⚠️ 陷阱3：smartBack FALLBACK_MAP 必须匹配入口

详见模式29。

---

## 模式45: 单文件语法错误导致整个构建静默失败

**场景**: 前端修改看起来"没生效"——所有页面都还是旧代码，多次构建部署都无效。

**根因**: 某个 `.vue` 文件有语法错误（如 `await` 在非 `async` 函数中），Vite 在构建阶段抛出错误并**终止整个构建**。后续的 deploy.sh 可能只执行了后端部分，前端 dist 还是旧的。

**症状**（按诊断优先级）:
1. 构建输出只有 `✓ 115 modules transformed.` 但没有 `✓ built in Xs` → **构建失败**！
2. `npm run build | tail -20` 显示具体错误（如 `Unexpected reserved word 'await'. (101:4)`）
3. 新加入的 HTML 元素在编译产物中不存在（如 `chat-row` 类在 `Orders-*.js` 中为 0 匹配）
4. deploy.sh 输出 `✅ 前端编译完成` 但实际走了旧的 dist

**排查步骤**:
```bash
# 1. 确认构建是否真正成功
cd /opt/ttdazi/frontend && npm run build 2>&1 | grep -E "✓ built|error during|error:"

# 2. 如果看到 `error during build:`，查看具体错误
npm run build 2>&1 | tail -30

# 3. 确认编译产物是否包含新代码
grep -c "chat-row\|与陪玩师私聊\|新功能关键词" dist/assets/Orders-*.js

# 4. 常见的语法错误模式
#    - function foo() { await api.post(...) }  →  needs async function foo()
#    - import { computed } from 'vue' missing   →  computed is not defined
#    - }  extra closing brace                    →  Unexpected token
```

**已发生（2026-07-07）**: `MyDemands.vue` 中 `function completeDemand()` 缺少 `async` 关键字，导致 `await api.post(...)` 报 `Unexpected reserved word 'await'`。整个前端构建失败，Orders.vue 的聊天按钮、DemandHall 的改动等 10+ 页面修改从未被部署。

**预防**: 每次 `npm run build` 后必须检查输出中是否包含 `✓ built in Xs`。只有这一行确认构建成功，否则所有前端改动都不会上线。

## 模式46: 管理端实名认证双表同步

**场景**: 用户提交实名认证后管理员后台看不到。

**根因**: 两条数据路径不互通：
- 用户提交 → `POST /user/verify` → 更新 `user.real_name, id_number, verify_status`
- 管理端查询 → `GET /admin/verifies` → 查询 `verify_application` 表

**修复**: 用户提交时同时写两张表：
```python
# POST /user/verify
cur.execute(
    "INSERT INTO verify_application (user_id, real_name, id_card, status) VALUES (%s, %s, %s, 0)",
    (user_id, real_name, id_number)
)
cur.execute("UPDATE user SET real_name=%s, id_number=%s, verify_status=2 WHERE id=%s",
    (real_name, id_number, user_id)
)
```

**历史数据补全**: 管理端查询也扫描 `user` 表中 `verify_status=2` 但不在 `verify_application` 的记录。

### ⚠️ 陷阱: `audit_log` 函数不存在

在 `admin.py` 中尝试 `from app.utils import audit_log` 但该函数**不存在**于 `utils.py` 中。正确的做法是：
```python
# 直接 INSERT SQL
cur.execute(
    "INSERT INTO audit_log (user_id, action, detail) VALUES (%s, %s, %s)",
    (admin_id, action, detail)
)
```

## 模式47: 管理后台路径每日轮换

**场景**: 管理后台 URL 每天自动更换，防止暴力破解。

### 前端动态路由实现

```javascript
// router/index.js — 路由生成函数
export function createAdminRoutes(prefix) {
  const p = `/${prefix}`
  return [
    { path: `${p}/login`, name: 'AdminLogin', ... },
    { path: `${p}/`, name: 'AdminDashboard', ... },
    // ... 所有 admin 路由用 `${p}` 前缀
  ]
}

// 从 sessionStorage 读取当前路径
const storedPrefix = sessionStorage.getItem('admin_route_path') || 'op-ztHWaT-0706'
const routes = [
  // ... 非 admin 路由
  ...createAdminRoutes(storedPrefix),
]

// 路由守卫：旧 /admin/ 路径重定向
router.beforeEach((to, from, next) => {
  const currentPath = sessionStorage.getItem('admin_route_path') || 'op-ztHWaT-0706'
  if (to.path.startsWith('/admin/') || to.path === '/admin') {
    return next(to.path.replace('/admin', `/${currentPath}`))
  }
  next()
})
```

### ⚠️ 陷阱1: `sessionStorage` 不在 Vue 3 模板白名单

Vue 3 模板中直接使用 `sessionStorage` 会报 `Cannot read properties of undefined (reading 'getItem')`。因为 Vue 模板只识别 `setup` 中的变量和内置全局。必须：

```vue
<!-- ❌ 模板中直接使用 -->
@click="$router.push(`/${sessionStorage.getItem('admin_route_path')}/users`)"  

<!-- ✅ 方案A: 用 window. 前缀 -->
@click="$router.push(`/${window.sessionStorage.getItem('admin_route_path')}/users`)"

<!-- ✅ 方案B（推荐）: 在 script 中读取，模板引用变量 -->
<script setup>
const adminPath = sessionStorage.getItem('admin_route_path') || 'op-ztHWaT-0706'
</script>
<template>
  @click="$router.push(`/${adminPath}/users`)"
</template>
```

### ⚠️ 陷阱2: 路由在模块加载时创建，App.vue 此时还未 fetch 路径

路由模块 `router/index.js` 在应用初始化时执行，比 `App.vue` 的 `onMounted` 早。路径 fetch 发生在 `App.vue.onMounted` 中：

```
1. 路由模块加载 → sessionStorage 可能为空 → 用默认路径
2. App.vue mount → fetch('/api/admin/path') → 存 sessionStorage
3. 但此时路由已创建，新路径不生效！
```

**修复**: App.vue 中路径 fetch 后如果检测到变化，重新加载页面：
```javascript
fetch('/api/admin/path').then(r=>r.json()).then(d=>{
  if (d && d.code === 0 && d.data && d.data.path) {
    const oldPath = sessionStorage.getItem('admin_route_path')
    const newPath = d.data.path
    sessionStorage.setItem('admin_route_path', newPath)
    if (oldPath && oldPath !== newPath) {
      window.location.reload()  // 重新加载 → 用新路径创建路由
    }
  }
})
```

### ⚠️ 陷阱3: AdminSidebar 路径硬编码

AdminSidebar.vue 中所有 `$router.push()` 和 `isActive()` 都用硬编码路径。批量替换时要注意产生 `//users`（双斜杠）的问题。

## 模式48: 管理端 `margin-left` 与 `flex` 布局冲突

**场景**: 管理后台内容区域偏移到右侧、显示错乱。

**根因**: `.admin-main` 同时使用了 `margin-left: 220px`（旧布局）和 `flex: 1`（新 Flex 布局）。当 `.admin-layout` 启用 `display: flex` 后，`margin-left` 导致内容在 flex 分配的空间基础上又偏移了 220px。

**排查**:
```bash
# 1. 浏览器检查 admin-main 元素的计算样式
grep "margin-left: 220px" /opt/ttdazi/frontend/src/assets/global.css
grep "margin-left: 220px" /opt/ttdazi/frontend/src/views/admin/ --include="*.vue"

# 2. 确认 dist 中的 CSS（部署才是实际生效的）
grep "margin-left.*220" dist/assets/style-*.css

# 3. 检查构建是否真的通过（见模式45）
```

**修复**: 统一为 Flex 布局，去掉 `margin-left`：
```css
/* ❌ 旧 */
.admin-main { margin-left: 220px; flex: 1; padding: 20px; }

/* ✅ 新 — flex: 1 自动分配剩余空间 */
.admin-main { flex: 1; padding: 20px; }
```

注意检查所有 admin 页面的 scoped CSS 和 `global.css` 两个位置。`global.css` 是影响所有页面的全局规则，优先级低于 scoped CSS 但有更高特异性时可能覆盖 flex。

## 模式49: 页面布局右移 — 检查 global.css 的非 scoped 规则

**场景**: 所有 admin 页面内容区域偏移，即使 scoped CSS 已经去掉 `margin-left`。

**根因**: `global.css` 中的非 scoped 规则 `.admin-main { margin-left: 220px; ... }` 在所有页面上生效，且 scoped CSS 的 `flex: 1` 不会自动覆盖 `margin-left`。

**排查工具**:
```javascript
// 浏览器控制台查看所有匹配的 CSS 规则
const rules = []
for (let i = 0; i < document.styleSheets.length; i++) {
  try {
    const sheet = document.styleSheets[i]
    for (let j = 0; j < (sheet.cssRules || []).length; j++) {
      const rule = sheet.cssRules[j]
      if (rule.selectorText && rule.selectorText.includes('admin-main') && rule.style.marginLeft === '220px') {
        rules.push({ selector: rule.selectorText, file: sheet.href })
      }
    }
  } catch(e) {}
}
console.log(rules)


**场景**: 有 tab 栏的页面（Orders、Messages）的渐变 banner 总高度比无 tab 页面高出约 36px。

**根因**: 全局 `.header-bar` 的 `padding-bottom: 12px` + tab 项的 `padding: 12px 0` 叠加。

**修复**:\n1. Tab 项 padding 从 `12px 0` → `8px 0`\n2. Tab 栏背景从白色 → 跟 header-bar 一致的渐变紫\n3. 选中态从蓝色 → 白色下划线\n\n## 模式42: Logo 设计多轮截图反馈流程\n\n**场景**: 用户要求重新设计网站 logo，需要先出设计稿截图给用户确认，再替换到线上。\n\n### 流程\n1. 创建独立的 HTML 设计展示页（`/tmp/logo_vX.html`），用纯 SVG 绘制多个方案\n2. 用 Playwright 截图：`npx playwright screenshot \"http://127.0.0.1:8999/logo_vX.html\" /tmp/logo_vX.png --full-page`\n3. 通过 QQ 发送截图给用户（`MEDIA:/tmp/logo_vX.png`）\n4. 根据用户反馈调整方向 → 重新设计 → 再截图\n5. 用户确认后：替换 `public/favicon.svg`、创建 `public/logo/*.svg` 全套\n6. 更新 `index.html` 的 `<link rel=\"icon\">` 和 `href`\n\n### 快速本地 HTTP 服务（用于截图）\n```bash\ncd /tmp && python3 -m http.server 8999 &\nnpx playwright screenshot \"http://127.0.0.1:8999/logo_design.html\" /tmp/logo.png --full-page\n```\n\n### 全套 Logo SVG 文件清单\n| 文件 | 用途 | 尺寸 |\n|------|------|------|\n| `public/favicon.svg` | 浏览器标签图标 | 48×48 紫色渐变方块+🎮 |\n| `public/logo/logo-vertical.svg` | 竖版标准主Logo | 🎮+同途搭子+拼音 |\n| `public/logo/logo-horizontal.svg` | 横版Header用 | 左🎮右文字 |\n| `public/logo/logo-app.svg` | App方形图标 | 180×180 渐变紫🎮 |\n| `public/logo/logo-wechat.svg` | 圆形微信头像 | 120×120 |\n\n### 设计参考\n- 比心(Bixin)风格：粉紫渐变心形+🎮，心形交叠代表「搭子」社交\n- 高端科技风：六边形棱镜+电路通路、莫比乌斯环、钻石切割、星际轨道\n- 品牌色：`#667eea` → `#764ba2`（蓝紫渐变）\n\n## 模式43: `goTo()` 函数必须放行公共页面\n\n**场景**: Profile.vue 的 `goTo()` 函数对所有非首页路径要求登录，但用户协议、隐私政策、关于页等应是公开可访问的。\n\n**症状**: 未登录用户点击「用户协议」菜单项时被重定向到登录页。\n\n**修复**:\n```js\nfunction goTo(path) {\n  const publicPaths = ['/', '/agreement/user', '/agreement/privacy', '/agreement/rules', '/agreement/disclaimer', '/about']\n  if (!user.value.id && !publicPaths.includes(path)) {\n    safeToast('请先登录')\n    router.push('/login')\n    return\n  }\n  router.push(path)\n}\n```\n\n**规则**: 所有需要登录检查的导航函数必须维护一个 `publicPaths` 白名单，放行协议/关于等公共页面。\n\n## 模式44: `onMounted` 中 `localStorage.setItem` 必须加 try/catch\n\n**场景**: 用户信息加载后将数据写入 localStorage。\n\n**症状**: 存储空间满时 `localStorage.setItem` 抛 `QuotaExceededError`，整个 `onMounted` 崩溃，用户看到白屏。\n\n**修复**:\n```js\nonMounted(async () => {\n  try {\n    const res = await api.get('/user/profile')\n    profileData.value = res || {}\n    try { localStorage.setItem('user', JSON.stringify(res || {})) } catch { /* 存储满静默 */ }\n  } catch (e) {\n    console.warn('加载失败:', e?.message)\n  }\n})\n```\n\n**规则**:\n- 只有读取 localStorage（`getItem`）需要在 `safeGetUser()` 这类函数中全局保护\n- 写入（`setItem`）在业务代码中单独加 `try/catch`，不需要提到工具函数中\n- 读取写入都不应该抛未捕获异常导致白屏

```css
/* Tab 栏用渐变紫与 header-bar 视觉连成一体 */
.tab-bar { background: linear-gradient(135deg, #667eea, #764ba2); padding: 0; }
.tab { padding: 8px 8px; font-size: 13px; color: rgba(255,255,255,0.65); }
.tab.active { color: #fff; font-weight: 700; border-bottom: 2px solid #fff; }

/* Messages 的 tab 同理 */
.msg-tabs { background: linear-gradient(135deg, #667eea, #764ba2); }
.tab-item { padding: 8px 0; color: rgba(255,255,255,0.65); }
.tab-item.active { color: #fff; border-bottom-color: #fff; }
```

**效果**: tab 栏视觉上融合为 banner 的一部分，总高度与无 tab 页面一致。

**影响文件**: Orders.vue（.tab-bar + .tab）, Messages.vue（.msg-tabs + .tab-item）

---

## 模式50: 陪玩师端页面布局统一标准

**场景**: 陪玩师端页面（PlaymateHome/Income/Profile/Orders）使用自定义布局而非标准 `.page` + `.header-bar`。

### 问题列表（2026-07-09 发现并修复）

| 页面 | 原问题 | 修复 |
|------|--------|------|
| PlaymateHome.vue | `page-container` + 自定义 `.header` 结构 | ✅ 改为 `.page` + `.header-bar` |
| PlaymateProfile.vue | `register-wrapper` + `reg-header` | ✅ 改为 `.page` + `.header-bar` |
| PlaymateIncome.vue | `page-container` + `gradient-header` + `back-row` | ✅ 改为 `.page` + `.header-bar` |
| PlaymateOrders.vue | `$router.push('/playmate/')` 硬编码返回 | ✅ 改为 `smartBack(route.path)` |
| 全部4页 | 缺 `smartBack`/`useRoute` import | ✅ 补全 |

### 标准模板

```vue
<template>
  <div class="page">
    <div class="header-bar">
      <span class="back" @click="smartBack(route.path)">‹</span>
      <span class="title">页面标题</span>
      <span class="right"></span>
    </div>
    <!-- 页面内容 -->
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { smartBack } from '@/utils/nav'
import safeToast from '@/utils/toast'
import api from '@/api'
const route = useRoute()
const router = useRouter()
</script>
```

### 检查命令

```bash
# 检查陪玩师端页面是否都用了标准布局
grep -n "class=\"page\"" src/views/playmate/*.vue
# 期望: 全部5个文件都有

# 检查是否还有自定义头栏
grep -n "register-wrapper\|page-container\|gradient-header\|back-row\|reg-header" src/views/playmate/*.vue
# 期望: 0 行

# 检查 import 完整性
grep -l "smartBack" src/views/playmate/*.vue
grep -l "useRoute" src/views/playmate/*.vue
# 期望: PlaymateHome/Income/Orders/Profile 都有
```

---

## 模式51: 陪玩师端运行时崩溃检查清单

**场景**: 检查陪玩师端页面（PlaymateHome/Income/Profile/Orders）是否存在运行时崩溃隐患。

### 致命级检查（必须修复，否则白屏/功能不可用）

| 检查项 | 错误示例 | 正确示例 |
|--------|---------|---------|
| 模板 @click 函数是否在 script 中定义 | `@click="chatWith(order)"` 但 script 无 `chatWith` 函数 | 定义 `async function chatWith(order) { ... }` |
| ref 变量名是否一致 | script 声明 `pendingOrders`，模板/script 引用 `pendingList` | 统一为 `pendingOrders` |
| 函数内部引用的变量是否存在 | `pendingList.value.find(...)` 但变量叫 `pendingOrders` | `pendingOrders.value.find(...)` |

### statusText 映射陷阱

**场景**: 陪玩师订单页显示状态文字错误。

**根因**: 订单状态使用字符串 key（如 `'completed'`, `'cancelled'`），但 API 返回数字（`0`=待支付, `1`=进行中, `2`=待确认, `3`=已完成, `4`=已取消）。

```js
// ❌ 错误 — 字符串 key，API 返回数字
const map = { completed: '已完成', cancelled: '已取消', paid: '已支付' }
return map[s] || s  // s=3 → undefined → 显示"3"

// ✅ 正确 — 数字 key
const st = Number(s)
return {0:'待支付',1:'进行中',2:'待确认',3:'已完成',4:'已取消'}[st] || '未知'
```

### 状态 badge class 陷阱

**场景**: 订单状态标签没有样式（显示为纯文字无背景色）。

**根因**: `:class="order.status"` 将数字（如 `3`）作为 class 名，但 CSS 定义的是 `.completed`, `.cancelled` 等字符串类名。

```html
<!-- ❌ 错误 — :class 生成 class="3" 但 CSS 定义 .completed -->
<span class="status-badge" :class="order.status">{{ statusText(order.status) }}</span>

<!-- ✅ 正确 — 用 's' + 数字前缀区分 -->
<span class="status-badge" :class="'s' + order.status">{{ statusText(order.status) }}</span>
```

```css
/* s3 对应 status=3 */
.s3 { background: #e8f5e9; color: #2e7d32; }
```

### 完成订单端点陷阱

**场景**: 陪玩师端「完成订单」按钮调用后端失效。

**根因**: 混淆了用户端完成和陪玩师端完成的端点：
- 用户端完成：`POST /order/complete`（在 `order.py` 中）
- 陪玩师端完成：`PUT /playmate/complete-order/<id>`（在 `playmate_api.py` 中）

```js
// ❌ 错误 — 用了用户端的端点
await api.post('/order/complete', { order_id: id })

// ✅ 正确 — 必须用陪玩师端的端点
await api.put('/playmate/complete-order/' + id)
```

### import 完整性检查

改 header-bar、改返回箭头、改 smartBack 调用后，必须检查以下三行是否齐全：

```bash
grep -c "smartBack" file.vue     # 使用 smartBack
grep -c "useRoute" file.vue      # 导入 useRoute
grep "const route = useRoute" file.vue  # 定义 route
```

```js
// 标准 import 模板
import { useRoute, useRouter } from 'vue-router'
import { smartBack } from '@/utils/nav'
const route = useRoute()
const router = useRouter()
```

**影响文件（2026-07-09）**: PlaymateHome.vue, PlaymateProfile.vue, PlaymateOrders.vue, Recharge.vue, VerifyIdentity.vue

---

## 模式41: `refreshCaptcha()` 的 `catch {}` 必须保持静默

**规则**: `refreshCaptcha()` 的 `catch {}` 是**故意静默**的——验证码加载失败时用户点击图片即可重试，不需要弹 Toast。

```js
async function refreshCaptcha() {
  try {
    const r = await api.get('/captcha/get')
    captchaImage.value = r.image
    captchaKey.value = r.key
    captchaAnswer.value = ''
  } catch {}  /* 静默：用户可点击验证码图片重试 */
}
```

**⚠️ 不要**在批量替换 `catch {} → safeToast` 时误改此函数。这个 catch 不是"吞错误"，而是有意的静默处理。

**影响文件**: Register.vue, EmailRegister.vue, FollowRegister.vue, Login.vue, Verification.vue

---

## 模式35: 首页配色增强（Home.vue 色彩优化）

**场景：** 用户觉得首页颜色"太单调了"。

### Hero 区 — 纯紫渐变 → 蓝粉金三色渐变 + 动画

```css
/* ❌ 旧：纯紫色静态渐变 */
.hero-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #5b2c8e 100%); }

/* ✅ 新：蓝粉金三色 + 动画呼吸 */
.hero-bg {
  background: linear-gradient(135deg, #4158D0 0%, #C850C0 46%, #FFCC70 100%);
  animation: heroFlow 8s ease infinite;
  background-size: 200% 200%;
}
@keyframes heroFlow {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
```

### 装饰粒子 — 静态圆 → 浮动发光动画
```css
.hero-bg::after {
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  animation: floatBubble 6s ease-in-out infinite;
}
```

### 区块标题 — 纯色 → 渐变色文字
```css
.section-title {
  font-size: 17px; font-weight: 700;
  background: linear-gradient(135deg, #4158D0, #C850C0);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

### 游戏网格 — 图标 → 白底圆角卡片
```css
.game-item { background: #fff; border-radius: 14px; padding: 10px 0; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
```

### 推荐卡片 & 陪玩师列表 — 加 3D 立体效果
用 `perspective(1000px) rotateX(1.5deg)` + 多层紫色阴影 + `::before` 高光。详见全站 3D 卡片模式。

**症状**: 设置页手机号行显示「›」（表示可绑定），但手机号已经绑定了。

**根因**: Settings.vue 模板中手机号行 `v-if` 判断写错了字段：
```vue
<!-- ❌ 错误 — 手机号行用了 email 的判断条件 -->
<span v-if="!user.email" class="mi-arrow">›</span>

<!-- ✅ 正确 — 应该用 phone_bound -->
<span v-if="!user.phone_bound" class="mi-arrow">›</span>
```

**规则**: 条件渲染字段必须一一对应——手机号用 `phone_bound`，邮箱用 `email`。做完字段相关修改后，检查同一组件内是否有其他字段用了错位的判断条件。

---

## 模式29: smartBack 回退路径必须匹配用户实际入口

**症状**: 用户在 Profile.vue 点"用户协议"进入 `/agreement/user`，返回时跳到了 `/settings`（错误的页面）。

**根因**: `utils/nav.js` 的 `FALLBACK_MAP` 把协议页面映射到 `/settings`，但这些页面实际是从 Profile 进入的。

**修复**:
```javascript
// utils/nav.js — 按用户实际导航路径映射，而非按功能分类
'/agreement/user': '/profile',          // 不是 '/settings'
'/agreement/privacy': '/profile',
'/agreement/rules': '/profile',
'/agreement/disclaimer': '/profile',
```

**规则**: FALLBACK_MAP 应该模拟用户访问此页面的真实路径：从哪里点进来的，回退时就回哪里。

**常见错误**:
- `/agreement/*` → `/settings`（实际从 Profile 进入）
- `/security` → `/settings`（实际从 Settings 进入，应该回到 `/settings` ✅）
- `/verify` → `/settings`（实际从 Settings 进入 ✅）
- `/service` → `/settings`（实际从 Settings 进入 ✅）

**检查方式**: 打开 Profile/Settings 等入口页，依次点每个 menu-item → 进入子页 → 点返回按钮 → 是否回到了原页。

---

## 模式30: 多 worker 验证码失效 — 必须用数据库

**症状**: 用户登录时反复提示"验证码已过期"，明明输入了正确的算术答案。

**根因**: gunicorn 启动多个 worker，每个 worker 内存里各有一份 `_store = {}` dict。GET 验证码走 worker A，登录校验走 worker B → worker B 找不到 → 报过期。

**修复**: 把 `_store` 改为 MySQL `captcha_log` 表，所有 worker 共享：

```sql
CREATE TABLE captcha_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `key` VARCHAR(32) NOT NULL,
    answer VARCHAR(10) NOT NULL,
    expires_at BIGINT NOT NULL,
    used TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_key (`key`),
    INDEX idx_expires (expires_at)
);
```

```python
# app/captcha.py
def get_captcha():
    # ... 生成图片算术题 ...
    cur.execute("INSERT INTO captcha_log (`key`, answer, expires_at) VALUES (%s, %s, %s)",
                (key, str(answer), int(time.time()) + 600))  # 10 分钟有效

def _verify(key, answer):
    cur.execute(
        "SELECT id, answer FROM captcha_log WHERE `key`=%s AND used=0 AND expires_at > %s LIMIT 1",
        (key, int(time.time())))
    row = cur.fetchone()
    if not row: return False, '验证码已过期，请刷新'
    cur.execute("UPDATE captcha_log SET used=1 WHERE id=%s", (row['id'],))
    return str(answer).strip() == row['answer'], 'ok'
```

**关键**:
1. 必须用所有 worker 共享的存储（DB/Redis），不能用内存 dict
2. 校验后立即标记 `used=1` 防止重用（一次性消费）
3. 定期清理过期记录（避免表无限增长）
4. 有效期建议 5-10 分钟（太短用户来不及输入，太长增大攻击窗口）

**配套前端处理**: 登录失败 → `refreshCaptcha()` 刷新图片 + 清空输入框。

---

## 模式31: deploy.sh 自动同步 Nginx 配置

**问题**: 修改 `deploy/ttdazi-nginx.conf` 后，需要手动 scp + ssh 重启 Nginx。每次发布都忘。

**修复**: 在 `deploy.sh` 末尾添加：

```bash
scp -o StrictHostKeyChecking=no deploy/ttdazi-nginx.conf "$SERVER_B_USER@$SERVER_B:/tmp/"
ssh -o StrictHostKeyChecking=no "$SERVER_B_USER@$SERVER_B" "sudo cp /tmp/ttdazi-nginx.conf /etc/nginx/sites-enabled/ttdazi && \
  sudo rm -f /etc/nginx/conf.d/ttdazi.conf && \
  sudo nginx -t && sudo systemctl reload nginx" || echo "Nginx配置更新失败（可手动执行）"
```

**⚠️ 关键陷阱**: Server B 上 `conf.d/ttdazi.conf` 和 `sites-enabled/ttdazi` 都定义了 `server_name 82.157.202.24`。Nginx 只加载第一个匹配的。**必须 `rm -f conf.d/ttdazi.conf`** 否则新配置永远不生效。

**部署后验证**:
```bash
curl -sI http://82.157.202.24/assets/$(ls frontend/dist/assets/ | grep '\.js$' | head -1) | grep -i 'cache-control'
# 期望: Cache-Control: public, immutable, max-age=31536000
```

---

---

> 参考: `references/api-mapping-cheatsheet.md` — 前后端路由/方法/字段映射
> 参考: `references/on-error-captured-checklist.md` — onErrorCaptured 诊断清单
> 参考: `references/mobile-webview-pitfalls.md` — 移动端 WebView 弹窗/剪贴板/定位陷阱
> 参考: `references/vant-toast-purge-20260706.md` — Vant Toast 全量清理 26 文件记录\n> 参考: `references/vue-css-design-system.md` — 全局 CSS 设计系统\n> 参考: `references/fullstack-audit-protocol.md` — 全量审计协议\n> 参考: `references/audit-delegation-pattern.md` — 并行子代理审计方法
```bash
# 后端日志
sudo journalctl -u ttdazi --no-pager -n 30

# 测试API
curl -s http://82.157.202.24/api/health
TOKEN=$(curl -s -X POST http://82.157.202.24/api/user/login \
  -H 'Content-Type: application/json' \
  -d '{"phone":"13800138000","password":"123456"}' | python3.12 -c "import sys,json;print(json.load(sys.stdin)['data']['token'])")

# 数据库检查
cd /opt/ttdazi/backend && python3.12 -c "
from db import get_connection
conn = get_connection()
with conn.cursor() as cur:
    cur.execute('DESCRIBE user')
    for r in cur.fetchall(): print(r)
conn.close()
"

# 前端构建
cd /opt/ttdazi/frontend && npm run build

# 部署
bash /opt/ttdazi/deploy.sh
```

---

## 模式36: 全量后端安全审计

**场景**: 上线前全面检查后端 API 安全、SQL 注入、错误处理。详见 `references/fullstack-audit-protocol.md`。

### 审计流程
1. 列举所有路由 → 检查每个路由的认证装饰器（`@login_required` / `@admin_required`）
2. 全局搜索 `except:` → 改为 `except Exception:` （裸 except 吞掉真实错误）
3. 检查 f-string SQL → 验证只拼接白名单预检字段
4. 检查前端API调用 vs 后端路由 → 交叉验证方法/路径/字段名

### 常见修复
| 问题 | 级别 | 修复 |
|------|------|------|
| 审核/举报路由无 `@admin_required` | 🔴 高危 | 补装饰器 |
| 签到/打卡路由无 `@login_required` | 🔴 高危 | 补装饰器 |
| `except: pass` 吞错误 | 🟡 中危 | `except Exception:` |
| f-string SQL（预检字段） | 🟢 低危 | 验证白名单后无需改 |

## 模式37: 管理后台菜单完整映射 — 用户功能都有管理端

检查用户端的每个功能是否都有对应的管理后台审核/管理页面：

| 用户端 | 管理端 | 管理操作 |
|--------|--------|---------|
| 注册登录 | AdminUsers | 列表/编辑/禁用 |
| 陪玩师入驻 | AdminPlaymates | 审核/上下架 |
| 订单 | AdminOrders | 查看/管理 |
| 评价 | AdminReviews | 评价/投诉处理 |
| 客服 | AdminService | 回复 |
| FAQ | AdminFaq | 类目/回复/审核 |
| 消息 | AdminMessages | 查看/发送通知 |
| 实名认证 | AdminVerify | 审核通过/拒绝 |
| 提现 | AdminWithdrawals | 审核通/拒 |
| 财务 | AdminFinance | 流水 |
| 设置 | AdminConfig | 51项配置 |
| 内容 | AdminContent | Banner/游戏CRUD |
| 优惠券 | AdminCoupons | 创建/记录 |
| 协议 | AdminAgreements | 编辑 |
- 意见反馈 | AdminFeedback | 查看/回复 |

### 审核通知全覆盖
- 实名认证\\陪玩师审核\\提现审核 通过/拒绝 → 通知用户
- 订单取消 → 通知陪玩师

---

## 模式38: 全量前端用户端审计流程

**场景**: 上线前逐页检查所有用户端页面的模板渲染、数据显示、交互逻辑、样式统一性。

### 审计维度（每个页面按此清单逐项检查）

```
① 模板undefined变量 — info.value?.xxx 但 API 返回扁平对象无 .value
② 数据显示条件 — v-if/v-else 分支覆盖充分？避免 NaN/null 显示
③ 空catch/静默失败 — catch{} / catch(e){console.error(e)} 无用户提示？
④ safeToast/safeConfirm 使用 — 所有catch是否都调了safeToast？确认弹窗是否用safeConfirm？
⑤ 全局样式一致性 — 是否使用 .page / .header-bar / .card-3d / .menu-item-3d？
⑥ 布局一致性 — 与Profile.vue基准对比：header-bar颜色、卡片间距、按钮风格
⑦ localStorage解析安全 — JSON.parse 是否在 try/catch 内？
⑧ 假值陷阱 — `item.rating || 5` 当rating=0时错误显示5星（应使用 ?? 而非 ||）
```

### 审计扫描命令

```bash
# 1. 全局扫描空catch（无 safeToast/console.error 保护的）
grep -rn "catch\s*{" frontend/src/views/ --include="*.vue" | grep -v "safeToast\|console\.error\|console\.warn"

# 2. 全局扫描完全空的 catch {}
grep -rn "catch\s*{}" frontend/src/views/ --include="*.vue"

# 3. 检查全局样式使用率
grep -rn 'class="page"' frontend/src/views/*.vue | wc -l
grep -rn 'class=".*header-bar"' frontend/src/views/*.vue | wc -l
grep -rn 'class="card-3d"' frontend/src/views/*.vue | wc -l

# 4. 检查还有哪些页面用自定义样式类代替全局样式
grep -l 'gradient-header\|page-container\|page-header\|settings-header\|verify-page\|wx-reg-page\|email-reg-page' frontend/src/views/*.vue

# 5. 检查 rating 假值陷阱（ || 而非 ?? ）
grep -rn 'rating ||' frontend/src/views/ --include="*.vue"

# 6. 检查 localStorage 解析安全
grep -rn 'JSON.parse.*localStorage' frontend/src/views/ --include="*.vue" | grep -v 'try'
```

### 常见问题模板

| 问题类别 | 严重度 | 修复模板 |
|----------|--------|---------|
| 空catch吞错误 | 🔴 高 | `catch{}` → `catch(e){ safeToast(e?.message \|\| '操作失败'); console.warn(e) }` |
| 不使用全局样式类 | 🔴 高 | 自定`.gradient-header`→`.header-bar`，`.page-wrapper`→`.page` |
| rating假值陷阱 | 🟡 中 | `item.rating \|\| 5` → `(item.rating ?? 5)` 或 `(item.rating >= 0 ? item.rating : 5)` |
| localStorage无try/catch | 🔴 高 | `JSON.parse(str)` → `try { JSON.parse(str) } catch { return {} }` |
| 自定义DOM加载替代 | 🟡 中 | `document.createElement` → Vue响应式 `ref(false)` + `v-if="overlay"` |

### ⚠️ 陷阱：`||` 和 `??` 的假值行为差异

```js
score || '后备'     // 跳过的值: '', 0, null, undefined, false, NaN  ← 危险！0也被跳过
score ?? '后备'     // 跳过的值: null, undefined  ← 数字推荐用 ??
```

**规则**:
- 数字用 `??`（`score ?? 5` 保留 0）
- 字符串用 `||`（`nickname || '未登录'`）
- 布尔用 `??`（`isOnline ?? false`）

### 全量审计发现记录

详见 `references/frontend-audit-20260706.md` — 25个页面的逐页问题清单，31处🔴严重问题、22处🟡中等问题。

## 模式55: axios 解包后禁止检查 res.code

**关键陷阱：** `src/api/index.js` 拦截器返回 `res.data.data`（已解包 inner data）。

- API 返回 `{code:0, data:{...}, msg:'ok'}` → 前端 `res = {...}`
- `res.code` 永远为 **undefined**
- `if (!res || res.code !== 0)` → `undefined !== 0` 永远为 `true` → **所有成功请求都被判失败**

```javascript
// ❌ 错误 — 所有成功走向失败分支
const res = await api.post('/companion/register', payload)
if (!res || res.code !== 0) { safeToast(res?.msg || '提交失败'); return }

// ✅ 正确 — 检查业务字段
const res = await api.post('/companion/register', payload)
if (!res || !res.companion_id) { safeToast('提交失败'); return }
```

## 模式59: 省市联动城市选择器（替换扁平城市列表）

**场景**: 把 List.vue/Settings.vue 中简单的硬编码城市列表替换为**先选省份 → 再选城市**的二级联动选择器，覆盖全国 34 个省级行政区 + 300+ 城市。

### 步骤

1. **创建 `src/utils/cities.js`** — 导出省市数据结构 + 工具函数
```javascript
const PROVINCES = [
  { name: '广东省', cities: ['广州市','深圳市','东莞市','佛山市', ...] },
  // ... 34 个省份
]
export default PROVINCES
export function searchCities(keyword) { /* 模糊搜索 */ }
```

2. **模板改造** — 二级联动结构：v-if="!selectedProvince" 显示省份列表，v-else 显示城市列表。每项带 `›` 箭头指示可点击进入下级。

3. **Script 改造** — `import PROVINCES from '@/utils/cities'`，加 `selectedProvince` ref + `currentCities` computed。

4. **CSS 追加** — `.cp-back`（返回按钮）、`.cp-arrow`（箭头指示器）。

### 常见坑
- Settings.vue 的 `@click.self` 必须改为 `closeCityPicker()` 函数（同时重置 province 和 search）
- 从城市页返回省份页时清空 `citySearch`，防止搜索条件残留
- 两级都要有「全部城市」选项放在列表第一项

---

## 模式60: 登录页验证码不显示 — Tab切换未触发 refreshCaptcha

**场景**: 登录页有多个Tab（微信登录/扫码登录/账号密码），切换到"账号密码"Tab时验证码图片空白。

**根因**: `captchaImg` 初始值为 `ref('')`，而 `refreshCaptcha()` 只在组件 `onMounted` 中调用。默认Tab不是"密码"模式时，captcha从未被加载，切换到密码Tab也不会触发加载。

**修复**: 用 `watch` 在切换Tab时自动加载验证码：
```javascript
const loginMode = ref('scan')  // 默认不是 password

// 切换到密码模式时加载验证码
watch(loginMode, (val) => {
  if (val === 'password') refreshCaptcha()
})
```

**检查清单**:
- [ ] 默认Tab不是密码模式时，`refreshCaptcha()` 是否被调用？
- [ ] 切换Tab时是否触发了 captcha 加载？
- [ ] 登录失败后的 `catch` 块是否调了 `refreshCaptcha()` 刷新？
- [ ] 验证码图片是否可点击刷新（`@click="refreshCaptcha"`）？

**影响文件**: Login.vue（ttdazi）

---

## 模式56: 陪玩师订单状态筛选（与用户端不同）

| 状态 | 用户端 | 陪玩师端 |
|------|--------|---------|
| 0 | 待支付 | — |
| 1 | 进行中 | 待接单（已支付） |
| 2 | 待确认 | 进行中 |
| ≥3 | 已完成/已取消 | 已完成/已取消 |

**陪玩师端正确筛选：**
```javascript
pendingOrders.value = list.filter(o => o.status === 1)   // 待接单
activeOrders.value = list.filter(o => o.status === 2)    // 进行中
historyOrders.value = list.filter(o => o.status >= 3)     // 历史
```

**常见错误：** 误将 status=0 作为待接单 → 点了接单按钮后端返回\"状态不正确\"。
