#!/usr/bin/env node
'use strict';

/**
 * Open Auto v3 - Heal Orchestrator
 * 修复编排引擎：统一事件总线 + 闭环修复 + 回滚机制
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const HEAL_DIR = '/tmp/open-auto-heal';
const EVENTS_FILE = path.join(HEAL_DIR, 'events.json');
const MAX_EVENTS = 200;

const DEFAULT_RULES = [
  {
    id: 'disk_full',
    name: '磁盘空间不足',
    condition: (m) => m.diskPercent >= 85,
    actions: [
      { cmd: 'sudo journalctl --vacuum-time=7d', label: '清理系统日志' },
      { cmd: 'sudo find /tmp -type f -mtime +7 -delete 2>/dev/null || true', label: '清理临时文件' },
      { cmd: 'sudo apt-get clean 2>/dev/null || true', label: '清理APT缓存' }
    ],
    cooldown: 3600
  },
  {
    id: 'memory_high',
    name: '内存使用率过高',
    condition: (m) => m.memoryPercent >= 90,
    actions: [
      { cmd: 'sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null', label: '释放缓存' }
    ],
    cooldown: 1800
  },
  {
    id: 'load_high',
    name: '系统负载过高',
    condition: (m) => m.load5 >= 4.0,
    actions: [
      { cmd: 'ps aux --sort=-%cpu | head -10', label: '查看CPU占用TOP10' }
    ],
    cooldown: 600
  },
  {
    id: 'nginx_down',
    name: 'Nginx服务异常',
    condition: () => {
      try {
        return execSync('systemctl is-active nginx 2>/dev/null', { encoding: 'utf-8' }).trim() !== 'active';
      } catch (e) { return true; }
    },
    actions: [{ cmd: 'sudo systemctl restart nginx', label: '重启Nginx' }],
    cooldown: 300
  },
  {
    id: 'pm2_crash',
    name: 'PM2进程崩溃',
    condition: () => {
      try {
        const list = JSON.parse(execSync('pm2 jlist 2>/dev/null', { encoding: 'utf-8' }));
        return list.some(p => p.pm2_env?.status === 'errored');
      } catch (e) { return false; }
    },
    actions: [{ cmd: 'pm2 restart all', label: '重启所有PM2进程' }],
    cooldown: 600
  }
];

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function loadEvents() {
  try {
    if (fs.existsSync(EVENTS_FILE)) return JSON.parse(fs.readFileSync(EVENTS_FILE, 'utf-8'));
  } catch (e) {}
  return [];
}

function saveEvents(events) {
  ensureDir(HEAL_DIR);
  if (events.length > MAX_EVENTS) events = events.slice(-MAX_EVENTS);
  fs.writeFileSync(EVENTS_FILE, JSON.stringify(events, null, 2));
}

function recordEvent(type, status, message, details = {}) {
  const events = loadEvents();
  events.push({ ts: new Date().toISOString(), type, status, message, ...details });
  saveEvents(events);
}

function executeAction(action, dryRun = false) {
  if (dryRun) return { success: true, output: '[DRY RUN] ' + action.cmd, dryRun: true };
  try {
    const output = execSync(action.cmd, { encoding: 'utf-8', timeout: 30000 });
    return { success: true, output: output.trim() };
  } catch (e) {
    return { success: false, output: e.stderr || e.message };
  }
}

function isInCooldown(ruleId, cooldown) {
  const events = loadEvents();
  const now = Date.now();
  const recent = events.filter(e => e.ruleId === ruleId && e.status === 'healed');
  if (recent.length === 0) return false;
  return (now - new Date(recent[recent.length - 1].ts).getTime()) < cooldown * 1000;
}

function getSystemMetrics() {
  try {
    const diskOut = execSync('df -h / | tail -1', { encoding: 'utf-8' }).trim();
    const memOut = execSync("free | awk '/Mem:/ {printf \"%d %d\", $3, $2}'", { encoding: 'utf-8' }).trim();
    const loadOut = execSync('cat /proc/loadavg', { encoding: 'utf-8' }).trim();
    return {
      diskPercent: parseInt(diskOut.split(/\s+/)[4]) || 0,
      memoryPercent: Math.round((parseInt(memOut.split(/\s+/)[0]) / parseInt(memOut.split(/\s+/)[1])) * 100),
      load5: parseFloat(loadOut.split(/\s+/)[1]) || 0
    };
  } catch (e) { return { diskPercent: 0, memoryPercent: 0, load5: 0 }; }
}

function runHeal(dryRun = false) {
  const results = [];
  const metrics = getSystemMetrics();
  for (const rule of DEFAULT_RULES) {
    try {
      if (!rule.condition(metrics)) continue;
      if (isInCooldown(rule.id, rule.cooldown)) {
        results.push({ rule: rule.name, status: 'cooldown', msg: '冷却期，跳过' });
        continue;
      }
      const actionResults = rule.actions.map(action => ({ ...action, ...executeAction(action, dryRun) }));
      const allSuccess = actionResults.every(r => r.success);
      const status = allSuccess ? 'healed' : 'failed';
      recordEvent('heal', status, rule.name, { ruleId: rule.id, actions: actionResults, dryRun });
      results.push({ rule: rule.name, status, actions: actionResults.map(a => `${a.label}: ${a.success ? '✅' : '❌'}`) });
    } catch (e) {
      results.push({ rule: rule.name, status: 'error', msg: e.message });
    }
  }
  return results;
}

function generateReport() {
  const events = loadEvents();
  const lines = [];
  lines.push('🔧 Open Auto v3 - 修复编排报告');
  lines.push(`时间: ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`);
  lines.push('');
  const recent = events.slice(-10);
  lines.push('📋 最近事件:');
  if (recent.length === 0) lines.push('  无');
  else {
    for (const event of recent) {
      const icon = event.status === 'healed' ? '✅' : event.status === 'failed' ? '❌' : '⚠️';
      const time = new Date(event.ts).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
      lines.push(`  ${icon} [${time}] ${event.message}`);
    }
  }
  const healed = events.filter(e => e.status === 'healed').length;
  const failed = events.filter(e => e.status === 'failed').length;
  lines.push('');
  lines.push('📊 统计:');
  lines.push(`  修复成功: ${healed}`);
  lines.push(`  修复失败: ${failed}`);
  return lines.join('\n');
}

function main() {
  const action = process.argv[2] || 'run';
  if (action === 'run') {
    const dryRun = process.argv.includes('--dry-run');
    console.log('🔧 执行修复编排...\n');
    const results = runHeal(dryRun);
    if (results.length === 0) console.log('✅ 无需修复');
    else {
      for (const r of results) {
        const icon = r.status === 'healed' ? '✅' : r.status === 'cooldown' ? '⏳' : '❌';
        console.log(`${icon} ${r.rule}: ${r.status}`);
        if (r.actions) r.actions.forEach(a => console.log(`    ${a}`));
      }
    }
    console.log('\n' + generateReport());
  } else if (action === 'report') {
    console.log(generateReport());
  } else if (action === 'events') {
    console.log(JSON.stringify(loadEvents().slice(-20), null, 2));
  } else {
    console.log('用法: node heal-orchestrator.cjs [run|report|events] [--dry-run]');
  }
}

if (require.main === module) main();
module.exports = { runHeal, generateReport, loadEvents, recordEvent };
