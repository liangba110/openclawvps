# 汇智云码科技官网 (openai2000.cn) 管理后台

## 概述

`openai2000.cn` 是公司展示站（汇智云码科技），**独立于同途搭子系统**，共享 Server B 的 Nginx 但使用不同的后端和数据库。

## 架构

| 组件 | 详情 |
|------|------|
| 域名 | https://openai2000.cn |
| 管理后台 | https://openai2000.cn/admin |
| 后端 | Node.js，端口 8081（Server B） |
| 进程 | `node /data/web/` (pid 1589) |
| 数据库 | `huizhiyunma_db`（MySQL，同 Server A） |
| 数据库用户 | `huizhiyunma` |
| 数据库密码 | `HuiZhiYunMa@2026` |
| 前端文件 | `/data/web/huizhiyunma/frontend/` (Server B) |
| 后端源码 | `/data/web/huizhiyunma/backend/` (Server B) |
| 上传目录 | `/data/web/huizhiyunma/uploads/` (Server B) |

## 管理员凭证

| 字段 | 值 |
|------|:---:|
| 管理后台URL | https://openai2000.cn/admin |
| 账号 | `admin` |
| 密码 | `Hzym@2026!Secure` |

凭证定义在 Server B `/data/web/huizhiyunma/backend/.env`：
```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Hzym@2026!Secure
```

## 数据库

独立数据库 `huizhiyunma_db`，不跟同途搭子共用 `huizhiyun` 库。

```bash
mysql -uhuizhiyunma -p'HuiZhiYunMa@2026' huizhiyunma_db -e "SHOW TABLES;"
```

## Nginx 注意

huizhiyunma 站点的 Nginx 配置中 `server_name openai2000.cn www.openai2000.cn` 同时存在 `location /api/ { proxy_pass http://127.0.0.1:8081; }` 和 `server_name dazi.openai2000.cn` 下的 `location /api/ { proxy_pass http://42.193.113.230:5002; }`。两个 server block 通过 SNI 区分，不会混淆。

## 常见操作

### 查看服务状态
```bash
# Server B 上
ss -tlnp | grep 8081
ps aux | grep "node /data/web"
```

### 重启后端
```bash
ssh ubuntu@82.157.202.24 "pm2 restart huizhiyunma 2>/dev/null || (cd /data/web/huizhiyunma/backend && kill \$(cat /tmp/huizhiyunma.pid 2>/dev/null) 2>/dev/null; node server.js &)"
```
