# 每日备份脚本模板

## 模式

每个项目独立备份脚本，存到 Server A 数据盘 `/root/data/disk/<project>/`。

## 脚本结构

```bash
#!/bin/bash
set -e

BACKUP_BASE="/root/data/disk/<project>"
RETENTION_DAYS=90
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE}/daily_${TIMESTAMP}"
LOG="/var/log/<project>_daily_backup.log"

sudo mkdir -p "$BACKUP_DIR"
sudo chown ubuntu:ubuntu "$BACKUP_DIR"

# 1. 数据库 (mysqldump)
# 2. 项目源码 (tar)
# 3. 用户数据/上传文件 (tar)
# 4. 前端编译产物 (tar)

# 打包成一个文件
sudo tar -czf "/tmp/<project>_full_${TIMESTAMP}.tar.gz" -C "${BACKUP_BASE}" "daily_${TIMESTAMP}/"

# 清理90天前的旧备份
sudo find "${BACKUP_BASE}" -maxdepth 1 -name "daily_*" -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} \;
```

## crontab

各项目错开执行时间，避免资源竞争：
- 同途搭子: `0 2 * * *`
- AI建站: `30 3 * * *`

## 注意事项

- 数据盘路径: `/root/data/disk/`（Server A，20G）
- 使用 `sudo` 确保目录创建权限
- 备份脚本放项目根目录 `/opt/<project>/daily_backup.sh`
- 清理由 `find -mtime +N` 自动完成
