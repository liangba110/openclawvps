#!/bin/bash
# ============================================================
# ai-ecom domestic-intel（每天03:00/15:00 内容生成） - QQ通知版
# 运行后根据日志判断结果并通知老板
# ============================================================
set -uo pipefail
NODE=/home/ubuntu/.nvm/versions/node/v22.23.0/bin/node
SCRIPT=/opt/ai-ecom-site/scripts/domestic-intel.mjs
LOG=/opt/ai-ecom-site/data/logs/cron-domestic.log
NOTIFY=/data/disk/notify_qq.sh

export DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-"your_api_key_here"}
export AUTOMATION_TOKEN=9a852e551372fc086a6e700ade394542e9466a17b406a908

BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
"$NODE" "$SCRIPT" >> "$LOG" 2>&1
EXIT=$?
NEW=$(tail -n +$((BEFORE+1)) "$LOG" 2>/dev/null)

if [ $EXIT -ne 0 ]; then
  bash "$NOTIFY" "❌ AI电商站 domestic-intel 执行失败（exit=$EXIT）
日志：$LOG" >> "$LOG" 2>&1
elif echo "$NEW" | grep -qE 'Done: [1-9]'; then
  N=$(echo "$NEW" | grep -oE 'Done: [0-9]+' | tail -1)
  bash "$NOTIFY" "✅ AI电商站内容生成完成（03:00/15:00）
$N 篇已发布" >> "$LOG" 2>&1
elif echo "$NEW" | grep -q 'Daily limit'; then
  echo "  达每日上限，静默" >> "$LOG"
else
  bash "$NOTIFY" "⚠️ AI电商站 domestic-intel 未发布文章（Done: 0）
可能生成失败或已达上限，请留意" >> "$LOG" 2>&1
fi
exit $EXIT
