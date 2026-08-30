#!/usr/bin/env node
'use strict';

/**
 * Open Auto v3 - Knowledge Base
 * 知识库模块：故障案例归档 + LLM生成运维手册 + 经验积累
 */

const fs = require('fs');
const path = require('path');

const KB_DIR = '/tmp/open-auto-kb';
const CASES_FILE = path.join(KB_DIR, 'cases.json');
const RUNBOOK_FILE = path.join(KB_DIR, 'runbook.md');
const MAX_CASES = 500;

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function loadCases() {
  try {
    if (fs.existsSync(CASES_FILE)) return JSON.parse(fs.readFileSync(CASES_FILE, 'utf-8'));
  } catch (e) {}
  return [];
}

function saveCases(cases) {
  ensureDir(KB_DIR);
  if (cases.length > MAX_CASES) cases = cases.slice(-MAX_CASES);
  fs.writeFileSync(CASES_FILE, JSON.stringify(cases, null, 2));
}

function recordCase(caseData) {
  const cases = loadCases();
  const entry = {
    id: Date.now().toString(36),
    ts: new Date().toISOString(),
    category: caseData.category || 'unknown',
    title: caseData.title,
    symptoms: caseData.symptoms || [],
    rootCause: caseData.rootCause || '',
    solution: caseData.solution || '',
    commands: caseData.commands || [],
    severity: caseData.severity || 'medium',
    resolved: caseData.resolved || false,
    tags: caseData.tags || []
  };
  cases.push(entry);
  saveCases(cases);
  return entry;
}

function searchCases(query) {
  const cases = loadCases();
  const q = query.toLowerCase();
  return cases.filter(c =>
    c.title.toLowerCase().includes(q) ||
    c.symptoms.some(s => s.toLowerCase().includes(q)) ||
    c.rootCause.toLowerCase().includes(q) ||
    c.solution.toLowerCase().includes(q) ||
    c.tags.some(t => t.toLowerCase().includes(q))
  );
}

function getStats() {
  const cases = loadCases();
  const categories = {};
  const severities = { low: 0, medium: 0, high: 0, critical: 0 };
  let resolved = 0;
  for (const c of cases) {
    categories[c.category] = (categories[c.category] || 0) + 1;
    severities[c.severity] = (severities[c.severity] || 0) + 1;
    if (c.resolved) resolved++;
  }
  return { total: cases.length, resolved, unresolved: cases.length - resolved, categories, severities };
}

function generateRunbook() {
  const cases = loadCases();
  const lines = [];
  lines.push('# Open Auto 运维手册');
  lines.push(`生成时间: ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`);
  lines.push('');
  lines.push('---');
  lines.push('');

  const grouped = {};
  for (const c of cases) {
    if (!grouped[c.category]) grouped[c.category] = [];
    grouped[c.category].push(c);
  }

  for (const [category, items] of Object.entries(grouped)) {
    lines.push(`## ${category}`);
    lines.push('');
    const sorted = items.sort((a, b) => {
      const order = { critical: 0, high: 1, medium: 2, low: 3 };
      return (order[a.severity] || 99) - (order[b.severity] || 99);
    });
    for (const item of sorted) {
      lines.push(`### ${item.title}`);
      lines.push(`- **严重程度**: ${item.severity}`);
      lines.push(`- **状态**: ${item.resolved ? '✅ 已解决' : '❌ 未解决'}`);
      lines.push('');
      if (item.symptoms.length > 0) {
        lines.push('**症状**:');
        item.symptoms.forEach(s => lines.push(`- ${s}`));
        lines.push('');
      }
      if (item.rootCause) {
        lines.push('**根因**:');
        lines.push(item.rootCause);
        lines.push('');
      }
      if (item.solution) {
        lines.push('**解决方案**:');
        lines.push(item.solution);
        lines.push('');
      }
      if (item.commands.length > 0) {
        lines.push('**修复命令**:');
        lines.push('```bash');
        item.commands.forEach(cmd => lines.push(cmd));
        lines.push('```');
        lines.push('');
      }
      if (item.tags.length > 0) {
        lines.push(`**标签**: ${item.tags.join(', ')}`);
        lines.push('');
      }
      lines.push('---');
      lines.push('');
    }
  }
  return lines.join('\n');
}

function saveRunbook() {
  const content = generateRunbook();
  ensureDir(KB_DIR);
  fs.writeFileSync(RUNBOOK_FILE, content);
  return RUNBOOK_FILE;
}

function addPresetCases() {
  const presets = [
    {
      category: '磁盘',
      title: '磁盘空间不足导致服务异常',
      symptoms: ['网站502错误', '数据库写入失败', '日志无法写入'],
      rootCause: '日志文件过大、备份文件堆积、临时文件未清理',
      solution: '清理日志、删除旧备份、清理临时文件',
      commands: ['sudo journalctl --vacuum-time=7d', 'sudo find /tmp -type f -mtime +7 -delete', 'sudo apt-get clean'],
      severity: 'high', resolved: true, tags: ['磁盘', '空间', '清理']
    },
    {
      category: '内存',
      title: '内存使用率过高导致OOM',
      symptoms: ['进程被kill', '系统响应缓慢', 'OOM Killer日志'],
      rootCause: '内存泄漏、缓存未释放、进程异常占用',
      solution: '释放缓存、重启问题进程',
      commands: ['sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches', 'pm2 restart all'],
      severity: 'high', resolved: true, tags: ['内存', 'OOM', '缓存']
    },
    {
      category: 'Nginx',
      title: 'Nginx配置错误导致502',
      symptoms: ['网站502错误', 'Nginx启动失败'],
      rootCause: '配置语法错误、端口冲突、证书过期',
      solution: '检查配置、修复语法、重启服务',
      commands: ['sudo nginx -t', 'sudo systemctl restart nginx'],
      severity: 'critical', resolved: true, tags: ['Nginx', '502', '配置']
    },
    {
      category: 'PM2',
      title: 'PM2进程频繁崩溃',
      symptoms: ['Node.js服务不可用', 'PM2日志显示错误'],
      rootCause: '代码bug、依赖缺失、内存溢出',
      solution: '检查日志、修复代码、重启服务',
      commands: ['pm2 logs --lines 50', 'pm2 restart all', 'pm2 monit'],
      severity: 'high', resolved: true, tags: ['PM2', 'Node.js', '崩溃']
    },
    {
      category: '数据库',
      title: 'SQLite数据库损坏',
      symptoms: ['查询报错', '数据丢失', '数据库锁定'],
      rootCause: '异常断电、并发写入冲突、磁盘空间不足',
      solution: '从备份恢复、修复数据库',
      commands: ['sqlite3 database.db "PRAGMA integrity_check;"', 'cp /data/backups/latest.db database.db'],
      severity: 'critical', resolved: true, tags: ['SQLite', '数据库', '损坏']
    }
  ];

  let added = 0;
  for (const preset of presets) {
    const existing = searchCases(preset.title);
    if (existing.length === 0) { recordCase(preset); added++; }
  }
  return added;
}

function generateReport() {
  const stats = getStats();
  const cases = loadCases();
  const lines = [];
  lines.push('📚 Open Auto v3 - 知识库报告');
  lines.push(`时间: ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`);
  lines.push('');
  lines.push('📊 统计:');
  lines.push(`  总案例: ${stats.total}`);
  lines.push(`  已解决: ${stats.resolved}`);
  lines.push(`  未解决: ${stats.unresolved}`);
  lines.push('');
  lines.push('📂 分类:');
  for (const [cat, count] of Object.entries(stats.categories)) lines.push(`  ${cat}: ${count}`);
  lines.push('');
  lines.push('⚠️ 严重程度:');
  for (const [sev, count] of Object.entries(stats.severities)) {
    if (count > 0) lines.push(`  ${sev}: ${count}`);
  }
  const recent = cases.slice(-5);
  if (recent.length > 0) {
    lines.push('');
    lines.push('📋 最近案例:');
    for (const c of recent) lines.push(`  ${c.resolved ? '✅' : '❌'} ${c.title} [${c.category}]`);
  }
  return lines.join('\n');
}

function main() {
  const action = process.argv[2] || 'report';
  if (action === 'init') {
    console.log('初始化知识库...\n');
    console.log(`添加 ${addPresetCases()} 个预置案例`);
    console.log('\n' + generateReport());
  } else if (action === 'add') {
    const title = process.argv[3];
    const category = process.argv[4] || '未分类';
    if (!title) { console.log('用法: knowledge-base.cjs add "标题" [分类]'); return; }
    const entry = recordCase({ title, category, symptoms: [], solution: '', resolved: false });
    console.log(`✅ 已添加案例: ${entry.id}`);
  } else if (action === 'search') {
    const query = process.argv[3];
    if (!query) { console.log('用法: knowledge-base.cjs search "关键词"'); return; }
    const results = searchCases(query);
    console.log(`找到 ${results.length} 个相关案例:\n`);
    for (const r of results) {
      console.log(`- ${r.title} [${r.category}]`);
      if (r.solution) console.log(`  解决方案: ${r.solution}`);
    }
  } else if (action === 'runbook') {
    const file = saveRunbook();
    console.log(`✅ 运维手册已生成: ${file}`);
    console.log('\n' + generateRunbook());
  } else if (action === 'report') {
    console.log(generateReport());
  } else if (action === 'list') {
    console.log(JSON.stringify(loadCases().slice(-20), null, 2));
  } else {
    console.log('用法: node knowledge-base.cjs [init|add|search|runbook|report|list]');
  }
}

if (require.main === module) main();
module.exports = { recordCase, searchCases, generateRunbook, getStats, addPresetCases };
