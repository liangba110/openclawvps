# 全量备份并对外提供密码保护下载

## 场景

需要把服务器A（42.193.113.230，后端+项目源码+数据库）的完整项目打包，通过服务器B（82.157.202.24，Nginx）提供密码保护的下载链接给运营者。

## 密码保护下载架构

```
┌──────────────┐  auth_basic    ┌──────────────┐
│  浏览器访问   │ ──── 401 ──►  │  Nginx       │
│  backup/     │ ◄── 200 ────  │  dazi.openai2000.cn │
│  (需密码)     │               │              │
└──────────────┘               └──────┬───────┘
                                      │ alias
                                      ▼
                              /data/backups/
                              (备份文件目录)
```

## 密码保护配置步骤

### 1. 创建目录和密码文件

```bash
# Server B 上执行
sudo mkdir -p /etc/nginx/backup-auth /data/backups
sudo chmod 700 /etc/nginx/backup-auth

# 安装 apache2-utils（如未安装）
sudo apt-get install -y apache2-utils

# 创建 htpasswd 文件（用户名 backup，密码自定义）
sudo htpasswd -c -b /etc/nginx/backup-auth/.htpasswd backup 你的密码
sudo chmod 644 /etc/nginx/backup-auth/.htpasswd
sudo chmod 755 /etc/nginx/backup-auth/
```

> ⚠️ **权限陷阱：** Nginx worker 以 `www-data` 用户运行。htpasswd 文件必须让 www-data 可读（644）。同时目录需有 execute 权限（755）让 nginx 能遍历进入。否则访问会返回 500 Internal Server Error，日志显示 `open() ... .htpasswd failed (13: Permission denied)`。

### 2. 在 Nginx 配置中添加 /backup/ 位置

在 dazi.openai2000.cn 的 server block 中（`/etc/nginx/sites-enabled/huizhiyunma`），在 SPA 兜底 `location /` 之前添加：

```nginx
# ──────────── 密码保护的备份下载 ────────────
location /backup/ {
    alias /data/backups/;
    autoindex on;
    auth_basic "备份文件下载";
    auth_basic_user_file /etc/nginx/backup-auth/.htpasswd;
    expires off;
    add_header Cache-Control "no-store";
}
```

### 3. 验证

```bash
sudo nginx -t && sudo nginx -s reload

# 无密码 → 401
curl -sI https://dazi.openai2000.cn/backup/ -o /dev/null -w "HTTP %{http_code}\n"
# 应输出: 401

# 有密码 → 200
curl -sI -u "backup:你的密码" https://dazi.openai2000.cn/backup/ -o /dev/null -w "HTTP %{http_code}\n"
# 应输出: 200
```

### 4. 备份文件同步

将备份文件放到 `/data/backups/` 目录，即可通过密码保护的 URL 访问：

```
https://dazi.openai2000.cn/backup/ttdazi_full_backup_20260719.tar.gz
```

### 5. 自动同步（daily_backup.sh 第8步）

`/opt/ttdazi/daily_backup.sh` 已集成同步逻辑：

```bash
# 打包全量备份并同步到 Server B 密码保护目录
sudo tar -czf "/tmp/ttdazi_full_backup_${TIMESTAMP}.tar.gz" -C "${BACKUP_BASE}" "daily_${TIMESTAMP}/"
scp "/tmp/ttdazi_full_backup_${TIMESTAMP}.tar.gz" ubuntu@${SERVER_B}:/data/backups/
# 保留最近3份，删除旧的
ssh ubuntu@${SERVER_B} "ls -t /data/backups/*.tar.gz | tail -n +4 | xargs -r rm -f"
```

## 旧方案（不再使用）

之前是把备份文件直接 scp 到 `/home/ubuntu/ttdazi-frontend/` 目录（无密码保护），任何人知道 URL 就能下载。已废弃，改用上面带 auth_basic 的方案。

## 步骤

### 1. 导出数据库

从 `config.py` 获取 MySQL 连接信息：

```python
# /opt/ttdazi/backend/config.py
MYSQL_HOST = '127.0.0.1'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'huizhiyun2026'
MYSQL_DB = 'huizhiyun'
```

```bash
mysqldump -h 127.0.0.1 -u root -p'huizhiyun2026' huizhiyun > /tmp/ttdazi_db.sql
```

### 2. 打包项目文件

```bash
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

cd /opt && tar -czf /tmp/ttdazi_full_${TIMESTAMP}.tar.gz \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  ttdazi/ /tmp/ttdazi_db.sql
```

- 排除 `.git`（大）、`node_modules`（可重装）、`__pycache__` / `*.pyc`（缓存）
- 打包后的文件约 99MB（项目核心 ~236MB，压缩后 ~99MB）

### 3. 传输到服务器B的 Web 目录

```bash
scp /tmp/ttdazi_full_${TIMESTAMP}.tar.gz \
    ubuntu@82.157.202.24:/home/ubuntu/ttdazi-frontend/
```

> **⚠️ SCP 超时陷阱：** 99MB 的 scp 传输在 foreground 模式（默认 timeout 120s）会超时断开。必须用 background 模式传输：`terminal(background=true, notify_on_complete=true)`，然后 `process(action='wait', timeout=300)` 等待完成。传输后通过 `curl -sI` 验证 HTTP 可达。
>
> `deploy.sh` 已配置 SSH 密钥认证，可直接 scp。

### 4. 验证可访问

```bash
curl -sI http://82.157.202.24/ttdazi_full_${TIMESTAMP}.tar.gz | head -8
# 期望输出: HTTP/1.1 200 OK
```

### 5. 清理

用户下载完成后删除公开文件：

```bash
ssh ubuntu@82.157.202.24 "rm /home/ubuntu/ttdazi-frontend/ttdazi_full_*.tar.gz"
```

## 备份文件内容清单

```
📁 ttdazi/
   ├── backend/             ← Flask 后端 (Python + 上传图片)
   │   └── app/uploads/     ← 用户上传的身份证等
   ├── frontend/            ← Vue3 前端源码
   ├── deploy/              ← Nginx 部署配置
   ├── deploy.sh            ← 部署脚本
   ├── start.sh             ← 启动脚本
   ├── rotate_admin_path.sh ← 管理后台路径轮换
   └── backup_hermes.sh     ← 备份脚本
📄 ttdazi_db.sql            ← MySQL 完整数据库
```

## 不包含的内容

- `.git` 目录（版本历史，可在目标服务器上 clone 恢复）
- `node_modules/`（在目标服务器上运行 `npm install` 恢复）
- `__pycache__` / `.pyc`（运行时会自动生成）
- Server B 上的 Nginx 配置文件（位于 `/etc/nginx/` 下，需单独备份）
- Systemd 服务文件 `/etc/systemd/system/ttdazi.service`（内容见下文迁移清单）
- SSL 证书 `/etc/nginx/ssl/ttdazi.crt` / `.key`
- Hermes Agent + cron 任务（订单结算/路径轮换/财务备份）
- Python pip 包（需 `pip install` 恢复）
- MySQL 服务本身（需先装 mysql-server）

## 完整迁移到新服务器清单

新服务器（合二为一架构）部署步骤：

```bash
# 1️⃣ 解压备份
tar -xzf ttdazi_full_*.tar.gz -C /opt/

# 2️⃣ 装 MySQL + 导入
sudo apt install -y mysql-server
mysql -u root < /tmp/ttdazi_db.sql
# 如 root 密码不同，先 CREATE DATABASE + 导入

# 3️⃣ 装 Python 依赖
sudo apt install -y python3-pip python3-venv python3-pil
python3 -m venv /opt/ttdazi/venv
source /opt/ttdazi/venv/bin/activate
pip install flask flask-REDACTED gunicorn PyMySQL Pillow requests flask-REDACTED

# 4️⃣ 创建 systemd 服务
cat > /etc/systemd/system/ttdazi.service << 'SERVICEEOF'
[Unit]
Description=同途搭子 游戏陪玩服务
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ttdazi/backend
ExecStart=/opt/ttdazi/venv/bin/gunicorn main:app -b 0.0.0.0:5002 -w 2 --log-level warning --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF
systemctl daemon-reload && systemctl enable --now ttdazi

# 5️⃣ 装 Node.js + 构建前端
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
sudo apt install -y nodejs
cd /opt/ttdazi/frontend && npm install && npm run build

# 6️⃣ 装 Nginx + 配置代理
sudo apt install -y nginx
# 静态文件服务 + API 反向代理
cat > /etc/nginx/sites-enabled/ttdazi << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    root /opt/ttdazi/frontend/dist;
    index index.html;

    # 静态文件
    location / {
        try_files $uri $uri/ /index.html;
    }
    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    # 上传文件
    location /uploads/ {
        proxy_pass http://127.0.0.1:5002;
    }
}
NGINXEOF
nginx -t && systemctl reload nginx

# 7️⃣ 恢复 cron 定时任务
# 订单结算（每5分钟）
# 管理路径轮换（每天3点）
# 财务备份（每天8/14/22点）
# 管理路径推送（每天7点）
```

## 静态文件独立迁移注意事项

如果只迁移前端构建产物（`dist/` 或 `ttdazi-frontend/` 目录）到新服务器：

**✅ 能工作的：** 页面渲染（HTML/CSS/JS 是纯静态的）、头像（在备份内）、favicon/logo

**❌ 不能工作的：** 登录注册、订单、消息、私聊、需求、充值等所有动态功能

**原因：** 前端 axios 使用 `baseURL: "/api"`（同域），所有 API 调用都走当前服务器。需要在新服务器上配 Nginx 反向代理：

```nginx
location / {
    root /path/to/ttdazi-frontend;
    try_files $uri $uri/ /index.html;
}
location /api/ {
    proxy_pass http://42.193.113.230:5002;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```
