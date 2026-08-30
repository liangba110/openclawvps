#!/usr/bin/env python3
"""
log_stream.py — 实时日志流分析（AIOps核心）
功能：
  - 实时追踪多个日志文件（tail -f 模式）
  - 自动学习正常基线（每小时/每天的正常模式）
  - 异常检测：频率突增、新模式、关键词聚类
  - LLM分析异常模式，生成预警
  - 预警通过事件总线广播

用法:
  python3 log_stream.py start         # 启动实时分析守护
  python3 log_stream.py once          # 分析一次（最近5分钟）
  python3 log_stream.py baseline      # 重建基线
  python3 log_stream.py status        # 查看状态
"""
import os
import sys
import json
import time
import re
import sqlite3
import hashlib
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# 事件总线
from event_bus import bus

DATA_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops')) / 'data'
BASELINE_DB = DATA_DIR / 'log_baseline.db'
ALERT_STATE = DATA_DIR / 'log_alert_state.json'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════
# 日志源配置
# ═══════════════════════════════════════════

LOG_SOURCES = [
    {
        'name': 'nginx_error',
        'path': '/var/log/nginx/error.log',
        'type': 'nginx_error',
        'severity': 'high',
        'patterns': {
            'upstream': r'upstream.*(?:timed out|refused|502|503)',
            'oom': r'out of memory|OOM',
            'disk_full': r'No space left on device',
            'permission': r'Permission denied',
            'connection': r'connect\(\) failed|Connection refused',
            'ssl_error': r'SSL.*error|handshake failure',
        }
    },
    {
        'name': 'nginx_access',
        'path': '/var/log/nginx/access.log',
        'type': 'nginx_access',
        'severity': 'medium',
        'patterns': {
            '5xx': r'" 5\d{2} ',
            'slow': r'" (\d{4,})ms',  # 响应>1000ms
            'scan': r'"GET /(admin|wp-login|phpmyadmin|\.env)',
            'brute': r'"POST /login.*" 401',
        }
    },
    {
        'name': 'syslog',
        'path': '/var/log/syslog',
        'type': 'syslog',
        'severity': 'medium',
        'patterns': {
            'oom_kill': r'Out of memory.*Killed',
            'disk_error': r'I/O error|EXT4-fs error',
            'ssh_brute': r'Failed password.*ssh',
            'systemd_fail': r'systemd.*Failed to start',
        }
    },
    {
        'name': 'auth_log',
        'path': '/var/log/auth.log',
        'type': 'auth',
        'severity': 'high',
        'patterns': {
            'ssh_brute': r'Failed password',
            'root_login': r'Accepted.*root',
            'sudo_fail': r'authentication failure',
        }
    },
]

# ═══════════════════════════════════════════
# 基线学习（自动学习正常模式）
# ═══════════════════════════════════════════

class BaselineLearner:
    """
    学习每个时间段的正常日志模式
    - 按小时统计错误频率
    - 按错误类型统计出现次数
    - 自动建立"正常"基线，超过基线即告警
    """
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = str(BASELINE_DB)
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.db.execute('''CREATE TABLE IF NOT EXISTS hourly_baseline (
            source TEXT,
            hour INTEGER,  -- 0-23
            pattern TEXT,
            avg_count REAL,
            max_count INTEGER,
            sample_days INTEGER,
            updated REAL,
            PRIMARY KEY (source, hour, pattern)
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS log_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL,
            source TEXT,
            pattern TEXT,
            count INTEGER,
            hour INTEGER
        )''')
        self.db.commit()

    def record(self, source, pattern_counts):
        """记录一次采样"""
        hour = datetime.now().hour
        for pattern, count in pattern_counts.items():
            self.db.execute(
                'INSERT INTO log_samples(ts, source, pattern, count, hour) VALUES(?,?,?,?,?)',
                (time.time(), source, pattern, count, hour)
            )
        self.db.commit()

    def update_baseline(self):
        """从历史采样更新基线（每天跑一次）"""
        cur = self.db.execute('''
            SELECT source, hour, pattern,
                   AVG(count) as avg_cnt,
                   MAX(count) as max_cnt,
                   COUNT(DISTINCT date(ts, 'unixepoch', 'localtime')) as days
            FROM log_samples
            WHERE ts > ?
            GROUP BY source, hour, pattern
        ''', (time.time() - 7 * 86400,))  # 最近7天

        for row in cur.fetchall():
            self.db.execute('''
                INSERT OR REPLACE INTO hourly_baseline(source, hour, pattern, avg_count, max_count, sample_days, updated)
                VALUES(?,?,?,?,?,?,?)
            ''', (*row, time.time()))
        self.db.commit()

    def get_threshold(self, source, pattern, hour=None):
        """获取异常阈值（基线的2倍或至少5次）"""
        if hour is None:
            hour = datetime.now().hour
        cur = self.db.execute(
            'SELECT avg_count, max_count FROM hourly_baseline WHERE source=? AND hour=? AND pattern=?',
            (source, hour, pattern)
        )
        row = cur.fetchone()
        if row:
            avg_cnt, max_cnt = row
            # 阈值 = max(avg*3, max*1.5, 5)
            return max(avg_cnt * 3, max_cnt * 1.5, 5)
        return 5  # 无基线时默认阈值

# ═══════════════════════════════════════════
# 实时日志追踪器
# ═══════════════════════════════════════════

class LogTailer:
    """类似 tail -f，追踪日志新增内容"""
    def __init__(self, filepath):
        self.filepath = filepath
        self._pos = 0
        self._inode = None
        self._open_file()

    def _open_file(self):
        try:
            if os.path.exists(self.filepath):
                stat = os.stat(self.filepath)
                # 日志轮转检测
                if self._inode and stat.st_ino != self._inode:
                    self._pos = 0
                self._inode = stat.st_ino
                self._f = open(self.filepath, 'r', errors='replace')
                self._f.seek(self._pos)
            else:
                self._f = None
        except:
            self._f = None

    def read_new_lines(self):
        """读取新增行"""
        if not self._f:
            self._open_file()
            if not self._f:
                return []

        try:
            lines = self._f.readlines()
            self._pos = self._f.tell()
            return [l.rstrip('\n') for l in lines if l.strip()]
        except:
            self._open_file()
            return []

# ═══════════════════════════════════════════
# 模式匹配引擎
# ═══════════════════════════════════════════

class PatternMatcher:
    """日志模式匹配 + 聚类"""
    def __init__(self):
        self._window = defaultdict(list)  # 滑动窗口
        self._window_size = 300  # 5分钟窗口

    def match(self, line, patterns):
        """匹配日志行，返回命中的模式列表"""
        matched = []
        for name, regex in patterns.items():
            if re.search(regex, line, re.IGNORECASE):
                matched.append(name)
        return matched

    def add_to_window(self, source, pattern, timestamp=None):
        """添加到滑动窗口"""
        if timestamp is None:
            timestamp = time.time()
        key = f'{source}:{pattern}'
        self._window[key].append(timestamp)
        # 清理过期
        cutoff = timestamp - self._window_size
        self._window[key] = [t for t in self._window[key] if t > cutoff]

    def get_window_count(self, source, pattern):
        """获取窗口内计数"""
        key = f'{source}:{pattern}'
        return len(self._window[key])

    def detect_burst(self, source, pattern, threshold):
        """检测突增（窗口内计数超过阈值）"""
        count = self.get_window_count(source, pattern)
        return count >= threshold, count

# ═══════════════════════════════════════════
# LLM异常分析
# ═══════════════════════════════════════════

def analyze_anomaly_llm(source, pattern, samples, count, threshold):
    """用LLM分析异常模式"""
    try:
        from brain_v2 import call_llm_safe
        prompt = f"""分析以下日志异常：

来源: {source}
模式: {pattern}
5分钟内出现: {count}次（阈值: {threshold:.0f}）
最近日志样本:
{chr(10).join(samples[:10])}

请返回JSON：
{{
  "severity": "low/medium/high/critical",
  "root_cause": "可能原因",
  "impact": "影响范围",
  "action": "建议操作",
  "auto_fix": true/false,
  "fix_cmd": "修复命令（如果auto_fix=true）"
}}"""
        result = call_llm_safe([{'role': 'user', 'content': prompt}], max_tokens=500)
        return result
    except Exception as e:
        return {'severity': 'medium', 'root_cause': f'LLM分析失败: {e}', 'action': '人工排查'}

# ═══════════════════════════════════════════
# 主分析引擎
# ═══════════════════════════════════════════

class LogStreamAnalyzer:
    def __init__(self):
        self.baseline = BaselineLearner()
        self.matcher = PatternMatcher()
        self.tailers = {}
        self.alert_state = self._load_alert_state()
        self._init_tailers()

    def _init_tailers(self):
        for src in LOG_SOURCES:
            if os.path.exists(src['path']):
                self.tailers[src['name']] = LogTailer(src['path'])

    def _load_alert_state(self):
        if ALERT_STATE.exists():
            try:
                return json.loads(ALERT_STATE.read_text())
            except:
                pass
        return {'last_alerts': {}, 'stats': {'total_lines': 0, 'total_alerts': 0}}

    def _save_alert_state(self):
        ALERT_STATE.write_text(json.dumps(self.alert_state, ensure_ascii=False, indent=1))

    def _should_alert(self, key, cooldown=300):
        """告警去重：同一key在cooldown内不重复"""
        last = self.alert_state['last_alerts'].get(key, 0)
        return time.time() - last > cooldown

    def analyze_once(self):
        """执行一次分析（读取新增日志）"""
        results = []
        total_new = 0

        for src in LOG_SOURCES:
            name = src['name']
            if name not in self.tailers:
                continue

            lines = self.tailers[name].read_new_lines()
            total_new += len(lines)

            if not lines:
                continue

            # 模式匹配
            pattern_counts = Counter()
            pattern_samples = defaultdict(list)

            for line in lines:
                matched = self.matcher.match(line, src['patterns'])
                for p in matched:
                    pattern_counts[p] += 1
                    if len(pattern_samples[p]) < 10:
                        pattern_samples[p].append(line[:200])
                    self.matcher.add_to_window(name, p)

            # 记录到基线
            self.baseline.record(name, dict(pattern_counts))

            # 检查是否超过阈值
            for pattern, count in pattern_counts.items():
                threshold = self.baseline.get_threshold(name, pattern)
                is_anomaly, window_count = self.matcher.detect_burst(name, pattern, threshold)

                if is_anomaly:
                    alert_key = f'{name}:{pattern}'
                    if self._should_alert(alert_key):
                        # LLM分析
                        analysis = analyze_anomaly_llm(
                            name, pattern, pattern_samples[pattern],
                            window_count, threshold
                        )
                        severity = analysis.get('severity', 'medium')

                        alert_data = {
                            'source': name,
                            'pattern': pattern,
                            'count': window_count,
                            'threshold': threshold,
                            'severity': severity,
                            'samples': pattern_samples[pattern][:5],
                            'analysis': analysis,
                            'timestamp': datetime.now().isoformat(),
                        }
                        results.append(alert_data)

                        # 通过事件总线广播
                        bus.emit('log_anomaly', alert_data, source='log_stream')

                        # 更新告警状态
                        self.alert_state['last_alerts'][alert_key] = time.time()
                        self.alert_state['stats']['total_alerts'] += 1

        self.alert_state['stats']['total_lines'] += total_new
        self._save_alert_state()

        return {
            'timestamp': datetime.now().isoformat(),
            'new_lines': total_new,
            'anomalies': len(results),
            'details': results,
        }

    def run_daemon(self, interval=60):
        """持续运行（默认每60秒分析一次）"""
        print(f"📡 日志流分析启动（间隔{interval}秒）")
        for src in LOG_SOURCES:
            status = '✅' if src['name'] in self.tailers else '❌'
            print(f"  {status} {src['name']}: {src['path']}")

        while True:
            try:
                result = self.analyze_once()
                if result['anomalies'] > 0:
                    for detail in result['details']:
                        icon = {'low': 'ℹ️', 'medium': '⚠️', 'high': '🚨', 'critical': '🔥'}.get(detail['severity'], '❓')
                        print(f"[{datetime.now():%H:%M:%S}] {icon} {detail['source']}:{detail['pattern']} x{detail['count']}")
                elif result['new_lines'] > 0:
                    print(f"[{datetime.now():%H:%M:%S}] ✅ 分析 {result['new_lines']} 行，无异常")
            except Exception as e:
                print(f"[{datetime.now():%H:%M:%S}] ❌ 分析异常: {e}")
            time.sleep(interval)

    def get_status(self):
        return {
            'tailers': {name: {'path': t.filepath, 'pos': t._pos} for name, t in self.tailers.items()},
            'stats': self.alert_state.get('stats', {}),
            'baseline_samples': self.baseline.db.execute('SELECT COUNT(*) FROM log_samples').fetchone()[0],
        }

# 全局实例
analyzer = LogStreamAnalyzer()

# CLI
if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'once'
    if cmd == 'start':
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        analyzer.run_daemon(interval)
    elif cmd == 'once':
        result = analyzer.analyze_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'baseline':
        analyzer.baseline.update_baseline()
        print("基线已更新")
    elif cmd == 'status':
        print(json.dumps(analyzer.get_status(), ensure_ascii=False, indent=2))
    else:
        print('用法: start [间隔秒] | once | baseline | status')
