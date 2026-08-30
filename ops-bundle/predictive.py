#!/usr/bin/env python3
"""
predictive.py — 预测性运维（从"出事修"变为"提前防"）
"""
import os
import json
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops')) / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

def run_cmd(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ''

class PredictiveOps:
    def __init__(self):
        self.db_path = str(DATA_DIR / 'metrics.db')
    
    def predict_issues(self):
        """基于趋势预测未来问题"""
        predictions = []
        
        # 磁盘预测
        disk_pred = self._predict_disk()
        if disk_pred:
            predictions.append(disk_pred)
        
        # SSL证书预测
        ssl_pred = self._predict_ssl()
        if ssl_pred:
            predictions.append(ssl_pred)
        
        # MySQL连接预测
        mysql_pred = self._predict_mysql()
        if mysql_pred:
            predictions.append(mysql_pred)
        
        # 内存预测
        mem_pred = self._predict_memory()
        if mem_pred:
            predictions.append(mem_pred)
        
        return predictions
    
    def _predict_disk(self):
        """磁盘趋势预测"""
        out = run_cmd("df / | tail -1 | awk '{print $5}' | tr -d '%'")
        try:
            current = int(out)
        except:
            return None
        
        # 简单线性预测：假设每天增长0.5%
        daily_growth = 0.5
        days_to_full = (100 - current) / daily_growth if daily_growth > 0 else float('inf')
        
        if days_to_full < 30:
            severity = 'critical' if days_to_full < 3 else ('high' if days_to_full < 7 else 'medium')
            return {
                'issue': f'磁盘将在{days_to_full:.0f}天后满（当前{current}%）',
                'severity': severity,
                'action': '自动清理过期备份和日志',
                'auto_fix': days_to_full < 7,
                'metric': 'disk',
                'current': current,
                'predicted_days': days_to_full
            }
        return None
    
    def _predict_ssl(self):
        """SSL证书到期预测"""
        hosts = ['www.ttdazi.xyz', 'aiweb.openai2000.cn', 'pay.openai2000.cn', 'www.openai2000.cn']
        
        for host in hosts:
            out = run_cmd(f"echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2")
            if out:
                try:
                    from email.utils import parsedate_to_datetime
                    exp = parsedate_to_datetime(out)
                    days_left = (exp - datetime.now(exp.tzinfo)).days
                    
                    if days_left < 14:
                        severity = 'critical' if days_left < 3 else 'high'
                        return {
                            'issue': f'SSL证书{host}将在{days_left}天后到期',
                            'severity': severity,
                            'action': f'certbot renew --cert-name {host.replace("www.", "")}',
                            'auto_fix': days_left < 7,
                            'metric': 'ssl',
                            'host': host,
                            'days_left': days_left
                        }
                except:
                    pass
        return None
    
    def _predict_mysql(self):
        """MySQL连接数预测"""
        import shlex
        out = run_cmd(f"mysql -uroot -p{shlex.quote(os.environ.get('MYSQL_PASSWORD',''))} -N -e \"SHOW STATUS LIKE 'Threads_connected';\" | awk '{{print $2}}'")
        try:
            current = int(out)
        except:
            return None
        
        # 假设最大连接数151
        max_conn = 151
        if current > max_conn * 0.7:  # 超过70%
            return {
                'issue': f'MySQL连接数接近上限（{current}/{max_conn}）',
                'severity': 'high' if current > max_conn * 0.85 else 'medium',
                'action': '检查慢查询 + 优化连接池',
                'auto_fix': False,
                'metric': 'mysql_conn',
                'current': current,
                'max': max_conn
            }
        return None
    
    def _predict_memory(self):
        """内存使用预测"""
        out = run_cmd("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
        try:
            current = float(out)
        except:
            return None
        
        if current > 85:
            return {
                'issue': f'内存使用率过高（{current}%）',
                'severity': 'high' if current > 90 else 'medium',
                'action': '检查内存大户 + 重启异常进程',
                'auto_fix': False,
                'metric': 'memory',
                'current': current
            }
        return None
    
    def auto_remediate(self, predictions):
        """自动处理可修复的预测问题"""
        actions_taken = []
        
        for pred in predictions:
            if not pred.get('auto_fix'):
                continue
            
            if pred['metric'] == 'disk':
                # 清理过期备份
                out = run_cmd("find /data/disk/daily_* -mtime +7 -exec rm -rf {} + 2>/dev/null")
                actions_taken.append(f"清理磁盘: {pred['issue']}")
            
            elif pred['metric'] == 'ssl':
                # 尝试续签
                host = pred.get('host', '')
                cert_name = host.replace('www.', '')
                out = run_cmd(f"sudo certbot renew --cert-name {cert_name} --quiet 2>&1", timeout=60)
                actions_taken.append(f"续签SSL: {host}")
            
            elif pred['metric'] == 'disk' and 'clean' in pred.get('action', ''):
                # 清理日志
                run_cmd("find /var/log -name '*.log' -mtime +30 -delete 2>/dev/null")
                actions_taken.append("清理旧日志")
        
        return actions_taken

# 全局实例
predictor = PredictiveOps()
