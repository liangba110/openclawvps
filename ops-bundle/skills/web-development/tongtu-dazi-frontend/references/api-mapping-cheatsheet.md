# 同途搭子 前后端API映射速查

## 用户端
| 功能 | 后端路由 |
|------|---------|
| 登录 | POST /api/user/login |
| 注册 | POST /api/user/register |
| 资料 | GET /api/user/profile |
| 修改 | PUT /api/user/update |
| 头像 | POST /api/user/avatar/upload (FormData) |
| 认证 | POST /api/user/verify |

## 陪玩师
| 功能 | 后端路由 |
|------|---------|
| 注册 | POST /api/companion/register (games[{game_id,price_1h}]) |
| 详情 | GET /api/companion/detail?id= (含games[],life_photos[]) |
| 列表 | GET /api/companion/list (需c.is_online=1) |
| 照片 | POST /api/companion/photos/upload (FormData,需companion已存在) |

## 管理端
| 功能 | 后端路由 | 方法 |
|------|---------|------|
| 登录 | /api/admin/login | POST |
| 陪玩师列表 | /api/admin/playmates | GET |
| 审核 | /api/admin/playmate/:id/audit | PUT+POST |
| 上下架 | /api/admin/playmate/:id/toggle | PUT |

## DB类型陷阱
| 表 | 列 | 类型 | 前端值 → 后端映射 |
|----|----|------|------|
| user | gender | TINYINT | 'male':1, 'female':2, 'secret':0 |
| companion | status | TINYINT | 0=待审, 1=通过, 2=拒绝 |
| companion | is_online | TINYINT | 0=下架, 1=上架 |
