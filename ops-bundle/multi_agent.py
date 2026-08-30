#!/usr/bin/env python3
"""
multi_agent.py — 多智能体协作框架
5个Agent协作处理事件：监控→诊断→修复→学习→报告
"""
import os
import sys
import json
import subprocess
import time
from pathlib import Path
import shlex
from datetime import datetime

OPS_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
DATA_DIR = OPS_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except:
        return '', -1

# ═══════════════════════════════════════════
# Agent 1: 监控Agent
# ═══════════════════════════════════════════
class MonitorAgent:
    def collect_metrics(self):
        """采集系统指标"""
        metrics = {}
        
        # CPU
        out, _ = run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
        metrics['cpu'] = float(out) if out else 0
        
        # 内存
        out, _ = run_cmd("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
        metrics['memory'] = float(out) if out else 0
        
        # 磁盘
        out, _ = run_cmd("df / | tail -1 | awk '{print $5}' | tr -d '%'")
        metrics['disk'] = int(out) if out.isdigit() else 0
        
        # MySQL连接
        out, _ = run_cmd("mysql -uroot -p$(shlex.quote(os.environ.get('MYSQL_PASSWORD',''))) -N -e \"SHOW STATUS LIKE 'Threads_connected';\" | awk '{print $2}'")
        metrics['mysql_conn'] = int(out) if out.isdigit() else 0
        
        # 负载
        out, _ = run_cmd("cat /proc/loadavg | awk '{print $1}'")
        metrics['load'] = float(out) if out else 0
        
        # 服务状态
        for svc in ['ttdazi', 'ttdazi-pay', 'aiweb', 'mysql', 'caddy']:
            out, _ = run_cmd(f"systemctl is-active {svc}")
            metrics[f'svc_{svc}'] = out == 'active'
        
        return metrics
    
    def detect_anomalies(self, metrics):
        """检测异常"""
        anomalies = []
        
        if metrics.get('cpu', 0) > 80:
            anomalies.append({'type': 'cpu_high', 'value': metrics['cpu'], 'severity': 'high'})
        if metrics.get('memory', 0) > 85:
            anomalies.append({'type': 'memory_high', 'value': metrics['memory'], 'severity': 'high'})
        if metrics.get('disk', 0) > 85:
            anomalies.append({'type': 'disk_high', 'value': metrics['disk'], 'severity': 'critical'})
        if metrics.get('mysql_conn', 0) > 100:
            anomalies.append({'type': 'mysql_conn_high', 'value': metrics['mysql_conn'], 'severity': 'high'})
        
        for svc in ['ttdazi', 'ttdazi-pay', 'aiweb', 'mysql', 'caddy']:
            if not metrics.get(f'svc_{svc}', True):
                anomalies.append({'type': 'service_down', 'service': svc, 'severity': 'critical'})
        
        return anomalies

# ═══════════════════════════════════════════
# Agent 2: 诊断Agent
# ═══════════════════════════════════════════
class DiagnoseAgent:
    def analyze(self, anomaly):
        """分析异常根因"""
        atype = anomaly.get('type', '')
        
        # 规则匹配
        rules = {
            'cpu_high': {
                'cause': '进程占用过高CPU',
                'check': 'top -bn1 | head -15',
                'auto_fix_safe': True,
                'action': 'check_processes'
            },
            'memory_high': {
                'cause': '内存使用过高',
                'check': 'free -h && ps aux --sort=-%mem | head -5',
                'auto_fix_safe': False,
                'action': 'check_memory'
            },
            'disk_high': {
                'cause': '磁盘空间不足',
                'check': 'df -h && du -sh /data/disk/* | sort -rh | head -5',
                'auto_fix_safe': True,
                'action': 'cleanup_disk'
            },
            'mysql_conn_high': {
                'cause': 'MySQL连接数过高',
                'check': f"mysql -uroot -p{shlex.quote(os.environ.get('MYSQL_PASSWORD',''))} -e \"SHOW PROCESSLIST;\"",
                'auto_fix_safe': False,
                'action': 'check_mysql'
            },
            'service_down': {
                'cause': f'服务{anomaly.get("service", "")}未运行',
                'check': f'systemctl status {anomaly.get("service", "")}',
                'auto_fix_safe': True,
                'action': 'restart_service'
            },
        }
        
        rule = rules.get(atype, {'cause': '未知异常', 'check': 'echo unknown', 'auto_fix_safe': False, 'action': 'unknown'})
        
        # 执行诊断命令
        out, _ = run_cmd(rule['check'])
        
        return {
            'anomaly': anomaly,
            'cause': rule['cause'],
            'diagnostic_output': out[:500],
            'auto_fix_safe': rule['auto_fix_safe'],
            'action': rule['action']
        }

# ═══════════════════════════════════════════
# Agent 3: 修复Agent
# ═══════════════════════════════════════════
class FixerAgent:
    def execute(self, diagnosis):
        """执行修复"""
        action = diagnosis.get('action', '')
        service = diagnosis.get('anomaly', {}).get('service', '')
        
        fix_commands = {
            'restart_service': f'sudo systemctl restart {service}',
            'cleanup_disk': 'find /data/disk/daily_* -mtime +7 -exec rm -rf {} + 2>/dev/null; find /var/log -name "*.log" -mtime +30 -delete 2>/dev/null',
            'check_processes': 'echo "检查完成，需人工分析"',
            'check_memory': 'echo "检查完成，需人工分析"',
            'check_mysql': 'echo "检查完成，需人工分析"',
        }
        
        cmd = fix_commands.get(action, 'echo "未知操作"')
        out, code = run_cmd(cmd, timeout=60)
        
        # 验证修复结果
        if action == 'restart_service' and service:
            time.sleep(3)
            status, _ = run_cmd(f"systemctl is-active {service}")
            success = status == 'active'
        else:
            success = code == 0
        
        return {
            'action': action,
            'success': success,
            'output': out[:200],
            'service': service
        }

# ═══════════════════════════════════════════
# Agent 4: 学习Agent
# ═══════════════════════════════════════════
class LearnerAgent:
    def find_similar(self, anomaly):
        """查找类似历史事件"""
        try:
            sys.path.insert(0, str(OPS_DIR))
            from self_learning import learner
            return learner.get_recommendation(anomaly.get('type', ''))
        except:
            return []
    
    def record(self, incident, diagnosis, result):
        """记录修复结果"""
        try:
            sys.path.insert(0, str(OPS_DIR))
            from self_learning import learner
            learner.record_fix(
                symptom=incident.get('type', ''),
                cause=diagnosis.get('cause', ''),
                action=result.get('action', ''),
                success=result.get('success', False),
                service=incident.get('service', '')
            )
        except:
            pass

# ═══════════════════════════════════════════
# Agent 5: 报告Agent
# ═══════════════════════════════════════════
class ReporterAgent:
    def generate(self, incident, diagnosis, result):
        """生成事件报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'incident': incident,
            'diagnosis': diagnosis.get('cause', ''),
            'action': result.get('action', ''),
            'success': result.get('success', False),
            'output': result.get('output', '')[:200]
        }
        
        # 保存报告
        report_file = DATA_DIR / 'incident_reports.jsonl'
        with open(report_file, 'a') as f:
            f.write(json.dumps(report, ensure_ascii=False) + '\n')
        
        return report

# ═══════════════════════════════════════════
# 编排器
# ═══════════════════════════════════════════
class AgentOrchestrator:
    def __init__(self):
        self.monitor = MonitorAgent()
        self.diagnose = DiagnoseAgent()
        self.fixer = FixerAgent()
        self.learner = LearnerAgent()
        self.reporter = ReporterAgent()
    
    def run_cycle(self):
        """执行一次完整周期：监控→诊断→修复→学习→报告"""
        # 1. 监控
        metrics = self.monitor.collect_metrics()
        anomalies = self.monitor.detect_anomalies(metrics)
        
        if not anomalies:
            return {'status': 'ok', 'message': '所有指标正常'}
        
        # 2. 处理每个异常
        results = []
        for anomaly in anomalies:
            # 诊断
            diagnosis = self.diagnose.analyze(anomaly)
            
            # 查历史
            history = self.learner.find_similar(anomaly)
            
            # 修复
            if diagnosis['auto_fix_safe']:
                result = self.fixer.execute(diagnosis)
            else:
                result = {'status': 'escalated', 'reason': '需要人工确认', 'action': diagnosis['action']}
            
            # 学习
            self.learner.record(anomaly, diagnosis, result)
            
            # 报告
            report = self.reporter.generate(anomaly, diagnosis, result)
            results.append(report)
        
        return {
            'status': 'actioned' if any(r.get('success') for r in results) else 'escalated',
            'anomalies': len(anomalies),
            'results': results
        }

# 全局实例
orchestrator = AgentOrchestrator()
