# 同途搭子 项目架构速查

## 服务器拓扑
```
用户 → 82.157.202.24:80 (Nginx, Server B)
         ├── /api/* → proxy → 42.193.113.230:5002 (Flask+gunicorn, Server A)
         ├── /uploads/* → proxy → 42.193.113.230:5002 (Flask send_from_directory)
         └── /* → /home/ubuntu/ttdazi-frontend/ (SPA)
```

## 文件路径
- 前端: `/opt/ttdazi/frontend/src/`
- 后端: `/opt/ttdazi/backend/`
- 部署: `/opt/ttdazi/deploy.sh`
- 备份: `/tmp/ttdazi_backup_*`
- Nginx(ServerB): `/etc/nginx/sites-enabled/ttdazi`

## 已去Vant化的页面
- Login.vue — 按钮loading态
- Orders.vue — 自定义遮罩
- Settings.vue — 自实现弹窗
- Profile.vue — 自定义遮罩
- Verification.vue — 自定义遮罩
- CompanionRegister.vue — safeToast替代
- Favorites.vue — safeToast替代

## 已知后端API
- `POST /api/user/login` — 登录
- `POST /api/user/register` — 注册
- `GET /api/user/profile` — 用户信息
- `PUT /api/user/update` — 更新资料(昵称/gender/城市)
- `POST /api/user/avatar/upload` — 头像上传
- `POST /api/user/verify` — 实名认证
- `GET /api/order/list` — 订单列表
- `GET /api/favorite/list` — 收藏列表
- `GET /api/companion/list` — 陪玩师列表
- `POST /api/companion/register` — 注册陪玩师
- `POST /api/companion/photos/upload` — 生活照上传

## 数据库关键字段
- `user.gender` — TINYINT: 0=secret, 1=male, 2=female
- `user.verify_status` — 0=未认证, 1=待审核, 2=已认证

## Git
- 仓库: `/opt/ttdazi/.git`
- 用户偏好每次部署后提交
