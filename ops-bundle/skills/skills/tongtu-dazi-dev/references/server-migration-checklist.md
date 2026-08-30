# 同途搭子 全量服务器迁移检查清单

## 架构回顾

| 服务器 | IP | 角色 | 关键端口 |
|--------|------|------|---------|
| Server A | 42.193.113.230 | Flask 后端 + MySQL | gunicorn 5002, MySQL 3306 |
| Server B | 82.157.202.24 | Nginx 反代 + 前端静态 + OpenClaw | Nginx 80/443, OpenClaw 38598 |

## 🔑 SSH 访问 Server A

Server A 只允许 SSH 密钥登录（`PubkeyAuthentication only`）。
```bash
# 在本机添加公钥到 Server A 的 ~/.ssh/authorized_keys
ssh-copy-id -i ~/.ssh/id_ed25519.pub ubuntu@42.193.113.230
```
已知密码作为备用: `wll16562341@`（需先改 PasswordAuthentication）

## 🗄️ MySQL 凭证

MySQL root 密码: `/opt/ttdazi/backend/app/backup_api.py` 中读取
```python
db_pass = os.environ.get('MYSQL_PASSWORD', 'huizhiyun2026')
```
- 数据库名: `huizhiyun`（41 张表）
- 导出命令: `MYSQL_PWD='huizhiyun2026' mysqldump -h127.0.0.1 -uroot --databases huizhiyun --routines --triggers --single-transaction`

## ⚠️ 已知陷阱

1. **Server B Nginx 的 ttdazi 站点未启用** — `/etc/nginx/sites-available/ttdazi` 存在但无 symlink 到 `sites-enabled/`
   修复: `sudo ln -s /etc/nginx/sites-available/ttdazi /etc/nginx/sites-enabled/ttdazi && nginx -t && systemctl reload nginx`
2. **Nginx 站点 ttdazi 的 proxy_pass 指向 Server A 外网 IP** — 合并到单机时必须改 `http://127.0.0.1:5002`
3. **vsftpd 密码认证失败** — Ubuntu 云服务器默认 SSH 密钥认证，ubuntu 用户可能无有效密码。vsftpd 需要 PAM 认证，设密码：`sudo passwd ubuntu`
4. **iptables 默认封闭所有端口** — 只开放了 22 和 5002（仅限 Server B）。用 HTTP 下载备份包时需：`sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT`

## 📦 完整备份清单（2026-07-13 实践版）

### 备份目录结构
```
backup_YYYYMMDD_HHMMSS/
├── ttdazi_database.sql              — MySQL完整导出(41张表)
├── ttdazi_program.tar.gz            — 项目源码(/opt/ttdazi/)
├── ttdazi_static_dist.tar.gz        — 前端编译产物(dist/)
├── ttdazi_uploads.tar.gz            — 用户上传文件(uploads/)
├── system_configs.tar.gz            — Systemd服务+MySQL配置
├── env_configs.tar.gz               — 环境变量+bashrc
├── requirements.txt                 — Python依赖清单(pip3 freeze)
├── crontab_root.txt                 — root定时任务
├── crontab_ubuntu.txt               — ubuntu定时任务
├── 迁移到新服务器操作手册.txt         — 开箱即用的迁移指南
└── server_b/                        — 服务器B专属配置
    ├── nginx_ssl_backup.tar.gz      — Nginx全配置+SSL证书
    ├── ttdazi_frontend_dist.tar.gz  — Server B前端静态文件
    ├── openclaw_config.tar.gz       — OpenClaw机器人配置
    ├── deploy.sh                    — 一键部署脚本
    ├── monitor.sh                   — 资源监控脚本
    ├── rotate_admin_path.sh         — 后台路径轮换脚本
    └── backup_hermes.sh             — Hermes备份脚本
```

### ✅ 完整备份步骤
```bash
# ===== Server A (本地) =====
MYSQL_PWD='huizhiyun2026' mysqldump -h127.0.0.1 -uroot --databases huizhiyun --routines --triggers --single-transaction > ttdazi_database.sql
tar -czf ttdazi_program.tar.gz -C /opt ttdazi/
tar -czf ttdazi_static_dist.tar.gz -C /opt/ttdazi/frontend dist/
tar -czf ttdazi_uploads.tar.gz -C /opt/ttdazi/backend app/uploads/
tar -czf system_configs.tar.gz /etc/systemd/system/ttdazi.service /etc/mysql/
pip3 freeze > requirements.txt

# ===== Server B (SSH 远程) =====
ssh ubuntu@82.157.202.24 "tar -czf /tmp/nginx_ssl_backup.tar.gz /etc/nginx/sites-available/ttdazi /etc/nginx/nginx.conf /etc/nginx/sites-enabled/ /etc/nginx/ssl/"
scp ubuntu@82.157.202.24:/tmp/nginx_ssl_backup.tar.gz server_b/
ssh ubuntu@82.157.202.24 "tar -czf /tmp/ttdazi_frontend_dist.tar.gz -C /home/ubuntu ttdazi-frontend/"
scp ubuntu@82.157.202.24:/tmp/ttdazi_frontend_dist.tar.gz server_b/

# ===== 生成迁移手册 =====
# 随备份生成 迁移到新服务器操作手册.txt
```

## 📦 打包与传输

备份到 Server A 数据盘后，按以下步骤打包并传输到新服务器：

### 打包成一个文件
```bash
# 在 Server A 上执行
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/ttdazi_full_backup_${TIMESTAMP}.tar.gz"
sudo tar -czf "$BACKUP_FILE" -C /root/data/disk backup_*/
sudo chown ubuntu:ubuntu "$BACKUP_FILE"
```

### 传输方式

**方式1: Python HTTP 服务器（推荐，最简单）**
```bash
# Server A 上启动
cd /tmp
python3 -m http.server 8080 &

# 新服务器上下载
curl -O http://42.193.113.230:8080/ttdazi_full_backup_*.tar.gz
```
> ⚠️ 可能需要放行 iptables: `sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT`

**方式2: scp 直接传输**
```bash
scp ubuntu@42.193.113.230:/tmp/ttdazi_full_backup_*.tar.gz .
```

**方式3: vsftpd（不推荐）**
> ⚠️ vsftpd 坑点：云服务器 ubuntu 用户可能无有效密码（SSH 密钥登录），FTP 认证会失败。需先用 `sudo passwd ubuntu` 设密码。

## 新服务器完整部署（9步）

```bash
# 1️⃣ 解压全部备份
tar -xzf ttdazi_program.tar.gz -C /opt/       # → /opt/ttdazi/
tar -xzf server_b/ttdazi_frontend_dist.tar.gz -C /home/ubuntu/

# 2️⃣ 装 MySQL 8.0 + 导入
sudo apt install -y mysql-server
mysql -u root -p < ttdazi_database.sql          # 密码: huizhiyun2026

# 3️⃣ Python 依赖 (105 个包)
pip3 install -r requirements.txt

# 4️⃣ Systemd 服务
tar -xzf system_configs.tar.gz -C /
systemctl daemon-reload && systemctl enable --now ttdazi

# 5️⃣ 验证后端
curl http://127.0.0.1:5002/api/health

# 6️⃣ 前端部署（用已编译的 dist）
# 已解压到 /home/ubuntu/ttdazi-frontend/

# 7️⃣ Nginx + SSL
sudo apt install -y nginx
tar -xzf server_b/nginx_ssl_backup.tar.gz -C /
# ⚠️ 编辑 /etc/nginx/sites-available/ttdazi:
#   proxy_pass http://42.193.113.230:5002 → http://127.0.0.1:5002
nginx -t && systemctl reload nginx

# 8️⃣ 定时任务（参考 crontab_ubuntu.txt）
(crontab -l 2>/dev/null; echo '* * * * * /bin/bash /opt/ttdazi/monitor.sh') | crontab -

# 9️⃣ 验证全站
curl http://localhost/api/health
# 浏览器访问 http://新服务器IP/
```

## 双→单服务器合并

- `proxy_pass` 从 `http://42.193.113.230:5002` → `http://127.0.0.1:5002`
- 移除 `allow 42.193.113.230` 防火墙规则
- Nginx 站点 ttdazi 需手动启用软链接

## 定时任务重建

```bash
# 订单3天结算（每5分钟）
hermes cron create --name '订单结算' --schedule 'every 5m' --no-agent --script settle_orders.py

# 路径轮换（每天3点）
0 3 * * * bash /opt/ttdazi/rotate_admin_path.sh

# 财务备份（每天8/14/22点）
0 8,14,22 * * * python3 /opt/ttdazi/scripts/finance_backup.py

# 监控（每分钟）
* * * * * bash /opt/ttdazi/monitor.sh

# 安全监控（每20分钟）
*/20 * * * * /usr/local/bin/ttdazi_security_monitor.sh
```

## 验证清单

- [ ] `curl /api/health` 返回 200
- [ ] 前端页面加载不白屏
- [ ] 登录功能正常
- [ ] 数据完整（用户数/订单数对比旧服务器）
- [ ] `journalctl -u ttdazi` 无 Traceback
