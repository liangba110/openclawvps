#!/usr/bin/env python3
"""
ops_main.py — 智能运维V2主入口
统一调度：事件总线 + 监控探测 + AI决策 + 自动修复 + 预测 + 告警 + 学习

用法:
  python3 ops_main.py              # 启动完整运维守护
  python3 ops_main.py once         # 执行一次巡检
  python3 ops_main.py status       # 查看系统状态
  python3 ops_main.py history      # 查看事件历史
"""
import os
import sys
import time
import signal
import json
from datetime import datetime
from pathlib import Path

from event_bus import bus
from brain_v2 import call_llm_safe
from monitor import monitor
from auto_fixer import scan_all, fix_issue
from predictive import predictor
from self_learning import learner
from alerts import send_alert, get_stats

DATA_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops')) / 'data'
RUNNING = True

def signal_handler(sig, frame):
    global RUNNING
    RUNNING = False
    print("\n收到退出信号，正在停止...")
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ═══════════════════════════════════════════
# 事件驱动的自动修复闭环
# ═══════════════════════════════════════════

def on_service_down(data):
    """服务宕机 → 自动诊断+修复"""
    service = data.get('service', 'unknown')
    print(f"[{datetime.now():%H:%M:%S}] 🔴 服务宕机: {service}")
    recommendations = learner.get_recommendation(f'{service}_down')
    if recommendations:
        best_action, success_rate, count = recommendations[0]
        if success_rate > 0.7 and count >= 3:
            print(f"  → 历史方案（成功率{success_rate:.0%}）: {best_action}")
            _execute_fix(service, best_action, source='learned')
            return
    analysis = call_llm_safe([{
        'role': 'user',
        'content': f'服务 {service} 宕机了，详情: {json.dumps(data.get("details", {}))}。请分析原因并给出修复命令。返回JSON: {{"analysis":"...","fix_cmd":"...","risk":"low/medium/high"}}'
    }])
    if analysis and analysis.get('fix_cmd'):
        fix_cmd = analysis['fix_cmd']
        risk = analysis.get('risk', 'medium')
        if risk == 'low':
            print(f"  → AI建议: {analysis.get('analysis', '')[:100]}")
            _execute_fix(service, fix_cmd, source='ai')
        else:
            send_alert(f'🔴 {service}宕机，AI建议高风险操作需人工确认\n分析: {analysis.get("analysis", "")[:200]}\n命令: {fix_cmd}', level='critical', source='brain_v2')
    else:
        send_alert(f'🔴 {service}宕机，无可用自动修复方案', level='critical', source='monitor')

def on_resource_alert(data):
    """资源告警 → 自动处理或通知"""
    metric = data.get('metric')
    value = data.get('value')
    threshold = data.get('threshold')
    print(f"[{datetime.now():%H:%M:%S}] ⚠️ 资源告警: {metric}={value}%（阈值{threshold}%）")
    if metric == 'disk' and value > 90:
        import subprocess
        subprocess.run("find /tmp -type f -mtime +3 -delete 2>/dev/null", shell=True)
        subprocess.run("find /var/log -name '*.gz' -mtime +7 -delete 2>/dev/null", shell=True)
        learner.record_fix('disk_full', 'tmp_and_logs', 'auto_cleanup', True, service='disk')
        send_alert(f'🗑️ 磁盘紧急清理完成（{metric}={value}%）', level='warn', source='auto_fixer')
    else:
        send_alert(f'⚠️ 资源告警: {metric}={value}%（阈值{threshold}%）', level='warn', source='monitor')

def _execute_fix(service, fix_cmd, source='unknown'):
    import subprocess
    start = time.time()
    try:
        r = subprocess.run(fix_cmd, shell=True, capture_output=True, text=True, timeout=60)
        success = r.returncode == 0
        duration = int((time.time() - start) * 1000)
        learner.record_fix(symptom=f'{service}_down', cause=f'auto_fix_{source}', action=fix_cmd, success=success, service=service, duration_ms=duration)
        if success:
            print(f"  ✅ 修复成功 ({duration}ms)")
            send_alert(f'✅ {service}自动修复成功（{source}）', level='info', source='auto_fixer')
        else:
            print(f"  ❌ 修复失败: {r.stderr[:100]}")
            send_alert(f'❌ {service}自动修复失败\n命令: {fix_cmd}\n错误: {r.stderr[:200]}', level='critical', source='auto_fixer')
    except Exception as e:
        learner.record_fix(f'{service}_down', 'fix_error', fix_cmd, False, service=service)

bus.on('service_down', on_service_down)
bus.on('resource_alert', on_resource_alert)

# ═══════════════════════════════════════════
# 主循环
# ═══════════════════════════════════════════

def run_once():
    print(f"\n{'='*50}")
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 🔍 开始巡检")
    print(f"{'='*50}")
    print("\n[1/4] 服务健康检查...")
    results = monitor.run_all_checks()
    for r in results:
        icon = '✅' if r['healthy'] else '❌'
        print(f"  {icon} {r['name']}")
    print("\n[2/4] 预测性检查...")
    predictions = predictor.predict_issues()
    for pred in predictions:
        print(f"  ⚠️ {pred['issue']}")
    print("\n[3/4] 自动修复扫描...")
    scan = scan_all()
    if scan['total_issues'] > 0:
        print(f"  发现 {scan['total_issues']} 个问题（{scan['auto_fixable']} 个可自动修复）")
        for issue in scan['issues'][:5]:
            print(f"  • {issue['title']}")
    else:
        print("  ✅ 无问题")
    print("\n[4/4] 预测性维护...")
    if predictions:
        actions = predictor.auto_remediate(predictions)
        for action in actions:
            print(f"  🔧 {action}")
    else:
        print("  ✅ 无需处理")
    down_count = len([r for r in results if not r['healthy']])
    if down_count > 0 or scan['total_issues'] > 0 or predictions:
        send_alert(f'巡检完成: {down_count}个服务异常, {scan["total_issues"]}个问题, {len(predictions)}个预测', level='warn' if down_count > 0 else 'info', source='ops_main')
    print(f"\n[{datetime.now():%H:%M:%S}] ✅ 巡检完成")
    return results, predictions, scan

def run_daemon(interval=300):
    print(f"🚀 智能运维V2启动（间隔{interval}秒）")
    print(f"   Ctrl+C 退出\n")
    run_once()
    while RUNNING:
        for _ in range(interval):
            if not RUNNING:
                break
            time.sleep(1)
        if RUNNING:
            try:
                run_once()
            except Exception as e:
                print(f"巡检异常: {e}")
                send_alert(f'巡检异常: {e}', level='critical', source='ops_main')
    print("🛑 智能运维已停止")

def show_status():
    status = monitor.get_status()
    stats = get_stats(24)
    learn_stats = learner.get_stats()
    print("═══ 智能运维V2 状态 ═══")
    print(f"\n📡 服务状态: {status['healthy']}/{status['total_services']} 正常")
    if status['down']:
        print(f"   ❌ 异常: {', '.join(status['down'])}")
    print(f"   上次检查: {status['last_check']}")
    print(f"\n📊 24h告警: {stats['total']}条")
    for level, count in stats.get('by_level', {}).items():
        print(f"   {level}: {count}条")
    print(f"\n🧠 学习库:")
    print(f"   总修复: {learn_stats['total_fixes']}次")
    print(f"   成功率: {learn_stats['success_rate']:.0%}")
    print(f"   已学习规则: {learn_stats['learned_rules']}条")

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'daemon'
    if cmd == 'once':
        run_once()
    elif cmd == 'status':
        show_status()
    elif cmd == 'history':
        events = bus.query(limit=20)
        for ev in events:
            print(f"[{datetime.fromtimestamp(ev[1]):%H:%M:%S}] {ev[2]}: {ev[3][:80]}")
    elif cmd == 'daemon':
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        run_daemon(interval)
    else:
        print('用法: [once|status|history|daemon [间隔秒数]]')
