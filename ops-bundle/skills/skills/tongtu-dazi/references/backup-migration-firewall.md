# Server Migration & Backup Procedure

## What to Backup

| Item | Location | Size |
|------|----------|------|
| Hermes Skills+Config | `~/.hermes/skills/` + `~/.hermes/config.yaml` | ~2MB |
| Project Source | `/opt/ttdazi/` (git-managed) | full repo |
| MySQL Database | `mysqldump -u root -p huizhiyun > backup.sql` | variable |

## Backup Command

```bash
# 1. Hermes core
tar -czf hermes_core.tar.gz -C ~/ .hermes/skills/ -C ~/ .hermes/config.yaml

# 2. Database
mysqldump -u root -p huizhiyun > ttdazi_db.sql && gzip ttdazi_db.sql

# 3. Project (git pull is enough, but full backup:)
tar -czf ttdazi_source.tar.gz --exclude=node_modules --exclude=dist backend/ frontend/ deploy.sh
```

Backup files go to `/opt/ttdazi/backend/app/backups/` accessible via /download page.

## Restore on New Server

```bash
# 1. Hermes
tar -xzf hermes_core.tar.gz -C ~/
pip3 install hermes-agent

# 2. Project
git clone <repo-url> /opt/ttdazi
cd /opt/ttdazi/frontend && npm install && npm run build

# 3. Database
mysql -u root -p huizhiyun < ttdazi_db.sql

# 4. Restart
cd /opt/ttdazi/backend && gunicorn main:app -b 0.0.0.0:5002 -w 2
```

## Firewall: Security Groups NOT iptables

**NEVER** use `iptables` directly on Tencent Cloud servers. Always use Security Groups via the Tencent Cloud console.

Why: `iptables -P INPUT DROP` runs immediately. If the ACCEPT rules for SSH/HTTP haven't been added yet (SSH timeout, command ordering), you lock yourself out. Recovery requires VNC console.

Security Group rules (configure in cloud console):
- Server A (API+DB): 22(SSH), 5002(Server B only), 3306(local)
- Server B (Public): 22(Server A only), 80/443(0.0.0.0/0)
