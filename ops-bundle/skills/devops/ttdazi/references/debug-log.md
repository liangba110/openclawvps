# 同途搭子 调试记录

## 2026-07-04 全线 Bug 修复

### Toast 空白问题（跨多个页面）

**链**: Login→api/index.js→toast.js
- toast.js: `safeToast` 返回 Promise，20ms 延迟渲染，先 remove 旧 DOM
- api/index.js: 后端空 msg → '操作异常'兜底，HTTP 401 补弹窗
- Login.vue: 移除 Vant loading，改用按钮 `loading` 状态

### 页面渲染错误（"建议刷新"）

**链**: App.vue `onErrorCaptured` 捕获子组件错误
- Orders.vue: `order.companion.nickname` → `order.nickname`（API 返回扁平结构）
- Settings.vue: `user` 普通函数 → `computed()` + `userVer` cache-buster
- Favorites.vue: `item.rating.toFixed(1)` → `typeof === 'number'` 守卫
- List.vue: `renderStars(score)` → `Number(score)||0` 防 NaN
- Detail.vue: `'★'.repeat(rv.rating)` → `rv.rating||0` 守卫
- CompanionRegister.vue: `url.startsWith('http')` → `typeof === 'string'` 守卫

### 管理端问题

- 陪玩师审核: `audit_status` int→string 映射，action/status 字段兼容，PUT+POST 双方法
- 上下架: URL `toggle-online`→`toggle`，方法 POST→PUT，字段 status→is_online
- 下架仍显示: 3 处 SQL 补充 `c.is_online=1` 过滤

### 后端崩溃

- gender 字段: MySQL TINYINT，后端存字符串 → 1366 DataError → 映射层修复
- companion 生活照上传: `/var/www` 无权限 → `app/uploads/life_photos`
- companion 双重 conn.close(): 第一个 finally 关闭 → 后续复用报 Already closed → 新连接

### 新功能

- 多游戏认证: 新建 `companion_game` 表，register 接受 `game_ids[]`
- 生活照相册: Detail.vue 新增 3 列网格展示
