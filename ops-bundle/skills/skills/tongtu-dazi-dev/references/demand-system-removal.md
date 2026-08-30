# 用户发布需求功能移除说明

## 移除内容
- 路由 `/create-demand` → 已从 `router/index.js` 删除
- 组件 `CreateDemand.vue` → 已删除文件
- MyDemands.vue → FAB 发布按钮和 `goCreate` 函数已移除
- 后端 `POST /api/demand/create` → 直接返回 `发布功能已关闭`

## 保留内容
- 需求大厅 (`/demand-hall`) → 保留浏览/接单功能
- 我的需求 (`/my-demands`) → 保留查看/取消/完成功能
- 管理端需求管理 → 保留管理员增删改查

## 文件清单
| 文件 | 操作 |
|------|------|
| `frontend/src/router/index.js` | 删除路由行 |
| `frontend/src/views/CreateDemand.vue` | 删除文件 |
| `frontend/src/views/MyDemands.vue` | 删除 FAB 按钮 + goCreate 函数 |
| `backend/app/demand.py` | `create()` 函数改为返回 fail |

## 用户要求
> 取消用户自己发布需求的页面
