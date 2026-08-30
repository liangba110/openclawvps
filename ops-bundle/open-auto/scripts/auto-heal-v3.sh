#!/bin/bash
# Open Auto v3 - 自动巡检集成脚本
# 定时调用 v3 模块，统一执行巡检和修复

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
V3_DIR="$SCRIPT_DIR/../v3"
LOG_DIR="/tmp/open-auto-logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/v3-check-$TIMESTAMP.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Open Auto v3 巡检开始 ==="

# 1. 指标采集
log "📊 采集系统指标..."
node "$V3_DIR/predictive-guard.cjs" collect >> "$LOG_FILE" 2>&1 || log "⚠️ 指标采集异常"

# 2. 安全扫描
log "🛡️ 安全扫描..."
node "$V3_DIR/security-guard.cjs" scan >> "$LOG_FILE" 2>&1 || log "⚠️ 安全扫描异常"

# 3. 修复编排
log "🔧 执行修复..."
node "$V3_DIR/heal-orchestrator.cjs" run >> "$LOG_FILE" 2>&1 || log "⚠️ 修复编排异常"

# 4. 清理旧日志（保留7天）
find "$LOG_DIR" -name "v3-check-*.log" -mtime +7 -delete 2>/dev/null || true

log "=== Open Auto v3 巡检完成 ==="

# 输出摘要
echo ""
echo "📋 巡检摘要："
tail -20 "$LOG_FILE"
