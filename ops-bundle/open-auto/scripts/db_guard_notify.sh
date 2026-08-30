#!/bin/bash
# ============================================================
# ai-ecom db-guard（每分钟数据库守护） - QQ通知版
# 通知策略：仅在检测到异常（数据过低/恢复/备份失败）时通知，正常静默
# ============================================================
set -uo pipefail
NODE=/home/ubuntu/.nvm/versions/node/v22.23.0/bin/node
SCRIPT=/opt/ai-ecom-site/scripts/db-guard.cjs
LOG=/opt/ai-ecom-site/data/logs/db-guard-cron.log
NOTIFY=/data/disk/notify_qq.sh

BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
"$NODE" "$SCRIPT" >> "$LOG" 2>&1
EXIT=$?
NEW=$(tail -n +$((BEFORE+1)) "$LOG" 2>/dev/null)

if echo "$NEW" | grep -qE 'LOW DATA|restoring|NO GOOD BACKUP|backup fail'; then
  MSG=$(echo "$NEW" | grep -E 'LOW DATA|restoring|NO GOOD BACKUP|backup fail' | tail -1)
  bash "$NOTIFY" "⚠️ AI电商站数据库守护异常：
$MSG" >> "$LOG" 2>&1
fi
exit $EXIT
