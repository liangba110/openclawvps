# 管理端 Bug 模式（子代理审计发现）

## 1. 缺少 `safeToast` / `safeConfirm` 导入

**受影响文件**：AdminMonitor.vue, AdminWithdrawals.vue, AdminPlaymates.vue

**症状**：运行时崩溃 `safeToast is not defined` / `safeConfirm is not defined`

**根因**：页面调用了 `safeToast()` 或 `safeConfirm()` 但 `<script setup>` 中未导入。

**修复检查清单**：
```
AdminMonitor.vue    → import safeToast from '@/utils/toast'
AdminWithdrawals.vue → import safeConfirm from '@/utils/confirm'
```

**所有新建管理页面**必须检查以下导入是否存在：
```js
import safeToast from '@/utils/toast'
import safeConfirm from '@/utils/confirm'
import api from '@/api'
```

## 2. AdminPlaymates 用 `safeToast` 代替 `safeConfirm`

**症状**：审核/上下架操作直接执行，无用户确认弹窗（safeToast 自动消失）。

**根因**：`safeToast('确定通过...')` 本应用 `safeConfirm` 弹出「确认/取消」对话框，但用了 `safeToast`（纯提示）。

**修复**：
```js
// ❌ 错误
safeToast(`确定${s}该陪玩师的入驻申请？`)

// ✅ 正确
const ok = await safeConfirm(`确定${s}该陪玩师的入驻申请？`)
if (!ok) return
```

**注意**：`safeConfirm` 是 async 函数，调用函数也必须是 async。

## 3. AdminDashboard 硬编码管理路径

**症状**：管理员路径轮换后，仪表盘快捷操作和退出按钮跳转到旧路径页面（404）。

**受影响位置**：
- 4 个快捷操作 link（users/playmates/orders/reviews）
- 退出登录 redirect

**修复**：
```js
const ap = "sessionStorage.getItem('admin_route_path') || 'op-ztHWaT-0706'"
// 用模板字符串拼接
router.push('/' + (sessionStorage.getItem('admin_route_path') || 'op-ztHWaT-0706') + '/users')
```

**全站搜索**：`/op-ztHWaT-0706` 出现的地方都必须改为动态路径。

## 4. 实名认证提交后管理后台不显示

**症状**：用户提交实名认证后，管理员后台「实名审核」页面始终为空。

**根因**：两套数据表不同步：
- 用户提交 `POST /api/user/verify` → 只更新 `user` 表（`verify_status=2`）
- 管理员查询 `GET /api/admin/verifies` → 查询 `verify_application` 表
- 两表之间无数据同步

**修复**：`user.py` 的 `verify()` 函数必须同时插入 `verify_application`：
```python
# user.py - def verify():
cur.execute(
    "INSERT INTO verify_application (user_id, real_name, id_card, status) VALUES (%s, %s, %s, 0)",
    (user_id, real_name, id_number)
)
cur.execute(
    "UPDATE user SET real_name=%s, id_number=%s, verify_status=2 WHERE id=%s",
    (real_name, id_number, user_id)
)
```

**注意**：admin.py 的 approve/reject 已正确同步 `verify_application` → `user` 表（通过 `SELECT user_id FROM verify_application` 后 UPDATE user）。

## 5. 全局 CSS `.admin-main` 样式泄露

**症状**：所有管理页面内容区比预期多偏移 220px。

**根因**：`frontend/src/assets/global.css` 中有 `.admin-main { margin-left: 220px; ... }` 全局规则。

**排查**：
```bash
# 源码检查
grep "margin-left" /opt/ttdazi/frontend/src/assets/global.css
# 编译产物检查
grep "margin-left" /opt/ttdazi/frontend/dist/assets/style-*.css | grep admin
```

**修复**：从 `global.css` 中删除 `margin-left: 220px`。每个管理页面的 scoped style 用 `flex: 1; padding: 20px` 控制。

**标准管理页面布局 CSS**：
```css
.admin-layout { display: flex; min-height: 100vh; background: #f5f6fa; }
.admin-main { flex: 1; padding: 20px; }
```

## 6. 构建失败后部署误报成功

**症状**：`deploy.sh` 输出 `✅ 前端编译完成` 但实际构建失败。

**根因**：`AdminConfig.vue` 中 `patch` 工具残留的孤儿 CSS 行导致 PostCSS 解析错误 `Unexpected }`，但 vite 退出码可能仍为 0。

**排查**：
```bash
# 查看完整构建输出末尾
npm run build 2>&1 | tail -10
# 寻找 "✓ built in Xs" 或 "error during build:"
```

**预防**：每次部署前单独运行 `npm run build 2>&1 | grep -E "✓ built|error during"` 确认构建状态。
