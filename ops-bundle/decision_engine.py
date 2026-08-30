#!/usr/bin/env python3
"""
decision_engine — AI决策引擎
混合架构：规则匹配 + 推理链 + LLM调用（可选）

当规则引擎无法处理时，启动推理链分析：
1. 收集上下文（服务状态/日志/历史事件）
2. 模式匹配（已知问题库）
3. 因果推理（A→B→C链式分析）
4. 决策输出（自动修复/升级人工/忽略）

用法:
  python3 /opt/ttdazi/ops/decision_engine.py analyze   # 分析当前所有异常
  python3 /opt/ttdazi/ops/decision_engine.py diagnose "症状描述"  # 诊断特定问题
  python3 /opt/ttdazi/ops/decision_engine.py learn      # 从历史事件学习
"""
import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
KNOWLEDGE_BASE = BASE_DIR / 'data' / 'knowledge_base.json'
HISTORY_FILE = BASE_DIR / 'data' / 'alerts' / 'history.jsonl'

def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ''

# ═══════════════════════════════════════════
# 知识库（已知问题+解决方案）
# ═══════════════════════════════════════════

DEFAULT_KNOWLEDGE = {
    "patterns": [
        {
            "symptoms": ["HTTP 502", "HTTP 503", "服务无响应"],
            "cause": "服务进程崩溃或未启动",
            "solution": "systemctl restart <service>",
            "auto_fix": True,
            "confidence": 0.9
        },
        {
            "symptoms": ["CPU > 90%", "load average 高", "响应慢"],
            "cause": "资源耗尽（死循环/内存泄漏/流量突增）",
            "solution": "top查看进程 → kill异常进程 → 检查日志",
            "auto_fix": False,
            "confidence": 0.7
        },
        {
            "symptoms": ["磁盘满", "No space left", "disk 100%"],
            "cause": "日志/备份/临时文件积累",
            "solution": "清理过期文件 + 扩容",
            "auto_fix": True,
            "confidence": 0.95
        },
        {
            "symptoms": ["Connection refused", "ECONNREFUSED"],
            "cause": "目标服务未监听端口",
            "solution": "检查服务状态 + 端口绑定",
            "auto_fix": True,
            "confidence": 0.85
        },
        {
            "symptoms": ["SSL证书", "证书过期", "TLS handshake failed"],
            "cause": "证书到期或配置错误",
            "solution": "certbot renew + reload nginx/caddy",
            "auto_fix": True,
            "confidence": 0.9
        },
        {
            "symptoms": ["SSH爆破", "Failed password", "brute force"],
            "cause": "SSH暴露公网被扫描",
            "solution": "fail2ban封禁IP + 更换端口",
            "auto_fix": True,
            "confidence": 0.95
        },
        {
            "symptoms": ["MySQL连接数高", "Too many connections"],
            "cause": "连接泄漏或并发过高",
            "solution": "show processlist → kill idle连接 → 检查代码",
            "auto_fix": False,
            "confidence": 0.8
        },
        {
            "symptoms": ["内存OOM", "Out of memory", "killed process"],
            "cause": "内存不足",
            "solution": "free -h → 找内存大户 → 重启/优化",
            "auto_fix": False,
            "confidence": 0.85
        },
        {
            "symptoms": ["nginx 502", "upstream timed out"],
            "cause": "nginx反代后端超时",
            "solution": "检查后端服务 + 增加proxy_read_timeout",
            "auto_fix": True,
            "confidence": 0.8
        },
        {
            "symptoms": ["数据库碎片", "DATA_FREE 高", "表碎片"],
            "cause": "频繁增删导致InnoDB碎片",
            "solution": "OPTIMIZE TABLE",
            "auto_fix": True,
            "confidence": 0.95
        }
    ],
    "causal_chains": [
        {
            "trigger": "MySQL宕机",
            "effects": ["后端502", "支付失败", "数据写入失败"],
            "root_cause_candidates": ["磁盘满", "内存不足", "配置错误", "并发过高"],
            "priority": "critical"
        },
        {
            "trigger": "磁盘满",
            "effects": ["MySQL写入失败", "日志无法记录", "临时文件创建失败"],
            "root_cause_candidates": ["备份未清理", "日志过大", "临时文件积累"],
            "priority": "critical"
        },
        {
            "trigger": "Caddy/Nginx挂",
            "effects": ["所有站点不可达", "SSL终止失败", "API不可用"],
            "root_cause_candidates": ["配置语法错误", "证书问题", "端口冲突"],
            "priority": "critical"
        }
    ]
}

def load_knowledge():
    """加载知识库"""
    if KNOWLEDGE_BASE.exists():
        try:
            return json.loads(KNOWLEDGE_BASE.read_text())
        except:
            pass
    return DEFAULT_KNOWLEDGE

def save_knowledge(kb):
    """保存知识库"""
    KNOWLEDGE_BASE.write_text(json.dumps(kb, ensure_ascii=False, indent=2))

# ═══════════════════════════════════════════
# 上下文收集器
# ═══════════════════════════════════════════

def collect_context():
    """收集当前系统状态作为决策上下文"""
    ctx = {}

    # 服务状态
    services = {}
    for svc in ['ttdazi', 'ttdazi-pay', 'aiweb', 'mysql', 'caddy', 'ops-engine']:
        active = run(f"systemctl is-active {svc}")
        pid = run(f"systemctl show {svc} --property=MainPID --value")
        services[svc] = {'active': active == 'active', 'pid': pid}
    ctx['services'] = services

    # 资源
    ctx['cpu'] = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
    ctx['memory'] = run("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
    ctx['disk_root'] = run("df / | tail -1 | awk '{print $5}' | tr -d '%'")
    ctx['disk_data'] = run("df /data/disk 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%'")
    ctx['load'] = run("cat /proc/loadavg | awk '{print $1}'")
    ctx['connections'] = run("ss -tn state established | wc -l")

    # MySQL
    ctx['mysql_conn'] = run("mysql -uroot -p'" + os.environ.get('MYSQL_PASSWORD', '') + "' -N -e \"SHOW STATUS LIKE 'Threads_connected';\" | awk '{print $2}'")
    ctx['mysql_queries'] = run("mysql -uroot -p'" + os.environ.get('MYSQL_PASSWORD', '') + "' -N -e \"SHOW STATUS LIKE 'Queries';\" | awk '{print $2}'")

    # 最近错误
    recent_errors = []
    for log in ['/var/log/auth.log', '/opt/ttdazi/backend/app/ttdazi.log']:
        if os.path.exists(log):
            out = run(f"tail -20 {log} | grep -iE 'error|exception|fatal' | tail -3")
            if out:
                recent_errors.extend(out.split('\n'))
    ctx['recent_errors'] = [e.strip() for e in recent_errors if e.strip()][:5]

    return ctx

# ═══════════════════════════════════════════
# 推理引擎
# ═══════════════════════════════════════════

def diagnose(symptoms_text):
    """根据症状描述诊断问题"""
    kb = load_knowledge()
    matches = []

    for pattern in kb['patterns']:
        score = 0
        matched_symptoms = []
        for symptom in pattern['symptoms']:
            if symptom.lower() in symptoms_text.lower():
                score += 1
                matched_symptoms.append(symptom)
        if score > 0:
            matches.append({
                'pattern': pattern,
                'score': score,
                'matched': matched_symptoms,
                'confidence': pattern['confidence'] * (score / len(pattern['symptoms']))
            })

    matches.sort(key=lambda x: x['confidence'], reverse=True)
    return matches[:3]

def analyze_anomalies():
    """分析当前所有异常，给出综合诊断"""
    ctx = collect_context()
    issues = []

    # 检查每个指标
    checks = {
        'cpu': ('CPU', float(ctx.get('cpu', 0) or 0), 80, 90),
        'memory': ('内存', float(ctx.get('memory', 0) or 0), 80, 90),
        'disk_root': ('系统盘', float(ctx.get('disk_root', 0) or 0), 80, 90),
        'disk_data': ('数据盘', float(ctx.get('disk_data', 0) or 0), 80, 90),
        'load': ('负载', float(ctx.get('load', 0) or 0), 4, 8),
        'mysql_conn': ('MySQL连接', int(ctx.get('mysql_conn', 0) or 0), 80, 120),
    }

    for key, (name, value, warn, crit) in checks.items():
        if value >= crit:
            severity = 'critical'
        elif value >= warn:
            severity = 'warn'
        else:
            continue

        # 诊断
        matches = diagnose(f"{name} {value}")
        root_cause = matches[0]['pattern']['cause'] if matches else '未知'
        solution = matches[0]['pattern']['solution'] if matches else '需人工排查'
        auto_fix = matches[0]['pattern']['auto_fix'] if matches else False

        issues.append({
            'metric': name,
            'value': value,
            'threshold': warn,
            'severity': severity,
            'root_cause': root_cause,
            'solution': solution,
            'auto_fix': auto_fix,
            'confidence': matches[0]['confidence'] if matches else 0.5
        })

    # 检查服务
    for svc, info in ctx.get('services', {}).items():
        if not info['active']:
            matches = diagnose(f"{svc} 服务无响应 HTTP 502")
            issues.append({
                'metric': f'服务:{svc}',
                'value': 'down',
                'severity': 'critical',
                'root_cause': matches[0]['pattern']['cause'] if matches else '服务未运行',
                'solution': matches[0]['pattern']['solution'] if matches else f'systemctl restart {svc}',
                'auto_fix': True,
                'confidence': matches[0]['confidence'] if matches else 0.9
            })

    # 因果链分析
    causal_analysis = analyze_causal_chains(issues)

    return {
        'timestamp': datetime.now().isoformat(),
        'context': {k: v for k, v in ctx.items() if k != 'recent_errors'},
        'issues': issues,
        'causal_analysis': causal_analysis,
        'recommendation': generate_recommendation(issues, causal_analysis)
    }

def analyze_causal_chains(issues):
    """因果链分析"""
    kb = load_knowledge()
    results = []

    for chain in kb.get('causal_chains', []):
        trigger_found = False
        for issue in issues:
            if chain['trigger'] in issue.get('metric', '') or chain['trigger'] in issue.get('root_cause', ''):
                trigger_found = True
                break

        if trigger_found:
            # 检查是否有连锁效应
            effects_found = []
            for issue in issues:
                for effect in chain['effects']:
                    if effect in issue.get('metric', '') or effect in issue.get('root_cause', ''):
                        effects_found.append(effect)

            if effects_found:
                results.append({
                    'chain': chain['trigger'],
                    'effects': effects_found,
                    'root_cause_candidates': chain['root_cause_candidates'],
                    'priority': chain['priority']
                })

    return results

def generate_recommendation(issues, causal_chains):
    """生成综合建议"""
    if not issues:
        return {'action': 'none', 'message': '系统正常，无需处理'}

    # 按严重度排序
    critical = [i for i in issues if i['severity'] == 'critical']
    warns = [i for i in issues if i['severity'] == 'warn']

    recommendations = []

    # 优先处理critical
    for issue in critical:
        if issue['auto_fix'] and issue['confidence'] > 0.8:
            recommendations.append({
                'priority': 'high',
                'action': 'auto_fix',
                'target': issue['metric'],
                'command': issue['solution'],
                'reason': f"{issue['root_cause']} (置信度{issue['confidence']:.0%})"
            })
        else:
            recommendations.append({
                'priority': 'high',
                'action': 'escalate',
                'target': issue['metric'],
                'message': f"{issue['metric']}: {issue['root_cause']}",
                'reason': '需要人工介入'
            })

    # 处理warn
    for issue in warns:
        recommendations.append({
            'priority': 'medium',
            'action': 'monitor',
            'target': issue['metric'],
            'message': f"{issue['metric']}={issue['value']}, 建议: {issue['solution']}"
        })

    # 因果链建议
    for chain in causal_chains:
        recommendations.insert(0, {
            'priority': 'critical',
            'action': 'chain_alert',
            'message': f"🔗 因果链: {chain['chain']} → {', '.join(chain['effects'])}",
            'root_cause_candidates': chain['root_cause_candidates']
        })

    return {
        'action': 'fix' if any(r['action'] == 'auto_fix' for r in recommendations) else 'escalate',
        'recommendations': recommendations
    }

# ═══════════════════════════════════════════
# 学习器（从历史事件中学习）
# ═══════════════════════════════════════════

def learn_from_history():
    """分析历史告警，提取新模式"""
    if not HISTORY_FILE.exists():
        return {'new_patterns': 0}

    alerts = []
    for line in HISTORY_FILE.read_text().strip().split('\n'):
        if line:
            try:
                alerts.append(json.loads(line))
            except:
                pass

    # 分析高频告警
    msg_counts = {}
    for a in alerts:
        msg = a.get('message', '')[:50]
        msg_counts[msg] = msg_counts.get(msg, 0) + 1

    # 高频出现的可能是新模式
    new_patterns = []
    kb = load_knowledge()
    existing_symptoms = set()
    for p in kb['patterns']:
        existing_symptoms.update(p['symptoms'])

    for msg, count in msg_counts.items():
        if count >= 3:  # 出现3次以上
            # 检查是否已在知识库中
            found = False
            for symptom in existing_symptoms:
                if symptom.lower() in msg.lower():
                    found = True
                    break
            if not found:
                new_patterns.append({'message': msg, 'count': count})

    return {
        'total_alerts': len(alerts),
        'frequent': len([m for m, c in msg_counts.items() if c >= 3]),
        'new_patterns': new_patterns[:5]
    }

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'analyze'

    if cmd == 'analyze':
        result = analyze_anomalies()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'diagnose' and len(sys.argv) > 2:
        symptom = ' '.join(sys.argv[2:])
        matches = diagnose(symptom)
        print(json.dumps(matches, ensure_ascii=False, indent=2))
    elif cmd == 'learn':
        result = learn_from_history()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('用法: analyze | diagnose <症状> | learn')
