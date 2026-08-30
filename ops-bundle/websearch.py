#!/usr/bin/env python3
"""
websearch — 通用网页搜索工具（无需web_search工具）
支持: GitHub仓库/代码, PyPI包, 普通网页(DuckDuckGo Lite)

用法:
  python3 /opt/ttdazi/ops/websearch.py github "python server monitor"
  python3 /opt/ttdazi/ops/websearch.py code "anomaly detection python"
  python3 /opt/ttdazi/ops/websearch.py pypi "process manager"
  python3 /opt/ttdazi/ops/websearch.py web "how to monitor mysql"
  python3 /opt/ttdazi/ops/websearch.py all "python ops automation"
"""
import os, sys, json, subprocess, re
from urllib.parse import quote
GITHUB_HEADERS = '-H "Accept: application/vnd.github.v3+json"' + (f' -H "Authorization: token {os.environ.get(\'GITHUB_TOKEN\', \'\')}"' if os.environ.get('GITHUB_TOKEN') else '')

def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ''

def search_github(query, limit=5):
    """搜索GitHub仓库"""
    q = query.replace(' ', '+')
    out = run(f'curl -s "https://api.github.com/search/repositories?q={q}&sort=stars&per_page={limit}"', timeout=10)
    if not out: return []
    try:
        data = json.loads(out)
        results = []
        for item in data.get('items', [])[:limit]:
            results.append({
                'title': item['full_name'],
                'url': item['html_url'],
                'stars': item['stargazers_count'],
                'description': (item.get('description') or '')[:120],
                'language': item.get('language', ''),
                'updated': item.get('updated_at', '')[:10]
            })
        return results
    except:
        return []

def search_github_code(query, limit=5):
    """搜索GitHub代码"""
    q = query.replace(' ', '+')
    out = run(f'curl -s "https://api.github.com/search/code?q={q}+language:python&per_page={limit}" -H "Accept: application/vnd.github.v3+json"', timeout=10)
    if not out: return []
    try:
        data = json.loads(out)
        results = []
        for item in data.get('items', [])[:limit]:
            results.append({
                'title': f"{item['repository']['full_name']}: {item['path']}",
                'url': item['html_url'],
                'score': item.get('score', 0)
            })
        return results
    except:
        return []

def search_pypi(query, limit=5):
    """搜索PyPI包"""
    q = query.replace(' ', '+')
    out = run(f'curl -s "https://pypi.org/search/?q={q}" -A "Mozilla/5.0"', timeout=10)
    if not out: return []
    results = []
    # 解析HTML
    packages = re.findall(r'class="package-snippet__name"[^>]*>([^<]+)<', out)
    versions = re.findall(r'class="package-snippet__version"[^>]*>([^<]+)<', out)
    descs = re.findall(r'class="package-snippet__description"[^>]*>([^<]+)<', out)
    for i in range(min(limit, len(packages))):
        results.append({
            'title': packages[i].strip() if i < len(packages) else '',
            'version': versions[i].strip() if i < len(versions) else '',
            'description': descs[i].strip()[:100] if i < len(descs) else '',
            'url': f"https://pypi.org/project/{packages[i].strip()}/" if i < len(packages) else ''
        })
    return results

def search_web(query, limit=5):
    """搜索网页（DuckDuckGo Lite）"""
    q = query.replace(' ', '+')
    out = run(f'curl -s "https://lite.duckduckgo.com/lite/?q={q}" -A "Mozilla/5.0" -L --max-time 10', timeout=12)
    if not out: return []
    results = []
    # 解析lite版HTML
    links = re.findall(r'<a[^>]+rel="nofollow"[^>]+href="([^"]+)"[^>]*>\s*<span>([^<]+)</span>', out)
    snippets = re.findall(r'<td[^>]*class="result-snippet"[^>]*>([^<]+)', out)
    for i in range(min(limit, len(links))):
        results.append({
            'title': links[i][1].strip() if i < len(links) else '',
            'url': links[i][0].strip() if i < len(links) else '',
            'snippet': snippets[i].strip()[:150] if i < len(snippets) else ''
        })
    return results

def search_all(query, limit=5):
    """综合搜索"""
    return {
        'github': search_github(query, limit),
        'code': search_github_code(query, limit),
    }

def format_results(results, search_type):
    """格式化输出"""
    if not results:
        return "无结果"

    if isinstance(results, dict):
        # 综合搜索
        output = []
        for source, items in results.items():
            if items:
                output.append(f"\n🔍 {source.upper()} ({len(items)}个结果):")
                for i, item in enumerate(items, 1):
                    stars = f" {item.get('stars',0)}⭐" if 'stars' in item else ''
                    output.append(f"  {i}. {item['title']}{stars}")
                    if item.get('description'): output.append(f"     {item['description']}")
                    output.append(f"     {item.get('url','')}")
        return '\n'.join(output)

    output = []
    for i, item in enumerate(results, 1):
        stars = f" {item.get('stars',0)}⭐" if 'stars' in item else ''
        output.append(f"{i}. {item['title']}{stars}")
        if item.get('description'): output.append(f"   {item['description']}")
        if item.get('snippet'): output.append(f"   {item['snippet']}")
        output.append(f"   {item.get('url','')}")
    return '\n'.join(output)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)

    search_type = sys.argv[1]
    query = ' '.join(sys.argv[2:])
    limit = 5

    if search_type == 'github':
        results = search_github(query, limit)
    elif search_type == 'code':
        results = search_github_code(query, limit)
    elif search_type == 'pypi':
        results = search_pypi(query, limit)
    elif search_type == 'web':
        results = search_web(query, limit)
    elif search_type == 'all':
        results = search_all(query, limit)
    else:
        print(f"未知类型: {search_type}")
        sys.exit(1)

    print(format_results(results, search_type))
