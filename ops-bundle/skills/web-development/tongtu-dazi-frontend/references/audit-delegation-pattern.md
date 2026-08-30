# 全量审计并行子代理模式

## 场景
上线前全面检查前后端所有功能、数据展示、交互逻辑、代码一致性。

## 流程

### 1. 并行派发审计任务
使用 `delegate_task` 并行派发 3 个子代理，分别审计：
- 用户端页面（25+ .vue 文件）
- 管理端页面（19+ .vue 文件）
- 后端 API（27+ .py 文件）

### 2. 每个子代理的审计清单

**用户端页面检查项**：
- 模板变量是否存在未定义（`info.value.xxx` 但 `info` 只是 `res` 无 `.value`）
- 数据显示条件是否缺失（`v-if` 缺了导致 NaN/null 显示）
- `catch(e)` 是否空块吞错误（只有 `catch{}` 或 `catch(e){}` 无 toast）
- `safeToast`/`safeConfirm` 是否正确使用
- 样式是否用了全局类（`.card-3d` / `.menu-item-3d` / `.header-bar` / `.page`）
- 布局一致性（跟 Profile.vue 对比顶栏、卡片、间距、颜色）

**管理端页面检查项**：
- API 调用路径是否跟后端匹配
- 数据列表渲染是否完整（v-for + key + 字段命名）
- 创建/编辑/删除操作是否有确认弹窗或用 safeConfirm
- 表单字段与后端 API 字段名称一致
- 布局是否用 `admin-layout` + `AdminSidebar` + `admin-main` + `margin-left: 220px`
- toast 提示是否完整（成功/失败的提示不为空）
- 分页功能（`v-if="total > pageSize"`）

**后端 API 检查项**：
- 每个路由的返回值格式统一 `{code:0, data:{...}, msg:"..."}`
- 数据返回时字段命名一致性
- 所有用户输入是否经过 sanitize() 或字段白名单
- 每个 create/update 操作是否有字段验证（长度/格式/必填）
- 分页返回格式统一 `{list, total, page, page_size}`
- 错误是否统一用 `fail()` 返回
- 数据库连接是否都在 `try/finally` 中关闭 `conn.close()`
- 审核类操作是否调用了 `audit_log()` 记录日志

### 3. 修复优先级
🔴 高危（必须立即修复）：认证缺失、变量未定义导致崩溃、SQL 注入
🟡 中危（可分批修）：布局不一致、缺少分页、Toast 缺失
🟢 低危（可延后）：样式微调、代码格式化

### 4. 输出格式
每个子代理输出 Markdown 报告，按严重程度标记 🔴🟡🟢。

### 常见修复结果

| 来源 | 典型修复 |
|------|---------|
| 用户端 | 18处空catch→加safeToast, rating=0显示5星bug, 全局样式统一 |
| 管理端 | margin-left:220px, 不匹配API路径/方法, 缺少admin_required, 分页 |
| 后端 | 认证装饰器缺失, 裸except吞错误, 变量未定义, f-string SQL安全检查 |
