---
name: admin-mirror-rule
description: 前端功能必须有对应的管理后台页面（管理/修改/审核）
trigger: 当开发新功能、新模块时，必须同步创建管理后台的对应页面
---

# 管理后台镜像规则

## 核心原则
**前端所有开发的功能，管理后台必须有对应的管理、修改、审核页面。**

## 对照清单

| 前端页面/功能 | 管理后台必须提供 | 同途搭子实战页 |
|--------------|----------------|---------------|
| 用户注册/登录 | 用户管理列表、编辑、封禁/解封 | AdminUsers.vue |
| 陪玩师注册/展示 | 陪玩师审核、上下架、编辑资料 | AdminPlaymates.vue + AdminPlaymateDetail.vue |
| 订单创建/支付 | 订单列表、详情、退款/取消 | AdminOrders.vue |
| 评价发表 | 评价管理、投诉处理、屏蔽/删除 | AdminReviews.vue |
| 客服咨询 | 客服消息列表、回复、FAQ管理 | AdminService.vue + AdminFaq.vue |
| 消息通知 | 后台查看用户通知记录 | AdminMessages.vue |
| 实名认证 | 认证审核（通过/拒绝）、查看材料 | AdminVerify.vue |
| 提现申请 | 提现审核（通过/拒绝）、记录查询 | AdminWithdrawals.vue |
| 财务流水 | 消费明细、充值明细、收支统计 | AdminFinance.vue |
| 系统设置 | 配置管理页面（所有参数可编辑） | AdminConfig.vue |
| 内容展示（Banner/游戏等） | 内容管理（增删改查） | AdminContent.vue |
| 优惠券 | 优惠券创建、发放、管理 | AdminCoupons.vue |
| 协议/政策 | 协议管理（编辑/版本） | AdminAgreements.vue |
| 手机号/邮箱绑定 | 后台绑定/解绑、查询绑定状态 | AdminUsers.vue |
| 安全监控/异常检测 | IP封禁、异常登录、安全告警 | AdminMonitor.vue |
| 意见反馈 | 反馈列表查看、回复、历史查询 | AdminFeedback.vue |
| 代码在线编辑 | 读写文件、保存、构建 | AdminCode.vue |

## 开发流程
1. 设计前端功能时，同步设计管理后台页面
2. 前端 API 完成后，立即补充管理端 API（admin.py 统一管理）
3. 管理端必须有：**列表查看 → 详情 → 修改 → 审核/操作** 完整链路
4. 管理端侧栏菜单同步更新入口（AdminSidebar.vue）

## 自检流程（开发完成后必须执行）
```
1. 列出所有前端路由 → src/router/index.js
2. 列出所有管理端路由 → 同上文件中 /PRIVATE_PATH/ 路径（非硬编码）
3. 列出所有管理端 API → grep @admin_bp.route app/admin.py
4. 逐项对比，标记缺失
5. 侧栏是否有入口 → grep push AdminSidebar.vue
6. 新页面是否继承 AdminSidebar → 检查 admin-layout 包裹
7. @admin_required 覆盖检查 → 所有 admin_bp 路由必须有此装饰器
   扫描命令: grep -B1 '@admin_bp.route' app/admin.py | grep -E '^def |@admin' | grep -v '@admin_required'
8. user_operate ALLOWED 循环检查 → 确认遍历 ALLOWED 全量字段而非只读 status/role
```

## 常见缺失项
这些功能容易漏掉管理端，创建前端功能时特别注意：
| 前端功能 | 管理端页面 | 
|----------|-----------|
| 实名认证提交 | 审核独立页(AdminVerify.vue) |
| 消息通知 | 查看+发送通知(AdminMessages.vue) |
| 邮箱绑定状态 | 用户列表显示 email 字段 |
| 手机绑定状态 | 用户列表显示 phone_bound 字段 |
| 用户封禁 | 用户管理封禁/解封按钮 |
| 安全监控 + 登录日志 | AdminMonitor.vue（侧栏入口易漏） |
| 绑定邮箱/手机功能 | 用户端设置页实现，管理端只需查看 |
| 主动推送通知 | AdminMessages.vue 发送通知弹窗 |
| 优惠券领取记录 | AdminCoupons.vue 查看谁领了券、是否使用 |
| 登录日志查看 | AdminMonitor.vue 登录日志Tab |

## 审计通过条件
新功能上线前必须通过以下检查：
1. ✅ 管理端有对应列表页（显示所有数据）
2. ✅ 列表每项可编辑/操作（修改/审核/删除至少其一）
3. ✅ 侧栏有菜单入口
4. ✅ 页面使用 admin-layout + AdminSidebar 统一布局
5. ✅ admin-main 有 margin-left: 220px（侧栏固定定位时内容被遮挡）
6. ✅ API 路由在 admin.py 中，使用 @admin_required
7. ✅ 数据库字段同步：login SELECT 和 /user/info 响应都包含新字段

## 注意事项
- 管理端 API 统一放在 `admin.py` 中，使用 `@admin_required` 装饰器
- 数据库字段变更后，需同步更新 login 查询 SELECT 和 /user/info 响应
- 用户端localStorage用户信息（`user`对象）需通过 login 响应或 /user/info 刷新
- 新功能的路由、侧栏、后端API三者必须同步添加，缺一不可
- **新管理页必须使用统一布局**：`<div class="admin-layout"><AdminSidebar /><div class="admin-main">内容</div></div>`，否则侧栏不显示
- **侧栏路径必须匹配真实路由**：`@click="$router.push('/{CURRENT_PATH}/page')"` 确认 `CURRENT_PATH` 与 DB 中 `admin_route.path` 一致（每日轮换时自动更新）

## 常见陷阱

### user_operate 只更新了 status/role（缺少 ALLOWED 全量字段循环）

**症状：** 管理端用户操作返回"没有允许更新的字段"，明明传了正确参数。

**根因：** PUT 路由只处理 `if 'status' in data` 和 `if 'role' in data`，没有遍历 ALLOWED 集合中的 nickname/city/email 等。

**修复模式：** 用 `for key in ALLOWED` 循环替代逐个 `if key in data`。

**预防：** 任何 `@admin_required` 的 `PUT /api/admin/user/<id>` 中，只应有**一个** `ALLOWED` 定义 + **一个** `safe_updates` + **一个** `if not safe_updates`。出现多个 ALLOWED 赋值就是 copy-paste 污染。

### `@admin_required` 遗漏

**症状：** 管理端接口可被任意用户调用。

**扫描：**
```
grep -B1 '@admin_bp.route' app/admin.py | grep -E '^def |@admin' | grep -v '@admin_required'
```
输出任何行即缺失。本期发现 3 个（security-alert, recent-anomalies, ban-ip）。

## 例外
- 纯展示类页面（关于我们、帮助中心、团队看板）不需要管理端
- 但其中可编辑的内容（如平台信息）仍需管理后台配置页
