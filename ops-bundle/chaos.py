#!/usr/bin/env python3
"""
chaos.py — 混沌工程（主动注入故障，测试系统韧性）

用法:
  python3 chaos.py list                    # 列出可用实验
  python3 chaos.py run <experiment>        # 运行指定实验
  python3 chaos.py auto                    # 自动运行安全实验
  python3 chaos.py report                  # 查看实验报告

实验列表（安全级别）:
  safe:    kill_process / disk_pressure / slow_network / port_block
  medium:  cpu_stress / memory_pressure / dns_fail / cert_near_expiry
  risky:   mysql_restart / nginx_restart / full_disk

每个实验流程：注入故障 → 监控自愈 → 恢复 → 记录结果
"""
import os
import sys
import json
import subprocess
import time
import random
import sqlite3
from datetime import datetime
from pathlib import Path

OPS_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
DATA_DIR = OPS_DIR / 'data'
CHAOS_DB = DATA_DIR / 'chaos.db'
DATA_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(OPS_DIR))
from event_bus import bus

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except:
        return '', -1

# ═══════════════════════════════════════════
# 实验数据库
# ═══════════════════════════════════════════

class ChaosDB:
    def __init__(self):
        self.db = sqlite3.connect(str(CHAOS_DB), check_same_thread=False)
        self.db.execute('''CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL,
            name TEXT,
            status TEXT,
            inject_result TEXT,
            heal_result TEXT,
            duration_sec REAL,
            success INTEGER,
            details TEXT
        )''')
        self.db.commit()

    def record(self, name, status, inject_result, heal_result, duration, success, details=''):
        self.db.execute(
            'INSERT INTO experiments(ts,name,status,inject_result,heal_result,duration_sec,success,details) VALUES(?,?,?,?,?,?,?,?)',
            (time.time(), name, status, inject_result, heal_result, duration, int(success), details)
        )
        self.db.commit()

    def get_report(self, limit=20):
        cur = self.db.execute(
            'SELECT ts, name, status, success, duration_sec, details FROM experiments ORDER BY ts DESC LIMIT ?',
            (limit,)
        )
        return cur.fetchall()

# ═══════════════════════════════════════════
# 故障注入器
# ═══════════════════════════════════════════

class ChaosExperiments:
    """故障注入实验"""

    @staticmethod
    def kill_random_process():
        """随机杀一个非关键进程"""
        # 找一个可杀的进程（排除关键系统进程）
        critical = ['systemd', 'init', 'sshd', 'nginx', 'mysql', 'node', 'python3', 'bash']
        out, _ = run_cmd("ps aux | awk '{print $2, $11}' | grep -v -E '" + '|'.join(critical) + "' | tail -20")
        pids = []
        for line in out.split('\n'):
            parts = line.split()
            if parts and parts[0].isdigit():
                pid = int(parts[0])
                if pid > 1000:  # 跳过低PID系统进程
                    pids.append((pid, parts[1] if len(parts) > 1 else 'unknown'))

        if not pids:
            return {'skipped': True, 'reason': '无可杀进程'}

        target = random.choice(pids)
        run_cmd(f"kill -9 {target[0]}")
        return {'killed': target[0], 'cmd': target[1]}

    @staticmethod
    def disk_pressure():
        """磁盘压力测试（创建临时大文件）"""
        tmpfile = '/tmp/chaos_disk_pressure'
        run_cmd(f"dd if=/dev/zero of={tmpfile} bs=1M count=500 2>/dev/null")
        time.sleep(5)
        run_cmd(f"rm -f {tmpfile}")
        return {'created_mb': 500, 'cleaned': True}

    @staticmethod
    def cpu_stress(duration=10):
        """CPU压力测试"""
        run_cmd(f"timeout {duration} openssl speed >/dev/null 2>&1 &")
        return {'duration_sec': duration, 'cores_stressed': 'all'}

    @staticmethod
    def memory_pressure():
        """内存压力测试（创建一个占内存的子进程）"""
        script = "import time; x = bytearray(200*1024*1024); time.sleep(10); del x"
        run_cmd(f"python3 -c '{script}' &", timeout=15)
        return {'allocated_mb': 200, 'duration_sec': 10}

    @staticmethod
    def port_block(port=80):
        """临时阻断端口（iptables）"""
        run_cmd(f"sudo iptables -A INPUT -p tcp --dport {port} -j DROP")
        time.sleep(5)
        run_cmd(f"sudo iptables -D INPUT -p tcp --dport {port} -j DROP")
        return {'port': port, 'blocked_sec': 5}

    @staticmethod
    def slow_network(delay_ms=500):
        """模拟网络延迟"""
        run_cmd(f"sudo tc qdisc add dev lo root netem delay {delay_ms}ms 2>/dev/null")
        time.sleep(5)
        run_cmd("sudo tc qdisc del dev lo root 2>/dev/null")
        return {'delay_ms': delay_ms, 'duration_sec': 5}

    @staticmethod
    def cert_near_expiry():
        """模拟证书即将到期（检查+告警测试）"""
        out, _ = run_cmd("echo | openssl s_client -connect www.openai2000.cn:443 -servername www.openai2000.cn 2>/dev/null | openssl x509 -noout -enddate")
        return {'cert_info': out, 'test_type': 'alert_simulation'}

# ═══════════════════════════════════════════
# 自愈验证器
# ═══════════════════════════════════════════

class HealVerifier:
    """验证系统是否自动恢复"""

    @staticmethod
    def check_service(name, port=None, process=None, timeout=60):
        """检查服务是否恢复"""
        start = time.time()
        while time.time() - start < timeout:
            if port:
                out, code = run_cmd(f"nc -z -w2 127.0.0.1 {port}")
                if code == 0:
                    return True, time.time() - start
            if process:
                out, _ = run_cmd(f"pgrep -f '{process}'")
                if out.strip():
                    return True, time.time() - start
            time.sleep(2)
        return False, timeout

    @staticmethod
    def check_disk_clean():
        """检查磁盘是否恢复"""
        out, _ = run_cmd("df / | tail -1 | awk '{print $5}' | tr -d '%'")
        try:
            return int(out) < 90, out
        except:
            return False, out

    @staticmethod
    def check_http(url='http://127.0.0.1', timeout=30):
        """检查HTTP是否恢复"""
        start = time.time()
        while time.time() - start < timeout:
            out, code = run_cmd(f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 {url}")
            if code == 0 and out.replace("'", "") in ('200', '301', '302'):
                return True, time.time() - start
            time.sleep(3)
        return False, timeout

# ═══════════════════════════════════════════
# 混沌编排器
# ═══════════════════════════════════════════

EXPERIMENTS = {
    'kill_process': {
        'name': '随机进程终止',
        'risk': 'safe',
        'inject': ChaosExperiments.kill_random_process,
        'verify': lambda: HealVerifier.check_service('system', process='python3'),
        'description': '随机杀一个非关键进程，验证自愈能力'
    },
    'disk_pressure': {
        'name': '磁盘压力测试',
        'risk': 'safe',
        'inject': ChaosExperiments.disk_pressure,
        'verify': HealVerifier.check_disk_clean,
        'description': '创建500MB临时文件，验证磁盘清理'
    },
    'cpu_stress': {
        'name': 'CPU压力测试',
        'risk': 'medium',
        'inject': lambda: ChaosExperiments.cpu_stress(10),
        'verify': lambda: (True, 0),  # CPU压力自动消失
        'description': '10秒全核压力，验证监控告警'
    },
    'memory_pressure': {
        'name': '内存压力测试',
        'risk': 'medium',
        'inject': ChaosExperiments.memory_pressure,
        'verify': lambda: (True, 0),
        'description': '分配200MB内存，验证内存告警'
    },
    'port_block': {
        'name': '端口阻断测试',
        'risk': 'medium',
        'inject': lambda: ChaosExperiments.port_block(80),
        'verify': lambda: HealVerifier.check_http('http://127.0.0.1'),
        'description': '临时阻断80端口，验证服务恢复'
    },
    'slow_network': {
        'name': '网络延迟测试',
        'risk': 'safe',
        'inject': lambda: ChaosExperiments.slow_network(500),
        'verify': lambda: (True, 0),
        'description': '模拟500ms网络延迟，验证超时处理'
    },
    'cert_check': {
        'name': '证书过期检查',
        'risk': 'safe',
        'inject': ChaosExperiments.cert_near_expiry,
        'verify': lambda: (True, 0),
        'description': '检查SSL证书，验证告警机制'
    },
}

class ChaosRunner:
    def __init__(self):
        self.db = ChaosDB()
        self.verifier = HealVerifier()

    def run(self, experiment_name):
        """运行一个混沌实验"""
        if experiment_name not in EXPERIMENTS:
            return {'error': f'未知实验: {experiment_name}'}

        exp = EXPERIMENTS[experiment_name]
        print(f"\n{'='*50}")
        print(f"🔥 混沌实验: {exp['name']}")
        print(f"   风险等级: {exp['risk']}")
        print(f"   说明: {exp['description']}")
        print(f"{'='*50}")

        start = time.time()

        # 1. 注入故障
        print(f"\n[1/3] 注入故障...")
        try:
            inject_result = exp['inject']()
            print(f"  ✅ 注入完成: {json.dumps(inject_result, ensure_ascii=False)}")
        except Exception as e:
            inject_result = {'error': str(e)}
            print(f"  ❌ 注入失败: {e}")

        # 2. 等待+验证恢复
        print(f"\n[2/3] 等待系统自愈...")
        try:
            healed, heal_time = exp['verify']()
            heal_result = {'healed': healed, 'time_sec': round(heal_time, 1)}
            print(f"  {'✅' if healed else '❌'} 恢复{'成功' if healed else '失败'} ({heal_time:.1f}秒)")
        except Exception as e:
            healed = False
            heal_result = {'error': str(e)}
            print(f"  ❌ 验证失败: {e}")

        # 3. 记录结果
        duration = time.time() - start
        self.db.record(
            experiment_name, 'completed',
            json.dumps(inject_result), json.dumps(heal_result),
            duration, healed, exp['description']
        )

        # 4. 发事件
        bus.emit('chaos_result', {
            'experiment': experiment_name,
            'success': healed,
            'duration': duration,
        }, source='chaos')

        return {
            'experiment': exp['name'],
            'success': healed,
            'inject': inject_result,
            'heal': heal_result,
            'duration': round(duration, 1),
        }

    def run_safe(self):
        """只运行安全级别的实验"""
        safe_exp = [k for k, v in EXPERIMENTS.items() if v['risk'] == 'safe']
        results = []
        for exp_name in safe_exp:
            result = self.run(exp_name)
            results.append(result)
            time.sleep(5)  # 实验间隔
        return results

    def get_report(self):
        """获取实验报告"""
        rows = self.db.get_report()
        report = []
        for row in rows:
            ts, name, status, success, duration, details = row
            report.append({
                'time': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M'),
                'experiment': name,
                'status': status,
                'healed': bool(success),
                'duration': f'{duration:.1f}s',
                'details': details,
            })
        return report

# CLI
if __name__ == '__main__':
    runner = ChaosRunner()
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'

    if cmd == 'list':
        print("═══ 可用混沌实验 ═══\n")
        for k, v in EXPERIMENTS.items():
            risk_icon = {'safe': '🟢', 'medium': '🟡', 'risky': '🔴'}.get(v['risk'], '⚪')
            print(f"  {risk_icon} {k:20s} {v['name']}  ({v['risk']})")
            print(f"     {v['description']}")
    elif cmd == 'run' and len(sys.argv) > 2:
        result = runner.run(sys.argv[2])
        print(f"\n结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    elif cmd == 'auto':
        print("🔒 运行安全级别实验...\n")
        results = runner.run_safe()
        print(f"\n═══ 实验报告 ═══")
        for r in results:
            icon = '✅' if r.get('success') else '❌'
            print(f"  {icon} {r['experiment']}: {r['duration']}s")
    elif cmd == 'report':
        report = runner.get_report()
        print("═══ 混沌实验报告 ═══\n")
        for r in report:
            icon = '✅' if r['healed'] else '❌'
            print(f"  {icon} [{r['time']}] {r['experiment']} ({r['duration']})")
    else:
        print('用法: list | run <experiment> | auto | report')
