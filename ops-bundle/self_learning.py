#!/usr/bin/env python3
"""
self_learning.py — 自学习闭环（修复结果自动反馈学习）
"""
import sqlite3
import json
import time
import os
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops')) / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

class SelfLearner:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = str(DATA_DIR / 'learning.db')
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        self.db.execute('''CREATE TABLE IF NOT EXISTS fix_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL,
            symptom TEXT,
            cause TEXT,
            action TEXT,
            result TEXT,
            success INTEGER,
            service TEXT,
            duration_ms INTEGER
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS learned_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symptom_pattern TEXT,
            recommended_action TEXT,
            success_rate REAL,
            sample_count INTEGER,
            created REAL,
            updated REAL
        )''')
        self.db.commit()
    
    def record_fix(self, symptom, cause, action, success, service='', duration_ms=0):
        """记录一次修复结果"""
        self.db.execute(
            'INSERT INTO fix_history(ts,symptom,cause,action,result,success,service,duration_ms) VALUES(?,?,?,?,?,?,?,?)',
            (time.time(), symptom, cause, action, '', int(success), service, duration_ms)
        )
        self.db.commit()
        
        # 更新学习规则
        self._update_rule(symptom, action, success)
    
    def _update_rule(self, symptom, action, success):
        """更新学习到的规则"""
        # 查找是否已有类似规则
        cur = self.db.execute(
            'SELECT id, success_rate, sample_count FROM learned_rules WHERE symptom_pattern LIKE ?',
            (f'%{symptom[:30]}%',)
        )
        existing = cur.fetchone()
        
        if existing:
            # 更新现有规则
            new_count = existing[2] + 1
            new_rate = (existing[1] * existing[2] + (1 if success else 0)) / new_count
            self.db.execute(
                'UPDATE learned_rules SET success_rate=?, sample_count=?, updated=? WHERE id=?',
                (new_rate, new_count, time.time(), existing[0])
            )
        else:
            # 创建新规则
            self.db.execute(
                'INSERT INTO learned_rules(symptom_pattern,recommended_action,success_rate,sample_count,created,updated) VALUES(?,?,?,?,?,?)',
                (symptom[:100], action, 1.0 if success else 0.0, 1, time.time(), time.time())
            )
        self.db.commit()
    
    def get_recommendation(self, symptom):
        """根据症状获取推荐修复方案"""
        cur = self.db.execute(
            'SELECT recommended_action, success_rate, sample_count FROM learned_rules WHERE symptom_pattern LIKE ? ORDER BY success_rate DESC, sample_count DESC LIMIT 3',
            (f'%{symptom[:30]}%',)
        )
        return cur.fetchall()
    
    def get_stats(self):
        """获取学习统计"""
        total = self.db.execute('SELECT COUNT(*) FROM fix_history').fetchone()[0]
        success = self.db.execute('SELECT COUNT(*) FROM fix_history WHERE success=1').fetchone()[0]
        rules = self.db.execute('SELECT COUNT(*) FROM learned_rules').fetchone()[0]
        
        return {
            'total_fixes': total,
            'successful_fixes': success,
            'success_rate': success / total if total > 0 else 0,
            'learned_rules': rules
        }
    
    def get_recent_fixes(self, limit=20):
        """获取最近的修复记录"""
        cur = self.db.execute(
            'SELECT ts, symptom, action, success, service FROM fix_history ORDER BY ts DESC LIMIT ?',
            (limit,)
        )
        return cur.fetchall()

# 全局实例
learner = SelfLearner()
