#!/bin/bash
# ============================================================
# ai-ecom watchdog（每分钟健康守护） - QQ通知版
# 通知策略：仅崩溃(CRASH)、实际发布、或执行异常时通知，正常静默
# 并发保护：flock 防止站点异常导致上一轮未结束、下一轮重复执行
# ============================================================
set -uo pipefail
NODE=/home/ubuntu/.nvm/versions/node/v22.23.0/bin/node
SCRIPT=/opt/ai-ecom-site/scripts/watchdog.mjs
LOG=/opt/ai-ecom-site/data/logs/watchdog-cron.log
NOTIFY=/data/disk/notify_qq.sh
LOCK=/tmp/aiecom-watchdog.lock

# 上一实例仍持有锁（健康检查慢/网络超时）则跳过本轮，避免并发写状态和重复通知
exec 9>"$LOCK" || exit 0
flock -n 9 || exit 0

BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
"$NODE" "$SCRIPT" >> "$LOG" 2>&1
EXIT=$?
NEW=$(tail -n +$((BEFORE+1)) "$LOG" 2>/dev/null)

if echo "$NEW" | grep -q 'CRASH'; then
  MSG=$(echo "$NEW" | grep 'CRASH' | tail -1)
  bash "$NOTIFY" "❌ AI电商站 watchdog 崩溃：
$MSG" >> "$LOG" 2>&1
elif echo "$NEW" | grep -q 'Published'; then
  bash "$NOTIFY" "✅ AI电商站 watchdog 触发发布完成（fallback 模式）" >> "$LOG" 2>&1
elif [ "$EXIT" -ne 0 ]; then
  # 无 CRASH 但退出码非 0（如 node 缺失、日志写失败后的未捕获异常）→ 必须让老板知道，否则静默失守
  LAST=$(echo "$NEW" | tail -1)
  bash "$NOTIFY" "⚠️ AI电商站 watchdog 执行异常（退出码 $EXIT）：
$LAST" >> "$LOG" 2>&1
fi
exit $EXIT
