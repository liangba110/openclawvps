# 同途搭子 后端 API 速查

## 路由前缀
所有 API 在 `/api/` 下，Nginx 代理到服务器A:5002。

## 蓝图路由表

| 蓝图 | 前缀 | 文件 | 关键端点 |
|------|------|------|---------|
| `user` | `/api/user/` | `app/user.py` | login, register, profile, update |
| `game` | `/api/game/` | `app/game.py` | list, detail |
| `companion` | `/api/companion/` | `app/companion.py` | list, detail, register, photos/upload |
| `order` | `/api/order/` | `app/order.py` | create, list |
| `admin` | `/api/admin/` | `app/admin.py` | login, users, playmates, orders, reviews, toggle |
| `cs` | `/api/cs/` | `app/customer_service.py` | send, history, faq, admin/users, admin/conversation, admin/reply, admin/faq/* |
| `config` | `/api/config/` | `app/config_api.py` | list, admin/list, admin/save |
| `coupon` | `/api/coupon/` | `app/coupon.py` | admin/list, admin/create |
| `agreement` | `/api/agreement/` | `app/agreement.py` | admin/list, admin/save |
| `review` | `/api/review/` | `app/review.py` | - |
| `fav` | `/api/fav/` | `app/favorite.py` | - |
| `message` | `/api/message/` | `app/message.py` | - |
| `playmate` | `/api/playmate/` | `app/playmate_api.py` | - |
| `attendance` | `/api/attendance/` | `app/attendance.py` | - |
| `payment` | `/api/payment/` | `app/payment.py` | - |
| `statistics` | `/api/statistics/` | `app/statistics.py` | - |

## 管理端页面路由

| 路由 | 组件 | 功能 |
|------|------|------|
| `/admin/` | AdminDashboard | 仪表盘 |
| `/admin/users` | AdminUsers | 用户管理 |
| `/admin/playmates` | AdminPlaymates | 陪玩师管理 |
| `/admin/orders` | AdminOrders | 订单管理 |
| `/admin/content` | AdminContent | 内容管理 |
| `/admin/reviews` | AdminReviews | 评价管理 |
| `/admin/withdrawals` | AdminWithdrawals | 提现审核 |
| `/admin/service` | AdminService | 客服消息（3s轮询） |
| `/admin/faq` | AdminFaq | FAQ 学习（审核/采纳） |
| `/admin/config` | AdminConfig | 系统设置（6大类22项） |
| `/admin/coupons` | AdminCoupons | 优惠券管理 |
| `/admin/agreements` | AdminAgreements | 协议管理 |

## 下载页
- `/download` — Download.vue，密码验证后下载加密 ZIP

## FAQ 系统
- 静态 10组关键词 + 动态学习（faq_log 表）
- 未匹配问题自动记录 + MD5 去重
- 7大类目 18 子类自动归类
- 管理端审核采纳后加入匹配引擎
- 前端分类折叠面板
