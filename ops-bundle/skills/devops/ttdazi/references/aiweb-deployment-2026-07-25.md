# AI建站系统 (aiweb) 部署架构 — 新项目隔离模板

## 服务架构

```
用户 → https://aiweb.openai2000.cn (Server B Nginx:443)
        ├── 前端静态文件 (/var/www/aiweb/frontend/dist/)
        └── /api/* → Server A:5003 (gunicorn)
```

## 技术栈

| 组件 | 选型 |
|:----|:------|
| 前端 | Vue 3 + Vite + Vue Router (Hash模式) |
| 后端 | Flask + PyMySQL + gunicorn |
| 数据库 | MySQL 8.0 (独立 `aiweb` 库) |
| 服务器A | 42.193.113.230 (后端+数据库) |
| 服务器B | 82.157.202.24 (Nginx反代+前端) |
| API通道 | Server B Nginx → Server A:5003（注意 iptables / 云安全组需放行端口）|

## 关键路径

| 项目 | 路径/值 |
|:----|:---------|
| 代码 | `/opt/aiweb/` |
| 后端 | `/opt/aiweb/backend/` (Flask, port 5003) |
| Python | `/opt/aiweb/venv/` (独立虚拟环境) |
| 前端 | `/opt/aiweb/frontend/` (Vue3) |
| 数据库 | `aiweb` (独立数据库，7张表) |
| systemd | `aiweb.service` |
| 部署脚本 | `bash /opt/aiweb/deploy.sh` |
| Nginx配置 | `/etc/nginx/sites-available/aiweb` |
| SSL | Let's Encrypt (`aiweb.openai2000.cn`) |
| 备份 | 每日3:30，保留90天，`/root/data/disk/aiweb/` |

## 微信扫码登录（从 ttdazi 复制）

扫码登录功能从 ttdazi 项目完整复制后适配：
- 后端: `scan_login.py` 蓝图，注册于 `/api/login/scan/*`
- 前端: `Login.vue` 增加「扫码登录」Tab，使用 `qrcode` 包
- 前端: `ScanConfirm.vue` 手机确认页

适配要点：
- QR_URL 改为 `https://aiweb.openai2000.cn/#/scan-confirm`
- API 端点从 ttdazi 的 `/login/scan/create` 改为同路径
- 响应格式适配 aiweb 的标准 `{code, data, msg}` 结构
