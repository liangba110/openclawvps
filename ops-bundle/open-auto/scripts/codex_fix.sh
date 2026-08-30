#!/bin/bash
# ============================================================
# 汇智云码 - 统一 codex 自动修复入口 (2026-08-13)
# 用途：任何自动任务执行失败时，调用本脚本让 codex 全面检查并修复
# 用法：bash /data/disk/codex_fix.sh "任务名" "失败描述"
# 日志：/data/disk/codex_fix.log
# ============================================================
TASK_NAME="${1:-未知任务}"
FAIL_DESC="${2:-执行失败}"
LOG="/data/disk/codex_fix.log"
NOTIFY="/data/disk/notify_qq.sh"
TS=$(date '+%Y-%m-%d %H:%M:%S')

log() { echo "[$TS] [$TASK_NAME] $1" >> "$LOG"; }

# 日志自愈：任何用户（含 root/sudo）调用后都保证 log 可追加，
# 避免 log 变 root 属主后 ubuntu 写入报 Permission denied 导致修复链路静默失败
if [ ! -w "$LOG" ]; then
  touch "$LOG" 2>/dev/null || true
  chown ubuntu:ubuntu "$LOG" 2>/dev/null || sudo -n chown ubuntu:ubuntu "$LOG" 2>/dev/null || true
  chmod 664 "$LOG" 2>/dev/null || sudo -n chmod 664 "$LOG" 2>/dev/null || true
fi

# 后台化执行：调用方（OpenClaw exec 工具约120秒超时/cron 等）不再被阻塞，
# 避免 codex 修复还没跑完就被 SIGKILL，导致任务被误判为“执行失败”。
# 用独立参数 __bg__ 标记后台实例（不用环境变量：env 会随 codex exec 会话泄漏，
# 导致会话内再次调用时被误判为后台实例而同步执行、再次阻塞调用方）。
# setsid 让后台实例脱离调用方进程组/会话，防止调用方会话清理时连后台修复一起被杀；
# 首次调用立即返回，实际修复由后台实例完成，结果写入 $LOG 并发送 QQ 通知。
if [ "${1:-}" != "__bg__" ]; then
  setsid nohup bash "$0" "__bg__" "$@" >> "$LOG" 2>&1 < /dev/null &
  log "已在后台启动 codex 修复（不阻塞调用方）: $FAIL_DESC"
  exit 0
fi
shift

# 并发保护：同一时刻只允许一个 codex 修复实例，重复触发直接跳过
exec 9>>"/data/disk/codex_fix.lock"
if ! flock -n 9; then
  log "已有 codex 修复在运行，跳过本次（防并发）: $FAIL_DESC"
  exit 0
fi

log "触发 codex 修复: $FAIL_DESC"

# 调用 codex 全面检查修复（限定网站目录，改前备份，修复后验证）
FIX_OUT=$(cd /data/web/huizhiyunma && timeout 600 /home/ubuntu/.local/bin/codex exec -C /data/web/huizhiyunma --skip-git-repo-check -s danger-full-access "自动任务【${TASK_NAME}】执行失败：${FAIL_DESC}。请全面检查定位根因：
1) 查看相关日志（/data/web/huizhiyunma/backend/seo/generate_article.log、/data/disk/backup_history.log、pm2 日志等）
2) 检查后端服务、数据库连接、脚本运行环境（node 路径、权限）
3) 定位根因后最小化修复；修改文件前必须先备份（cp 加 .bak_时间戳）
4) 修复后验证：curl -s -o /dev/null -w '%{http_code}' https://openai2000.cn/ 返回 200；若任务可手动重跑则重跑确认成功
输出：修复根因、改动内容、验证结果。" 2>&1)

EXIT_CODE=$?
echo "$FIX_OUT" | tail -40 >> "$LOG"
log "codex 退出码: $EXIT_CODE"

# 修复后验证网站健康
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://openai2000.cn/ 2>/dev/null)

if [ "$EXIT_CODE" -eq 0 ] && [ "$HTTP_CODE" = "200" ]; then
  log "✅ codex 修复完成，网站正常"
  bash "$NOTIFY" "🔧 【$TASK_NAME】失败已由 codex 自动修复
问题：$FAIL_DESC
处理：codex 已定位并修复（详见 /data/disk/codex_fix.log）
网站状态：正常 (HTTP 200)" >> "$LOG" 2>&1
else
  log "⚠️ codex 修复未完成（exit=$EXIT_CODE, http=$HTTP_CODE），需人工介入"
  bash "$NOTIFY" "🚨 【$TASK_NAME】失败，codex 修复未完成！
问题：$FAIL_DESC
codex 退出码：$EXIT_CODE，网站 HTTP：$HTTP_CODE
详见 /data/disk/codex_fix.log，请人工介入！" >> "$LOG" 2>&1
fi

exit $EXIT_CODE
