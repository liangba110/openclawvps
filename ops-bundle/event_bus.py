#!/usr/bin/env python3
"""
event_bus.py — 统一事件总线
SQLite持久化 + 内存订阅 + 线程安全
"""
import sqlite3
import json
import threading
import time
import os
from collections import defaultdict
from pathlib import Path
from datetime import datetime

EVENTS_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops')) / 'data'
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

class EventBus:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = str(EVENTS_DIR / 'events.db')
        self.db_path = db_path
        self._init_db()
        self._handlers = defaultdict(list)
        self._lock = threading.Lock()
    
    def _init_db(self):
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL,
            type TEXT,
            source TEXT,
            data TEXT,
            handled INTEGER DEFAULT 0
        )''')
        self.db.commit()
    
    def emit(self, event_type, data, source='system'):
        """发布事件"""
        with self._lock:
            self.db.execute(
                'INSERT INTO events(ts,type,source,data) VALUES(?,?,?,?)',
                (time.time(), event_type, source, json.dumps(data, ensure_ascii=False))
            )
            self.db.commit()
        
        # 触发订阅的handler
        for handler in self._handlers.get(event_type, []):
            try:
                threading.Thread(target=handler, args=(data,), daemon=True).start()
            except Exception:
                pass
        # 通配符*
        for handler in self._handlers.get('*', []):
            try:
                threading.Thread(target=handler, args=(data,), daemon=True).start()
            except Exception:
                pass
    
    def on(self, event_type, handler):
        """订阅事件"""
        self._handlers[event_type].append(handler)
    
    def query(self, event_type=None, since=None, limit=100):
        """查询事件"""
        q = 'SELECT * FROM events WHERE 1=1'
        params = []
        if event_type:
            q += ' AND type=?'
            params.append(event_type)
        if since:
            q += ' AND ts>?'
            params.append(since)
        q += ' ORDER BY ts DESC LIMIT ?'
        params.append(limit)
        return self.db.execute(q, params).fetchall()
    
    def mark_handled(self, event_id):
        """标记事件已处理"""
        self.db.execute('UPDATE events SET handled=1 WHERE id=?', (event_id,))
        self.db.commit()
    
    def cleanup(self, days=7):
        """清理旧事件"""
        cutoff = time.time() - days * 86400
        self.db.execute('DELETE FROM events WHERE ts<?', (cutoff,))
        self.db.commit()

# 全局实例
bus = EventBus()
