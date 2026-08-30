#!/bin/bash
# ============================================================
# ai-ecom toc-guard（store 产品 TOC 完整性巡检）- 全自动运维版
# 通知策略：修复成功仅写日志，修复失败/反复复发才通知
# 防死循环：同一产品24h内修复超过5次 → 跳过，通知人工排查
# ============================================================
set -uo pipefail
NODE=/home/ubuntu/.nvm/versions/node/v22.23.0/bin/node
SCRIPT=/opt/ai-ecom-site/scripts/toc-guard.cjs
LOG=/opt/ai-ecom-site/data/logs/toc-guard-cron.log
NOTIFY=/data/disk/notify_qq.sh
STATE=/tmp/toc-guard-fix-count.json

# 初始化状态文件
if [ ! -f "$STATE" ]; then
  echo '{}' > "$STATE"
fi

OUT=$("$NODE" "$SCRIPT" 2>&1)
EXIT=$?
if [ -n "$OUT" ]; then
  printf '%s\n' "$OUT" >> "$LOG"
fi

# 提取修复过的产品
FIXED_SLUGS=$(printf '%s\n' "$OUT" | grep -oE 'FIXED [a-z0-9][a-z0-9-]* L2=' | awk '{print $2}' | sort -u)
# 检查是否有ERROR
HAS_ERROR=$(printf '%s\n' "$OUT" | grep -c 'ERROR' || true)

# 处理修复结果
if [ -n "$FIXED_SLUGS" ]; then
  while IFS= read -r slug; do
    # 读取当前计数
    COUNT=$(python3 -c "
import json, time
try:
    with open('$STATE','r') as f: d=json.load(f)
except: d={}
key='${slug}'
entry=d.get(key, {'count':0, 'first':0})
now=int(time.time())
if now - entry.get('first',0) > 86400:
    entry={'count':0, 'first':now}
entry['count']+=1
d[key]=entry
with open('$STATE','w') as f: json.dump(d,f)
print(entry['count'])
" 2>/dev/null || echo "1")

    if [ "$COUNT" -gt 5 ]; then
      bash "$NOTIFY" "🔴 AI电商站 toc-guard: ${slug} 24h内已修复${COUNT}次仍反复异常，请人工排查" >> "$LOG" 2>&1
    else
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] toc-guard: ${slug} 自动修复成功(第${COUNT}次)" >> "$LOG"
    fi
  done <<< "$FIXED_SLUGS"
fi

# 脚本本身报错，通知
if [ "$EXIT" -eq 1 ] && [ "$HAS_ERROR" -gt 0 ]; then
  bash "$NOTIFY" "🔴 AI电商站 toc-guard 脚本执行异常，请检查日志" >> "$LOG" 2>&1
fi

exit $EXIT
