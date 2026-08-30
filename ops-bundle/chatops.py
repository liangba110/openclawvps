#!/usr/bin/env python3
"""
chatops.py — 自然语言运维（ChatOps）
让用户用自然语言直接查询/操作服务器

用法:
  python3 chatops.py "最近哪个服务最不稳定？"
  python3 chatops.py "MySQL当前连接数多少？"
  python3 chatops.py "清理7天前的tmp文件"
  python3 chatops.py "最近24小时告警统计"

能力范围：
  - 服务状态查询
  - 系统资源查询
  - 日志分析查询
  - 告警历史查询
  - 安全操作执行（只读+白名单写操作）
"""
import os
import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

OPS_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
sys.path.insert(0, str(OPS_DIR))

from event_bus import bus
from monitor import monitor
from self_learning import learner
from alerts import get_history, get_stats
from brain_v2 import call_llm_safe

# ═══════════════════════════════════════════
# 安全白名单（只允许这些操作）
# ═══════════════════════════════════════════

SAFE_READ_COMMANDS = {
    'disk': 'df -h /',
    'memory': 'free -h',
    'cpu': 'top -bn1 | head -5',
    'uptime': 'uptime',
    'nginx_status': 'systemctl status nginx --no-pager | head -10',
    'mysql_status': 'systemctl status mysql --no-pager | head -10',
    'mysql_processlist': 'mysql -uroot -p"$MYSQL_PASSWORD" -e "SHOW PROCESSLIST;" 2>/dev/null | head -20',
    'mysql_slow': 'mysql -uroot -p"$MYSQL_PASSWORD" -N -e "SHOW STATUS LIKE \\"Slow_queries\\";" 2>/dev/null',
    'nginx_connections': 'ss -s | grep -A2 "TCP"',
    'listening_ports': 'ss -tlnp | head -20',
    'top_cpu': 'ps aux --sort=-%cpu | head -10',
    'top_mem': 'ps aux --sort=-%mem | head -10',
    'recent_logins': 'last -10',
    'failed_ssh': 'journalctl -u ssh --since "1 hour ago" | grep -c "Failed" 2>/dev/null || echo 0',
    'cert_expiry': 'echo | openssl s_client -connect www.openai2000.cn:443 -servername www.openai2000.cn 2>/dev/null | openssl x509 -noout -enddate',
}

SAFE_WRITE_COMMANDS = {
    'clean_tmp': 'find /tmp -type f -mtime +3 -delete',
    'clean_logs': 'find /var/log -name "*.gz" -mtime +7 -delete',
    'restart_nginx': 'sudo systemctl restart nginx',
    'restart_mysql': 'sudo systemctl restart mysql',
    'sync_time': 'sudo timedatectl set-ntp true',
    'drop_caches': 'sync && echo 3 | sudo tee /proc/sys/vm/drop_caches',
}

# ═══════════════════════════════════════════
# 上下文采集（给LLM提供系统现状）
# ═══════════════════════════════════════════

def collect_context():
    """采集系统当前状态作为LLM上下文"""
    ctx = {}

    # 系统资源
    try:
        ctx['disk'] = subprocess.run("df -h / | tail -1", shell=True, capture_output=True, text=True).stdout.strip()
        ctx['memory'] = subprocess.run("free -h | grep Mem", shell=True, capture_output=True, text=True).stdout.strip()
        ctx['uptime'] = subprocess.run("uptime", shell=True, capture_output=True, text=True).stdout.strip()
    except:
        pass

    # 服务状态
    try:
        status = monitor.get_status()
        ctx['services'] = status
    except:
        ctx['services'] = 'unavailable'

    # 最近告警
    try:
        stats = get_stats(24)
        ctx['alerts_24h'] = stats
    except:
        ctx['alerts_24h'] = 'unavailable'

    # 学习库
    try:
        ctx['learning'] = learner.get_stats()
    except:
        ctx['learning'] = 'unavailable'

    return ctx

# ═══════════════════════════════════════════
# LLM意图识别 + 命令生成
# ═══════════════════════════════════════════

def parse_intent(question, context):
    """用LLM解析用户意图，生成执行计划"""
    prompt = f"""你是一个服务器运维助手。用户问题：{question}

当前系统状态：
{json.dumps(context, ensure_ascii=False, indent=1)}

可用的安全读操作：{json.dumps(list(SAFE_READ_COMMANDS.keys()))}
可用的安全写操作：{json.dumps(list(SAFE_WRITE_COMMANDS.keys()))}

请返回JSON格式：
{{
  "intent": "query/exec/analyze/explain",
  "category": "disk/memory/cpu/service/mysql/nginx/alert/log/security/general",
  "commands": ["要执行的命令key列表"],
  "custom_cmd": "如果需要自定义命令（仅限只读查询），否则为空",
  "analysis_needed": true/false,
  "explanation": "简要说明"
}}

规则：
1. 优先用预定义命令，不够才用custom_cmd（只读）
2. 写操作必须用预定义命令，禁止自定义
3. 分析类问题设analysis_needed=true，我来用LLM分析
4. 不确定就返回intent=explain，给出说明"""

    result = call_llm_safe([{'role': 'user', 'content': prompt}], max_tokens=800)
    return result

# ═══════════════════════════════════════════
# 执行引擎
# ═══════════════════════════════════════════

def execute_plan(plan):
    """执行计划"""
    results = {}

    # 执行预定义命令
    for cmd_key in plan.get('commands', []):
        if cmd_key in SAFE_READ_COMMANDS:
            cmd = SAFE_READ_COMMANDS[cmd_key]
            # 环境变量替换
            cmd = cmd.replace('$MYSQL_PASSWORD', os.environ.get('MYSQL_PASSWORD', ''))
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                results[cmd_key] = r.stdout.strip()[:500]
            except Exception as e:
                results[cmd_key] = f'执行失败: {e}'
        elif cmd_key in SAFE_WRITE_COMMANDS:
            cmd = SAFE_WRITE_COMMANDS[cmd_key]
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                results[cmd_key] = f'完成 (exit={r.returncode})'
            except Exception as e:
                results[cmd_key] = f'执行失败: {e}'

    # 自定义只读命令
    custom_cmd = plan.get('custom_cmd', '')
    if custom_cmd and plan.get('intent') != 'exec':  # 只读
        # 安全检查
        dangerous = ['rm ', 'dd ', 'mkfs', 'chmod 777', '> /dev', 'shutdown', 'reboot']
        if any(d in custom_cmd.lower() for d in dangerous):
            results['custom'] = '拒绝执行：命令包含危险操作'
        else:
            try:
                r = subprocess.run(custom_cmd, shell=True, capture_output=True, text=True, timeout=15)
                results['custom'] = r.stdout.strip()[:500]
            except Exception as e:
                results['custom'] = f'执行失败: {e}'

    return results

def analyze_results(question, results, context):
    """用LLM分析执行结果"""
    prompt = f"""用户问题：{question}

系统状态：{json.dumps(context, ensure_ascii=False)[:500]}

执行结果：
{json.dumps(results, ensure_ascii=False, indent=1)}

请用简洁中文回答用户问题，包含：
1. 直接回答
2. 如果有问题，给出建议
3. 如果有风险，给出警告

保持简洁，不超过200字。"""

    result = call_llm_safe([{'role': 'user', 'content': prompt}], max_tokens=500)
    if isinstance(result, dict):
        return result.get('raw', result.get('content', str(result)))
    return str(result)

# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def chat(question):
    """自然语言运维主入口"""
    print(f"🤔 理解问题: {question}")

    # 1. 采集上下文
    context = collect_context()

    # 2. LLM意图识别
    plan = parse_intent(question, context)
    print(f"📋 意图: {plan.get('intent', 'unknown')} / {plan.get('category', 'unknown')}")
    print(f"   说明: {plan.get('explanation', '')}")

    # 3. 执行
    if plan.get('intent') == 'explain':
        # 纯解释类，直接回答
        answer = analyze_results(question, {}, context)
        return answer

    results = execute_plan(plan)

    # 4. 分析结果
    if plan.get('analysis_needed', False) or plan.get('intent') == 'analyze':
        answer = analyze_results(question, results, context)
    else:
        # 直接展示结果
        answer = f"查询结果:\n"
        for k, v in results.items():
            answer += f"\n{k}:\n{v}\n"

    return answer

# CLI
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    question = ' '.join(sys.argv[1:])
    answer = chat(question)
    print(f"\n{'='*50}")
    print(answer)
