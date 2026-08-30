#!/bin/bash
# 每日健康巡检 - no_agent cron watchdog 模板（正常静默、异常才输出）
# 放置：~/.hermes/scripts/daily_healthcheck.sh
# cron：no_agent=true, script=daily_healthcheck.sh（相对路径）, schedule=0 8 * * *
# 语义：stdout 非空→发送；stdout 空→静默；非零退出→错误告警（健康必须 exit 0）
REPORT=""

# 1. 磁盘（>85% 报警；/data/disk 与 / 都查）
DATA_PCT=$(df /data/disk | tail -1 | awk '{print $5}' | tr -d '%')
SYS_PCT=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
[ "${DATA_PCT:-0}" -ge 85 ] && REPORT+="⚠️ 数据盘使用 ${DATA_PCT}%\n"
[ "${SYS_PCT:-0}" -ge 85 ] && REPORT+="⚠️ 系统盘使用 ${SYS_PCT}%\n"

# 2. 站点 HTTP（带浏览器 UA，防 E 服务器安全分流转 D 旧版）
for u in "https://api.openai2000.cn/" "https://www.ttdazi.xyz/" "https://aiweb.openai2000.cn/" "https://pay.openai2000.cn/"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 8 -A 'Mozilla/5.0' "$u" 2>/dev/null)
  [ "$code" != "200" ] && REPORT+="❌ $u → HTTP $code\n"
done

# 3. 昨日备份（daily_* 目录最新日期必须=今天或昨天）
LATEST_BACKUP=$(ls -dt /data/disk/daily_* 2>/dev/null | head -1)
if [ -z "$LATEST_BACKUP" ]; then
  REPORT+="❌ /data/disk 无备份目录\n"
else
  BK_DATE=$(basename "$LATEST_BACKUP" | sed 's/daily_//;s/_.*//')
  TODAY=$(date +%Y%m%d)
  YDAY=$(date -d yesterday +%Y%m%d 2>/dev/null || date -v-1d +%Y%m%d)
  [ "$BK_DATE" != "$TODAY" ] && [ "$BK_DATE" != "$YDAY" ] && REPORT+="❌ 最新备份停留在 $BK_DATE\n"
fi

# 4. 服务进程
for svc in ttdazi ttdazi-pay aiweb; do
  systemctl is-active --quiet "$svc" 2>/dev/null || REPORT+="❌ 服务 $svc 未运行\n"
done

# 输出（空=正常静默，exit 0；异常=报告+exit 1）
if [ -n "$REPORT" ]; then
  echo -e "🩺 每日巡检 $(date '+%m-%d %H:%M')\n$REPORT"
  exit 1
fi
exit 0
