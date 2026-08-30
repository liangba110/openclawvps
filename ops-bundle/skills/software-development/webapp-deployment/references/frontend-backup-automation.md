# Automated Backup with Email Delivery

## Script Design

A single `auto_backup.sh` script handles: MySQL dump → source archive → email attachment → cleanup.

```bash
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/ubuntu/backups/auto_${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

# 1. Database
sudo mysqldump -u root -p<password> <dbname> | gzip > "$BACKUP_DIR/database.sql.gz"

# 2. Source code (exclude dev artifacts)
tar --exclude='*/node_modules/*' --exclude='*/__pycache__/*' --exclude='*.pyc' \
    --exclude='*/dist/*' --exclude='*/.vite/*' \
    -czf "$BACKUP_DIR/source_code.tar.gz" -C /opt <project-dir>/

# 3. Send via SMTP (Python inline)
python3 -c "
import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header

msg = MIMEMultipart()
msg['Subject'] = Header('Backup $TIMESTAMP', 'utf-8')
msg['From'] = 'sender@qq.com'
msg['To'] = 'recipient@qq.com'

# plain-text body
files = sorted(os.listdir(bkdir))
body_lines = ['Backup Report', '', 'Time: $TIMESTAMP', '']
for f in files:
    body_lines.append(f'  {f}')
msg.attach(MIMEText('\n'.join(body_lines), 'plain', 'utf-8'))

# attachments
for f in files:
    with open(os.path.join(bkdir, f), 'rb') as fh:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(fh.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment', filename=('utf-8', '', f))
        msg.attach(part)

smtp = smtplib.SMTP_SSL('smtp.qq.com', 465)
smtp.login(from_email, smtp_pass)
smtp.sendmail(from_email, [to_email], msg.as_string())
smtp.quit()
"

# 4. Cleanup backups older than 7 days
find /home/ubuntu/backups/ -name "auto_*" -type d -mtime +7 -exec rm -rf {} \;
```

## Cron Schedule

Three times daily (times should be outside peak hours):

```bash
0 6,14,22 * * * /home/ubuntu/.hermes/scripts/auto_backup.sh
```

## Key Details

- **SMTP encoding**: Use `Header('Subject', 'utf-8')` for Chinese subjects, NOT plain `msg['Subject'] = '中文'` (fails with ASCII-only SMTP `sendmail`).
- **Attachment filenames**: Use 3-tuple `('utf-8', '', f)` in `add_header('Content-Disposition', ...)` to support Chinese characters.
- **Cron job placement**: Place scripts under `~/.hermes/scripts/` for Hermes cron integration, or `/etc/cron.d/` for system cron.
- **Old backup cleanup**: `-mtime +7` matches files modified 7+ days ago. Run `rm -rf` with caution — test with `-print` first.
- **Email body encoding**: Use `'plain'` (not `'html'`) for SMTP reliability with Chinese characters. HTML bodies need multipart/alternative with utf-8 charset on every MIME part.

## Pitfalls

- **SMTP sendmail blocks the API**: Running SMTP inside a Flask request handler blocks the response until delivery completes (up to 15s+). For user-facing flows, defer to a background thread or task queue. For the backup cron job (run outside the request cycle), blocking is acceptable.
- **Email attachment charset**: QQ Mail SMTP rejects non-ASCII attachment filenames if not properly encoded. The 3-tuple format `filename=('utf-8', '', f)` handles this.
- **Memory constraint**: Backup to disk first, then attach. Building emails with very large attachments (>25MB) can hit Python memory limits. Compress everything before attaching.
- **SMTP login failures**: QQ Mail requires an **authorization code** (开启SMTP服务后生成), NOT the QQ password. The code is usually 16 characters.
