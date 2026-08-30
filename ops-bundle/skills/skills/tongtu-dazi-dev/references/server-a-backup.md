# Server A 完整备份指南

Server A (42.193.113.230) 即当前本地机器（VM-0-15-ubuntu），运行 Flask 后端 + MySQL。

## 架构信息

| 项目 | 值 |
|------|-----|
| 主机 | VM-0-15-ubuntu |
| 公网 IP | 42.193.113.230（本机） |
| 内网 IP | 10.2.0.15 |
| 项目路径 | `/opt/ttdazi/` |
| 项目大小 | ~389M |
| 后端服务 | gunicorn (Flask, port 5002) |
| 数据库 | MySQL 8.0.46 → 库名 `huizhiyun`（46张表） |
| MySQL root 密码 | 从 `/opt/ttdazi/backend/app/backup_api.py` 读取默认 `huizhiyun2026` |
| Systemd 服务 | `/etc/systemd/system/ttdazi.service` + `ttdazi-pay.service` |
| 数据盘 | `/dev/vdb` → `/root/data/disk/`（20G，~19G 可用） |

## SSH 密钥认证（从 Server B 访问）

Server B (82.157.202.24) 访问 Server A 时需要 SSH 密钥：

```bash
# 在 Server A 上添加 Server B 的公钥
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMpBfX/VbpVFsQfEVOrsi4qeddE84tzAAVyv/DYjGTrw ubuntu@VM-0-15-ubuntu' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

## Server B 数据备份（从 Server A 发起）

Server B (82.157.202.24) 上存放 Nginx 反向代理配置、SSL 证书、前端静态文件和 OpenClaw 机器人配置。备份时从 Server A 远程拉取：

```bash
mkdir -p "$BACKUP_DIR/server_b"

# 1. Nginx 配置 + SSL 证书
ssh ubuntu@82.157.202.24 "sudo tar -czf /tmp/nginx_ssl_backup.tar.gz \
  /etc/nginx/sites-available/ttdazi \
  /etc/nginx/sites-enabled/huizhiyunma \
  /etc/nginx/nginx.conf \
  /etc/nginx/ssl/"
scp ubuntu@82.157.202.24:/tmp/nginx_ssl_backup.tar.gz "$BACKUP_DIR/server_b/"

# 2. 前端静态文件（dist）
ssh ubuntu@82.157.202.24 "tar -czf /tmp/ttdazi_frontend_dist.tar.gz \
  -C /home/ubuntu ttdazi-frontend/"
scp ubuntu@82.157.202.24:/tmp/ttdazi_frontend_dist.tar.gz "$BACKUP_DIR/server_b/"

# 3. OpenClaw 配置
ssh ubuntu@82.157.202.24 "tar -czf /tmp/openclaw_config.tar.gz \
  -C /home/ubuntu .openclaw/openclaw.json \
  -C /home/ubuntu .openclaw/agents/ \
  -C /home/ubuntu .config/systemd/user/openclaw-gateway.service"
scp ubuntu@82.157.202.24:/tmp/openclaw_config.tar.gz "$BACKUP_DIR/server_b/"

# 4. 安全监控脚本
ssh ubuntu@82.157.202.24 "sudo cp /usr/local/bin/ttdazi_security_monitor.sh /tmp/ && sudo chown ubuntu:ubuntu /tmp/ttdazi_security_monitor.sh"
scp ubuntu@82.157.202.24:/tmp/ttdazi_security_monitor.sh "$BACKUP_DIR/server_b/" 2>/dev/null
```

> 🔴 注意：Server B 的 `huizhiyunma` 是 Nginx 唯一生效的配置文件（sites-enabled/ 中的独立副本，非软链接）。`sites-available/ttdazi` 可能已过时。配置请直接修改 `sites-enabled/huizhiyunma`。合并到单机时必须将 proxy_pass 从 `http://42.193.113.230:5002` 改为 `http://127.0.0.1:5002`

## 完整备份命令

```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/root/data/disk/backup_${TIMESTAMP}"
sudo mkdir -p "$BACKUP_DIR"

# 1. MySQL 全量导出（46张表，~324K）
MYSQL_PWD='huizhiyun2026' mysqldump -h127.0.0.1 -uroot \
  --databases huizhiyun --routines --triggers --single-transaction \
  | sudo tee "$BACKUP_DIR/ttdazi_database.sql" > /dev/null

# 2. 程序文件（~279M，~16769个文件）
sudo tar -czf "$BACKUP_DIR/ttdazi_program.tar.gz" -C /opt ttdazi/

# 3. 系统配置（含支付微服务）
sudo tar -czf "$BACKUP_DIR/system_configs.tar.gz" \
  /etc/systemd/system/ttdazi.service \
  /etc/systemd/system/ttdazi-pay.service

# 4. 定时任务
sudo crontab -l 2>/dev/null | sudo tee "$BACKUP_DIR/crontab_root.txt" > /dev/null
crontab -l 2>/dev/null | sudo tee "$BACKUP_DIR/crontab_ubuntu.txt" > /dev/null

# 5. 环境变量
sudo tar -czf "$BACKUP_DIR/env_configs.tar.gz" \
  /home/ubuntu/.bashrc /etc/environment

# 6. 前端静态文件（编译产物 dist/）
sudo tar -czf "$BACKUP_DIR/ttdazi_static_dist.tar.gz" \
  -C /opt/ttdazi/frontend dist/

# 7. 用户上传文件
sudo tar -czf "$BACKUP_DIR/ttdazi_uploads.tar.gz" \
  -C /opt/ttdazi/backend app/uploads/ \
  -C /opt/ttdazi/backend uploads/ 2>/dev/null

# 8. Python 依赖清单
pip3 freeze | sudo tee "$BACKUP_DIR/requirements.txt" > /dev/null

# 9. 支付微服务证书和配置
sudo tar -czf "$BACKUP_DIR/payment_service_certs.tar.gz" \
  -C /opt/ttdazi/payment_service certs/ config.py db.py requirements.txt

# 10. 部署脚本和管理脚本
sudo cp /opt/ttdazi/deploy.sh "$BACKUP_DIR/" 2>/dev/null
sudo cp /opt/ttdazi/monitor.sh "$BACKUP_DIR/" 2>/dev/null

# 11. 固定权限（注意：/root/data/disk/ 需要 sudo 访问）
sudo chown -R ubuntu:ubuntu "$BACKUP_DIR"
sudo chmod -R 755 "$BACKUP_DIR"

echo "备份完成: $BACKUP_DIR"
sudo ls -lh "$BACKUP_DIR"
```

## 定时任务清单（Server A ubuntu 用户）

```
* * * * * /bin/bash /opt/ttdazi/monitor.sh
*/20 * * * * /usr/local/bin/ttdazi_security_monitor.sh > /dev/null 2>&1
0 3 * * * bash /opt/ttdazi/rotate_admin_path.sh >> /var/log/rotate_admin.log 2>&1
0 4 * * * bash /opt/ttdazi/backup_hermes.sh >> /var/log/hermes_backup.log 2>&1
```

## 自动化每日备份脚本

位置: `/opt/ttdazi/daily_backup.sh`

自动执行完整备份 + 保留最近7天。输出到 `/root/data/disk/daily_YYYYMMDD_HHMMSS/`。

### cron 配置

```cron
0 2 * * * sudo bash /opt/ttdazi/daily_backup.sh >> /var/log/ttdazi_daily_backup.log 2>&1
```

需要 sudoers 免密规则：

```bash
echo "ubuntu ALL=(ALL) NOPASSWD: /opt/ttdazi/daily_backup.sh" | sudo tee /etc/sudoers.d/ttdazi_backup
sudo chmod 440 /etc/sudoers.d/ttdazi_backup
```

### 备份内容

| 步骤 | 内容 | 目标位置 |
|------|------|---------|
| 1/7 | MySQL 全库导出 | `ttdazi_database.sql` |
| 2/7 | 项目源码 | `ttdazi_program.tar.gz` |
| 3/7 | 前端 dist | `ttdazi_static_dist.tar.gz` |
| 4/7 | 上传文件 | `ttdazi_uploads.tar.gz` |
| 5/7 | 系统配置 + requirements.txt | `system_configs.tar.gz` |
| 6/7 | Server B (Nginx/SSL/前端) | `server_b/` 子目录 |
| 7/7 | crontab 快照 | `crontab_*.txt` |

### Server B 备份说明

脚本通过 SSH 从 Server A 拉取 Server B 数据。需要 Server A 的 SSH 公钥在 Server B 的 `~/.ssh/authorized_keys` 中。如果 Server B 不可达，脚本会跳过并记录警告。

## 验证备份完整性

```bash
BACKUP_DIR="/root/data/disk/backup_YYYYMMDD_HHMMSS"

# 验证 SQL
sudo head -5 "$BACKUP_DIR/ttdazi_database.sql"
sudo tail -5 "$BACKUP_DIR/ttdazi_database.sql"
sudo grep -c "CREATE TABLE" "$BACKUP_DIR/ttdazi_database.sql"

# 验证 tar 包文件数
sudo tar -tzf "$BACKUP_DIR/ttdazi_program.tar.gz" | wc -l

# 验证 tar 包完整性（所有备份包逐一检查）
for f in ttdazi_program.tar.gz system_configs.tar.gz \
         ttdazi_static_dist.tar.gz ttdazi_uploads.tar.gz \
         payment_service_certs.tar.gz; do
  sudo tar -tzf "$BACKUP_DIR/$f" > /dev/null && echo "✅ $f 完整"
done

# 验证 Server B 包（如存在）
[ -f "$BACKUP_DIR/nginx_ssl_backup.tar.gz" ] && \
  sudo tar -tzf "$BACKUP_DIR/nginx_ssl_backup.tar.gz" > /dev/null && \
  echo "✅ nginx_ssl_backup.tar.gz 完整"
[ -f "$BACKUP_DIR/ttdazi_frontend_dist_server_b.tar.gz" ] && \
  sudo tar -tzf "$BACKUP_DIR/ttdazi_frontend_dist_server_b.tar.gz" > /dev/null && \
  echo "✅ ttdazi_frontend_dist_server_b.tar.gz 完整"
```

## 下载/传输方式

备份到数据盘后，可通过以下方式传输到新服务器：

### 方式1: Python HTTP 服务器（推荐）
```bash
# 在 Server A 上启动 HTTP 服务器
cd /home/ubuntu
python3 -m http.server 8080 &

# 从新服务器下载
curl -O http://42.193.113.230:8080/ttdazi_full_backup_YYYYMMDD_HHMMSS.tar.gz
```
> ⚠️ 可能需要放行 iptables: `sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT`

### 方式2: 打包到 ubuntu 家目录（推荐用于下载）

```bash
# 打包成一个文件到 /home/ubuntu/（可被 ubuntu 用户直接访问）
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
sudo tar -czf "/home/ubuntu/ttdazi_full_backup_${TIMESTAMP}.tar.gz" \
  -C /root/data/disk backup_*/
sudo chown ubuntu:ubuntu "/home/ubuntu/ttdazi_full_backup_${TIMESTAMP}.tar.gz"
```

⚠️ `/root/data/disk/` 目录归 root 所有，ubuntu 用户无法直接 `ls` 或 `scp`。
备份文件打包到 `/home/ubuntu/` 后可直接用 `scp` 或其他工具下载。

### 方式3: scp 直接拉取
```bash
# 从其他服务器拉取（在目标服务器上执行）
scp ubuntu@42.193.113.230:/home/ubuntu/ttdazi_full_backup_*.tar.gz ./
```

## 备份总览

| 项目 | 大小 | 说明 |
|------|------|------|
| `ttdazi_database.sql` | ~324K | MySQL 全库导出（46张表，含 routines/triggers） |
| `ttdazi_program.tar.gz` | ~279M | 完整项目源码 + 支付微服务（~16769文件） |
| `ttdazi_static_dist.tar.gz` | ~780K | 前端编译产物 dist/ |
| `ttdazi_uploads.tar.gz` | ~11M | 用户上传文件（头像/身份证） |
| `system_configs.tar.gz` | ~500B | Systemd 服务（ttdazi + ttdazi-pay） |
| `payment_service_certs.tar.gz` | ~7K | 支付微服务证书和配置 |
| `requirements.txt` | ~2K | Python 依赖清单 |
| `env_configs.tar.gz` | ~2.1K | bashrc + /etc/environment |
| `crontab_*.txt` | ~600B | 系统+应用定时任务 |
| `nginx_ssl_backup.tar.gz` | ~4K | Server B Nginx + huizhiyunma + SSL |
| `ttdazi_frontend_dist_server_b.tar.gz` | ~10M | Server B 前端静态文件 |
| **完整迁移包** | **~300M** | 打包为单一 tar.gz（比旧版小，因不含重复的 dist） |
| 数据盘 | 20G 余 19G | `/dev/vdb` → `/root/data/disk/` |
