# 智能分析层模式

## EWMA 自学习基线

```python
import numpy as np

def compute_ewma(values, alpha=0.3):
    """指数加权移动平均，alpha越大越重视近期数据"""
    ewma = values[0]
    for v in values[1:]:
        ewma = alpha * v + (1 - alpha) * ewma
    return ewma

def compute_baselines(values, alpha=0.3):
    """返回基线数据：ewma + 标准差 + 异常阈值"""
    arr = np.array(values)
    ewma = compute_ewma(arr, alpha)
    std = float(np.std(arr))
    return {
        'ewma': round(float(ewma), 2),
        'std': round(std, 2),
        'upper': round(float(ewma) + 2.5 * std, 2),  # 2.5σ异常阈值
        'lower': round(float(ewma) - 2.5 * std, 2),
    }
```

## z-score 异常检测

```python
def is_anomaly(current_value, baseline):
    """当z-score > 2.5时判定为异常"""
    if baseline['std'] > 0:
        z_score = abs(current_value - baseline['ewma']) / baseline['std']
        return z_score > 2.5, z_score
    return False, 0
```

## 线性回归趋势预测

```python
def predict_disk_full(dates, values, current_day):
    """预测磁盘达到100%的天数"""
    x = np.array(dates)
    y = np.array(values)
    n = len(x)
    x_mean, y_mean = np.mean(x), np.mean(y)
    slope = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
    intercept = y_mean - slope * x_mean
    if slope > 0:
        days_to_full = (100 - intercept) / slope - current_day
        return round(days_to_full, 0)
    return None  # 不增长
```

## 根因关联

```python
from collections import defaultdict

def correlate_events(events, window_minutes=5):
    """5分钟窗口内多事件聚类 → 推断根因"""
    windows = defaultdict(list)
    for e in events:
        ts = datetime.fromisoformat(e['timestamp'])
        key = ts.strftime('%Y-%m-%d %H:') + str(ts.minute // window_minutes * window_minutes).zfill(2)
        windows[key].append(e)
    
    correlations = []
    for key, group in windows.items():
        if len(group) >= 2:
            rules = [e.get('rule', '') for e in group]
            # 规则模式匹配推断根因
            root_cause = infer_root_cause(rules)
            correlations.append({'time': key, 'rules': rules, 'root_cause': root_cause})
    return correlations
```

## 数据采集存储（SQLite）

```python
import sqlite3

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS metrics (
        timestamp TEXT, cpu REAL, mem REAL, 
        disk_root REAL, disk_data REAL,
        connections INT, mysql_conn INT, load REAL
    )""")
    return conn

def store_metrics(conn, ts, metrics):
    conn.execute("INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?)",
        (ts, metrics['cpu'], metrics['mem'], metrics['disk_root'],
         metrics['disk_data'], metrics['connections'], 
         metrics['mysql_conn'], metrics['load']))
    conn.commit()
```
