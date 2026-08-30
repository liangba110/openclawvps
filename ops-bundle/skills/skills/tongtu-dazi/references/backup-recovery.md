# 同途搭子 备份与恢复指南

## 📍 架构回顾

| 组件 | 地址 | 说明 |
|------|------|------|
| Server A | 42.193.113.230:5002 | Flask + gunicorn + MySQL |
| Server B | 82.157.202.24:80 | Nginx 反向代理 + 前端静态文件 |
| 项目路径 | `/opt/ttdazi/` (Server A) | 全量代码 |
| 前端部署 | `/home/ubuntu/ttdazi-frontend/` (Server B) | 由 deploy.sh 同步 |
| 主站域名 | `https://dazi.openai2000.cn` | 同途搭子主站 |

## 全量备份步骤

### 1. 创建备份目录

```bash
BACKUP_DIR="/opt/ttdazi/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
```

### 2. 数据库备份（MySQL）

```bash
# 仅 huizhiyun 主库（推荐）
mysqldump -uroot -p'密码' --databases huizhiyun \
  --hex-blob --routines --events --triggers --single-transaction \
  | gzip > "$BACKUP_DIR/huizhiyun_db.sql.gz"

# 全库备份（含 mysql 系统库等）
mysqldump -uroot -p'密码' --all-databases \
  --hex-blob --routines --events --triggers --single-transaction \
  | gzip > "$BACKUP_DIR/all_databases.sql.gz"
```

> **参数说明：** `--single-transaction` 保证一致性且不加锁；`--hex-blob` 防止二进制数据乱码；`--routines --events --triggers` 备份存储过程/事件/触发器。

### 3. 代码备份

```bash
tar czf "$BACKUP_DIR/ttdazi_code_backup.tar.gz" \
  -C /opt/ttdazi \
  --exclude=".git" \
  --exclude="node_modules" \
  --exclude="frontend/node_modules" \
  --exclude="__pycache__" \
  --exclude="*.pyc" \
  --exclude="backups" \
  --exclude=".venv" \
  --exclude="venv" \
  .
```

> **排除说明：** Git 历史、node_modules、__pycache__ 等都是可重建的，不备份。backups 目录本身也排除，避免递归膨胀。

### 4. 支付微服务

```bash
tar czf "$BACKUP_DIR/payment_service_backup.tar.gz" \
  -C /opt/ttdazi payment_service/
```

### 5. Nginx 配置（Server B）

```bash
ssh ubuntu@82.157.202.24 \
  "sudo tar czf /tmp/nginx_configs.tar.gz \
    /etc/nginx/sites-enabled/ \
    /etc/nginx/nginx.conf \
    /etc/nginx/conf.d/"

scp ubuntu@82.157.202.24:/tmp/nginx_configs.tar.gz "$BACKUP_DIR/"
```

> **注意：** Server B 上 ttdazi Nginx 配置文件权限为 600 (仅root可读)，需 sudo 读取。

---

## 数据恢复

### 恢复数据库

```bash
gunzip < "$BACKUP_DIR/huizhiyun_db.sql.gz" | mysql -uroot -p'密码' huizhiyun
```

### 恢复代码

```bash
sudo tar xzf "$BACKUP_DIR/ttdazi_code_backup.tar.gz" -C /opt/ttdazi/
# 恢复后重建依赖
cd /opt/ttdazi/backend && pip install -r requirements.txt
cd /opt/ttdazi/frontend && npm install
```

### 恢复 Nginx 配置

```bash
scp "$BACKUP_DIR/nginx_configs.tar.gz" ubuntu@82.157.202.24:/tmp/
ssh ubuntu@82.157.202.24 "sudo tar xzf /tmp/nginx_configs.tar.gz -C / && sudo nginx -t && sudo systemctl reload nginx"
```

### 恢复后部署

```bash
cd /opt/ttdazi/frontend && npm run build && bash /opt/ttdazi/deploy.sh
```
