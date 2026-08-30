# Daily Backup with Retention (Pattern)

## Core Pattern

```bash
#!/bin/bash
BACKUP_BASE="/path/to/backup"
RETENTION_DAYS=90
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE}/daily_${TIMESTAMP}"

mkdir -p "$BACKUP_DIR"

# 1. Database
mysqldump -h127.0.0.1 -uroot -p"${PASS}" \
  --single-transaction --routines --triggers dbname \
  > "${BACKUP_DIR}/dbname_database.sql"

# 2. Source code
tar -czf "${BACKUP_DIR}/program.tar.gz" -C /opt project/

# 3. User uploads
tar -czf "${BACKUP_DIR}/uploads.tar.gz" -C /opt/project backend/app/uploads/

# 4. Cleanup old backups (the key pattern)
find "${BACKUP_BASE}" -maxdepth 1 -name "daily_*" -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} \;
```

## Multi-Project Setup

When multiple projects need separate backups on the same server:

```bash
# crontab entries (stagger times to avoid I/O spikes)
0 2 * * * sudo bash /opt/project_a/daily_backup.sh        # Project A
30 3 * * * sudo bash /opt/project_b/daily_backup.sh        # Project B
```

Each project has its own subdirectory under the backup base:
- `/root/data/disk/` — Project A backups
- `/root/data/disk/project_b/` — Project B backups

## Auto-Cleanup Mechanics

- `find ... -mtime +90` matches files/folders modified more than 90 days ago
- `-exec rm -rf {} \;` deletes each matched item
- Runs at the END of each backup, so current backup is never deleted
- Storage grows linearly: daily_backup_size × RETENTION_DAYS

## Pitfalls

- **Permission**: The backup directory may be owned by root after `sudo mkdir`. Always `sudo chown` if the backup script runs as a non-root user part-way through.
- **Disk space check**: Add a pre-check before starting:
  ```bash
  AVAIL=$(df --output=avail "${BACKUP_BASE}" | tail -1)
  if [ "$AVAIL" -lt 1048576 ]; then echo "WARN: Low disk space"; fi
  ```
- **Compression ordering**: `tar -czf` before `sudo mv` — write to /tmp first (no sudo needed), then move to destination (may need sudo).
- **Log file growth**: Redirect script output to a dedicated log, use `tee -a` to see both console and log.
- **Retention vs storage**: 90 days × ~50MB/day = ~4.5GB. For a 20GB data disk this is fine; for smaller disks adjust RETENTION_DAYS.
