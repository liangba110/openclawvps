#!/usr/bin/env python3
"""
brain_v2.py — LLM调用加固版（缓存+重试+fallback）
"""
import os
# 自动加载 .env
from pathlib import Path as _Path
_env_file = _Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
import json
import hashlib
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops')) / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = DATA_DIR / 'llm_cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def call_llm_safe(messages, max_tokens=2000, retries=3):
    """带重试+缓存+fallback的LLM调用"""
    # 1. 查缓存（1小时内相同输入直接返回）
    cache_key = hashlib.md5(json.dumps(messages, sort_keys=True).encode()).hexdigest()
    cache_file = CACHE_DIR / f'{cache_key}.json'
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < 3600:
        try:
            return json.loads(cache_file.read_text())
        except:
            pass
    
    # 2. 重试调用
    last_err = None
    for i in range(retries):
        try:
            result = _do_call(messages, max_tokens)
            # 缓存成功结果
            cache_file.write_text(json.dumps(result, ensure_ascii=False))
            return result
        except Exception as e:
            last_err = e
            time.sleep(2 ** i)  # 指数退避
    
    # 3. Fallback：返回规则引擎结果
    return _fallback_decide(messages, last_err)

def _do_call(messages, max_tokens):
    """实际调用MiMo API"""
    import urllib.request
    
    api_key = os.environ.get('MIMO_API_KEY', '')
    base_url = os.environ.get('MIMO_BASE_URL', 'https://token-plan-cn.xiaomimimo.com/v1')
    
    if not api_key:
        raise Exception('MIMO_API_KEY未配置')
    
    payload = json.dumps({
        'model': os.environ.get('MIMO_MODEL', 'mimo-v2.5-pro'),
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': 0.1,
    }).encode('utf-8')
    
    req = urllib.request.Request(
        f'{base_url}/chat/completions',
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST'
    )
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
        msg = data['choices'][0]['message']
        content = msg.get('content', '') or ''
        reasoning = msg.get('reasoning_content', '') or ''
        raw = content if content.strip() else reasoning
        
        # 安全提取JSON
        return _extract_json(raw)

def _extract_json(text):
    """安全提取嵌套JSON"""
    start = text.find('{')
    if start < 0:
        return {'raw': text[:500]}
    
    depth = 0
    end = start
    for i in range(start, len(text)):
        if text[i] == '{': depth += 1
        elif text[i] == '}': depth -= 1
        if depth == 0:
            end = i + 1
            break
    
    try:
        return json.loads(text[start:end])
    except:
        return {'raw': text[:500], 'parse_error': True}

def _fallback_decide(messages, error=None):
    """Fallback到规则引擎"""
    # 从消息中提取关键词，匹配规则库
    text = str(messages).lower()
    
    rules = {
        'mysql': {'action': 'restart', 'service': 'mysql', 'confidence': 0.7},
        '连接数': {'action': 'check_connections', 'confidence': 0.6},
        '磁盘': {'action': 'cleanup', 'confidence': 0.8},
        '内存': {'action': 'check_memory', 'confidence': 0.6},
        'cpu': {'action': 'check_processes', 'confidence': 0.6},
        'nginx': {'action': 'restart', 'service': 'nginx', 'confidence': 0.8},
        'ssl': {'action': 'renew_cert', 'confidence': 0.9},
    }
    
    for keyword, rule in rules.items():
        if keyword in text:
            return {
                'analysis': f'基于规则匹配: {keyword}',
                'actions': [{'cmd': rule['action'], 'reason': f'规则匹配: {keyword}', 'risk': 'low'}],
                'confidence': rule['confidence'],
                'needs_human': False,
                'source': 'fallback_rules',
                'error': str(error)[:100] if error else None
            }
    
    return {
        'analysis': 'LLM调用失败且无匹配规则',
        'actions': [],
        'confidence': 0,
        'needs_human': True,
        'source': 'fallback',
        'error': str(error)[:100] if error else 'unknown'
    }
