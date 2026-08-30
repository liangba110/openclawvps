from event_bus import bus
from config import MYSQL_NM
#!/usr/bin/env python3
"""
智能分析层 — 自学习基线 + 异常检测 + 趋势预测 + 根因关联 + 自动调参
用法:
  python3 /opt/ttdazi/ops/intelligence.py --collect    # 采集数据点
  python3 /opt/ttdazi/ops/intelligence.py --analyze    # 分析+预测
  python3 /opt/ttdazi/ops/intelligence.py --correlate  # 根因关联
  python3 /opt/ttdazi/ops/intelligence.py --tune       # 自动调参
  python3 /opt/ttdazi/ops/intelligence.py --report     # 综合报告

零外部依赖(只用numpy+标准库)，纯本地运算。
"""
import os
import sys
import json
import time
import subprocess
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import statistics

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'metrics.db'
BASELINES_PATH = DATA_DIR / 'baselines.json'
PREDICTIONS_PATH = DATA_DIR / 'predictions.json'

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════
# 数据采集
# ═══════════════════════════════════════════

def run_cmd(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ''

def collect_metrics():
    """采集系统指标"""
    metrics = {}
    ts = datetime.now().isoformat()
    
    # CPU使用率
    cpu = run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
    metrics['cpu_percent'] = float(cpu) if cpu else 0
    
    # 内存使用率
    mem = run_cmd("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
    metrics['mem_percent'] = float(mem) if mem else 0
    
    # 磁盘使用率
    disk_root = run_cmd("df / | tail -1 | awk '{print $5}' | tr -d '%'")
    disk_data = run_cmd("df /data/disk 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%'")
    metrics['disk_root_percent'] = float(disk_root) if disk_root else 0
    metrics['disk_data_percent'] = float(disk_data) if disk_data else 0
    
    # 网络连接数
    conns = run_cmd("ss -tn state established | wc -l")
    metrics['connections'] = int(conns) if conns.isdigit() else 0
    
    # MySQL连接数
    mysql_conn = run_cmd("mysql -uroot -p'" + os.environ.get('MYSQL_PASSWORD', '') + "' -N -e \"SHOW STATUS LIKE 'Threads_connected';\" 2>/dev/null | awk '{print $2}'")
    metrics['mysql_connections'] = int(mysql_conn) if mysql_conn.isdigit() else 0
    
    # MySQL查询数
    queries = run_cmd("mysql -uroot -p'" + os.environ.get('MYSQL_PASSWORD', '') + "' -N -e \"SHOW STATUS LIKE 'Queries';\" 2>/dev/null | awk '{print $2}'")
    metrics['mysql_queries'] = int(queries) if queries.isdigit() else 0
    
    # 负载
    load = run_cmd("cat /proc/loadavg | awk '{print $1}'")
    metrics['load_1m'] = float(load) if load else 0
    
    # 进程数
    procs = run_cmd("ps aux | wc -l")
    metrics['process_count'] = int(procs) - 1 if procs.isdigit() else 0
    
    # 磁盘IO（读写KB/s）
    diskio = run_cmd("iostat -d 1 2 2>/dev/null | tail -2 | head -1 | awk '{print $3, $4}'")
    if diskio:
        parts = diskio.split()
        metrics['disk_read_kbs'] = float(parts[0]) if len(parts) > 0 else 0
        metrics['disk_write_kbs'] = float(parts[1]) if len(parts) > 1 else 0
    else:
        metrics['disk_read_kbs'] = 0
        metrics['disk_write_kbs'] = 0
    
    # 写入数据库
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS metrics (
        timestamp TEXT, cpu REAL, mem REAL, disk_root REAL, disk_data REAL,
        connections INT, mysql_conn INT, mysql_queries INT, load REAL,
        processes INT, disk_read REAL, disk_write REAL
    )""")
    conn.execute("""
        INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (ts, metrics['cpu_percent'], metrics['mem_percent'],
          metrics['disk_root_percent'], metrics['disk_data_percent'],
          metrics['connections'], metrics['mysql_connections'],
          metrics['mysql_queries'], metrics['load_1m'],
          metrics['process_count'], metrics['disk_read_kbs'], metrics['disk_write_kbs']))
    conn.commit()
    conn.close()
    
    return metrics

# ═══════════════════════════════════════════
# 特性1: EWMA自学习基线
# ═══════════════════════════════════════════

def compute_baselines(days=7):
    """用EWMA计算自学习基线（指数加权移动平均）"""
    conn = sqlite3.connect(str(DB_PATH))
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT cpu, mem, disk_root, disk_data, connections, mysql_conn, load FROM metrics WHERE timestamp > ?",
        (cutoff,)
    ).fetchall()
    conn.close()
    
    if len(rows) < 10:
        return None
    
    data = np.array(rows) if HAS_NUMPY else [list(r) for r in rows]
    col_names = ['cpu', 'mem', 'disk_root', 'disk_data', 'connections', 'mysql_conn', 'load']
    
    baselines = {}
    alpha = 0.3  # EWMA衰减系数（越大越重视近期数据）
    
    for i, name in enumerate(col_names):
        values = [r[i] for r in rows] if not HAS_NUMPY else data[:, i]
        
        # EWMA
        if HAS_NUMPY:
            ewma = float(values[0])
            for v in values[1:]:
                ewma = alpha * float(v) + (1 - alpha) * ewma
        else:
            ewma = values[0]
            for v in values[1:]:
                ewma = alpha * v + (1 - alpha) * ewma
        
        # 标准差
        std = float(np.std(values)) if HAS_NUMPY else statistics.stdev(values) if len(values) > 1 else 0
        
        # 异常阈值 = 基线 + 2.5倍标准差
        upper = ewma + 2.5 * std
        lower = ewma - 2.5 * std
        
        baselines[name] = {
            'ewma': round(ewma, 2),
            'std': round(std, 2),
            'upper': round(upper, 2),
            'lower': round(lower, 2),
            'samples': len(rows)
        }
    
    BASELINES_PATH.write_text(json.dumps(baselines, indent=2))
    return baselines

# ═══════════════════════════════════════════
# 特性2: 滑动窗口异常检测
# ═══════════════════════════════════════════

def detect_anomalies(current_metrics, baselines=None):
    """基于EWMA基线检测当前指标是否异常"""
    if baselines is None:
        if BASELINES_PATH.exists():
            baselines = json.loads(BASELINES_PATH.read_text())
        else:
            return []
    
    anomalies = []
    mapping = {
        'cpu': 'cpu_percent', 'mem': 'mem_percent',
        'disk_root': 'disk_root_percent', 'disk_data': 'disk_data_percent',
        'connections': 'connections', 'mysql_conn': 'mysql_connections',
        'load': 'load_1m'
    }
    
    for key, metric_name in mapping.items():
        if key not in baselines or metric_name not in current_metrics:
            continue
        
        bl = baselines[key]
        value = current_metrics[metric_name]
        ewma = bl['ewma']
        std = bl['std']
        
        if std > 0:
            z_score = abs(value - ewma) / std
        else:
            z_score = 0
        
        if value > bl['upper']:
            anomalies.append({
                'metric': metric_name,
                'value': value,
                'baseline': ewma,
                'z_score': round(z_score, 2),
                'severity': 'critical' if z_score > 4 else 'warn',
                'direction': 'high',
                'detail': f'{metric_name}={value} (基线{ewma}±{std:.1f}, z={z_score:.1f})'
            })
        elif value < bl['lower'] and key not in ('disk_root', 'disk_data'):
            # 磁盘下降不算异常（清理是好事）
            anomalies.append({
                'metric': metric_name,
                'value': value,
                'baseline': ewma,
                'z_score': round(z_score, 2),
                'severity': 'info',
                'direction': 'low',
                'detail': f'{metric_name}={value} 低于基线{ewma}'
            })
    
    return anomalies

# ═══════════════════════════════════════════
# 特性3: 线性回归趋势预测
# ═══════════════════════════════════════════

def predict_trends(days_history=30, predict_days=30):
    """基于历史数据预测磁盘/资源趋势"""
    conn = sqlite3.connect(str(DB_PATH))
    cutoff = (datetime.now() - timedelta(days=days_history)).isoformat()
    rows = conn.execute(
        "SELECT timestamp, disk_root, disk_data FROM metrics WHERE timestamp > ? ORDER BY timestamp",
        (cutoff,)
    ).fetchall()
    conn.close()
    
    if len(rows) < 20:
        return None
    
    predictions = {}
    
    for col_idx, col_name in enumerate([1, 2]):
        col_key = 'disk_root' if col_idx == 0 else 'disk_data'
        # 提取时间序列
        timestamps = []
        values = []
        base_time = datetime.fromisoformat(rows[0][0]).timestamp()
        
        for row in rows:
            try:
                ts = datetime.fromisoformat(row[0]).timestamp() - base_time
                val = row[col_idx]
                if val is not None and val > 0:
                    timestamps.append(ts / 86400)  # 转换为天
                    values.append(float(val))
            except:
                continue
        
        if len(timestamps) < 10:
            continue
        
        x = np.array(timestamps) if HAS_NUMPY else timestamps
        y = np.array(values) if HAS_NUMPY else values
        
        # 最小二乘线性回归
        if HAS_NUMPY:
            n = len(x)
            x_mean = np.mean(x)
            y_mean = np.mean(y)
            slope = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
            intercept = y_mean - slope * x_mean
        else:
            n = len(x)
            x_mean = sum(x) / n
            y_mean = sum(y) / n
            slope = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)) / sum((xi - x_mean) ** 2 for xi in x)
            intercept = y_mean - slope * x_mean
        
        # 预测
        current_day = (datetime.now().timestamp() - base_time) / 86400
        current_value = slope * current_day + intercept
        
        # 预测达到100%的天数
        if slope > 0:
            days_to_full = (100 - intercept) / slope - current_day
        else:
            days_to_full = float('inf')
        
        # 预测未来N天的值
        future_values = {}
        for d in [7, 14, 30]:
            future_day = current_day + d
            future_val = slope * future_day + intercept
            future_values[f'+{d}d'] = round(float(min(future_val, 100)), 1)
        
        col = 'disk_root' if col_idx == 0 else 'disk_data'
        predictions[col] = {
            'current': round(current_value, 1),
            'daily_growth': round(slope, 3),
            'days_to_100': round(days_to_full, 0) if days_to_full < 1000 else None,
            'forecast': future_values,
            'trend': 'increasing' if slope > 0.1 else ('decreasing' if slope < -0.1 else 'stable')
        }
    
    PREDICTIONS_PATH.write_text(json.dumps(predictions, indent=2))
    return predictions

# ═══════════════════════════════════════════
# 特性4: 根因关联分析
# ═══════════════════════════════════════════

def correlate_events():
    """分析最近事件，寻找根因关联"""
    # 读取引擎日志
    logs_dir = BASE_DIR / 'logs'
    events = []
    
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = logs_dir / f'{today}.jsonl'
    if log_file.exists():
        for line in log_file.read_text().strip().split('\n'):
            if line:
                try:
                    events.append(json.loads(line))
                except:
                    pass
    
    if not events:
        return {'message': '今日无事件'}
    
    # 按时间窗口分组（5分钟内为同一事件组）
    time_windows = defaultdict(list)
    for event in events:
        try:
            ts = datetime.fromisoformat(event['timestamp'])
            window_key = ts.strftime('%Y-%m-%d %H:') + str(ts.minute // 5 * 5).zfill(2)
            time_windows[window_key].append(event)
        except:
            pass
    
    # 找关联：同一时间窗口内多个不同规则触发 = 可能有共同根因
    correlations = []
    for window_key, window_events in time_windows.items():
        if len(window_events) >= 2:
            rule_names = [e.get('rule', 'unknown') for e in window_events]
            severities = [e.get('severity', 'info') for e in window_events]
            
            # 推断根因
            root_cause = infer_root_cause(window_events)
            
            correlations.append({
                'time_window': window_key,
                'event_count': len(window_events),
                'rules': rule_names,
                'max_severity': 'critical' if 'critical' in severities else 'warn',
                'suspected_root_cause': root_cause
            })
    
    return {
        'total_events': len(events),
        'time_windows': len(time_windows),
        'correlations': correlations
    }

def infer_root_cause(events):
    """推断事件根因"""
    rules = [e.get('rule', '') for e in events]
    
    # 规则模式匹配
    if any('MySQL' in r for r in rules) and any('后端' in r for r in rules):
        return 'MySQL故障导致后端不可用'
    if any('Caddy' in r for r in rules) and any('后端' in r for r in rules):
        return 'Caddy反代故障导致所有站点不可达'
    if any('磁盘' in r for r in rules) and any('MySQL' in r for r in rules):
        return '磁盘满导致MySQL写入失败'
    if any('CPU' in r or '内存' in r for r in rules) and any('后端' in r for r in rules):
        return '资源耗尽导致服务响应超时'
    
    return '多个规则同时触发，需人工排查'

# ═══════════════════════════════════════════
# 特性5: 自动调参（根据基线动态调整阈值）
# ═══════════════════════════════════════════

def auto_tune_rules():
    """根据学习到的基线，自动调整YAML规则中的阈值"""
    if not BASELINES_PATH.exists():
        return {'message': '无基线数据，跳过'}
    
    baselines = json.loads(BASELINES_PATH.read_text())
    rules_dir = BASE_DIR / 'rules'
    changes = []
    
    # 读取数据库规则
    db_rule_file = rules_dir / 'database.yaml'
    if db_rule_file.exists():
        content = db_rule_file.read_text()
        
        # 动态调整MySQL连接数阈值
        if 'mysql_conn' in baselines:
            bl = baselines['mysql_conn']
            new_threshold = max(int(bl['upper'] * 1.5), 50)  # 基线上限的1.5倍
            
            # 替换阈值
            import re
            old_content = content
            content = re.sub(
                r'(cmd:.*Threads_connected.*threshold:\s*)\d+',
                f'\\g<1>{new_threshold}',
                content
            )
            if content != old_content:
                changes.append(f'MySQL连接数阈值 → {new_threshold} (基于EWMA基线{bl["ewma"]:.0f})')
        
        # 动态调整碎片阈值
        if 'disk_root' in baselines:
            # 磁盘碎片阈值根据当前使用率动态调整
            pass  # 碎片率本身是百分比，不需要动态调
        
        db_rule_file.write_text(content)
    
    return {'changes': changes}

# ═══════════════════════════════════════════
# 综合报告
# ═══════════════════════════════════════════

def generate_report():
    """生成综合智能分析报告"""
    print("🧠 智能分析报告")
    print("=" * 50)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 采集当前指标
    print("\n📊 当前指标:")
    metrics = collect_metrics()
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    
    # 2. 计算/更新基线
    baselines = compute_baselines()
    if baselines:
        print(f"\n📈 自学习基线 (样本: {list(baselines.values())[0]['samples']}个):")
        for k, v in baselines.items():
            print(f"  {k}: EWMA={v['ewma']}, σ={v['std']}, 上限={v['upper']}")
    
    # 3. 异常检测
    anomalies = detect_anomalies(metrics, baselines)
    if anomalies:
        print(f"\n🚨 异常检测 ({len(anomalies)}个):")
        for a in anomalies:
            icon = '🔴' if a['severity'] == 'critical' else '🟡'
            print(f"  {icon} {a['detail']}")
    else:
        print("\n✅ 无异常")
    
    # 4. 趋势预测
    predictions = predict_trends()
    if predictions:
        print("\n🔮 趋势预测:")
        for name, pred in predictions.items():
            icon = '📈' if pred['trend'] == 'increasing' else ('📉' if pred['trend'] == 'decreasing' else '➡️')
            print(f"  {icon} {name}: 当前{pred['current']}% | 日增长{pred['daily_growth']}%")
            if pred['days_to_100']:
                print(f"    ⚠️ 预计{pred['days_to_100']:.0f}天后达到100%")
            print(f"    预测: {pred['forecast']}")
    
    # 5. 根因关联
    correlations = correlate_events()
    if correlations.get('correlations'):
        print(f"\n🔗 根因关联:")
        for c in correlations['correlations']:
            print(f"  📍 {c['time_window']} | {c['event_count']}个事件")
            print(f"    规则: {', '.join(c['rules'])}")
            print(f"    疑似根因: {c['suspected_root_cause']}")
    
    # 6. 自动调参
    tune_result = auto_tune_rules()
    if tune_result.get('changes'):
        print("\n🔧 自动调参:")
        for c in tune_result['changes']:
            print(f"  ✅ {c}")
    
    print("\n" + "=" * 50)

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == '--collect':
            m = collect_metrics()
            print(json.dumps(m, indent=2))
        elif cmd == '--analyze':
            generate_report()
        elif cmd == '--baselines':
            b = compute_baselines()
            print(json.dumps(b, indent=2) if b else '数据不足')
        elif cmd == '--predict':
            p = predict_trends()
            print(json.dumps(p, indent=2) if p else '数据不足')
        elif cmd == '--correlate':
            c = correlate_events()
            print(json.dumps(c, indent=2, ensure_ascii=False))
        elif cmd == '--tune':
            r = auto_tune_rules()
            print(json.dumps(r, indent=2, ensure_ascii=False))
        else:
            print("用法: --collect | --analyze | --baselines | --predict | --correlate | --tune")
    else:
        generate_report()
