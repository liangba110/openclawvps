#!/usr/bin/env node
'use strict';

/**
 * Open Auto v3 - Security Guard
 * 安全自愈模块：恶意IP检测 + 自动封禁 + SSH暴力破解防护
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const SECURITY_DIR = '/tmp/open-auto-security';
const BLOCKED_IPS_FILE = path.join(SECURITY_DIR, 'blocked_ips.json');
const ATTACK_LOG_FILE = path.join(SECURITY_DIR, 'attack_log.json');
const MAX_ATTACK_LOG = 500;

const THRESHOLDS = {
  ssh_fail_per_min: 5,
  ssh_fail_per_hour: 20,
  http_4xx_per_min: 50,
  http_5xx_per_min: 10,
  concurrent_connections: 200,
  ban_duration_hours: 24
};

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function parseSSHFailures() {
  const failures = {};
  try {
    const log = execSync('journalctl -u sshd --since "1 hour ago" 2>/dev/null || cat /var/log/auth.log 2>/dev/null | tail -500', { encoding: 'utf-8' });
    for (const line of log.split('\n')) {
      if (line.includes('Failed password') || line.includes('Invalid user')) {
        const match = line.match(/from (\d+\.\d+\.\d+\.\d+)/);
        if (match) failures[match[1]] = (failures[match[1]] || 0) + 1;
      }
    }
  } catch (e) {}
  return failures;
}

function getBlockedIPs() {
  try {
    if (fs.existsSync(BLOCKED_IPS_FILE)) return JSON.parse(fs.readFileSync(BLOCKED_IPS_FILE, 'utf-8'));
  } catch (e) {}
  return {};
}

function saveBlockedIPs(blocked) {
  ensureDir(SECURITY_DIR);
  fs.writeFileSync(BLOCKED_IPS_FILE, JSON.stringify(blocked, null, 2));
}

function logAttack(ip, type, details) {
  ensureDir(SECURITY_DIR);
  let logs = [];
  try {
    if (fs.existsSync(ATTACK_LOG_FILE)) logs = JSON.parse(fs.readFileSync(ATTACK_LOG_FILE, 'utf-8'));
  } catch (e) {}
  logs.push({ ts: new Date().toISOString(), ip, type, details });
  if (logs.length > MAX_ATTACK_LOG) logs = logs.slice(-MAX_ATTACK_LOG);
  fs.writeFileSync(ATTACK_LOG_FILE, JSON.stringify(logs, null, 2));
}

function blockIP(ip, reason) {
  const blocked = getBlockedIPs();
  const now = Date.now();
  if (blocked[ip] && blocked[ip].expires > now) return { action: 'already_blocked', ip };

  const expires = now + THRESHOLDS.ban_duration_hours * 3600 * 1000;
  try {
    execSync(`sudo iptables -A INPUT -s ${ip} -j DROP 2>/dev/null || true`);
    execSync(`sudo ip6tables -A INPUT -s ${ip} -j DROP 2>/dev/null || true`);
  } catch (e) {}

  blocked[ip] = { blockedAt: new Date().toISOString(), expires, reason, autoBlocked: true };
  saveBlockedIPs(blocked);
  logAttack(ip, 'blocked', reason);
  return { action: 'blocked', ip, expires: new Date(expires).toISOString() };
}

function unblockIP(ip) {
  const blocked = getBlockedIPs();
  if (!blocked[ip]) return { action: 'not_found', ip };
  try {
    execSync(`sudo iptables -D INPUT -s ${ip} -j DROP 2>/dev/null || true`);
    execSync(`sudo ip6tables -D INPUT -s ${ip} -j DROP 2>/dev/null || true`);
  } catch (e) {}
  delete blocked[ip];
  saveBlockedIPs(blocked);
  return { action: 'unblocked', ip };
}

function cleanupExpiredBlocks() {
  const blocked = getBlockedIPs();
  const now = Date.now();
  let cleaned = 0;
  for (const [ip, info] of Object.entries(blocked)) {
    if (info.expires < now) { unblockIP(ip); cleaned++; }
  }
  return cleaned;
}

function getConnections() {
  try {
    const out = execSync('ss -s', { encoding: 'utf-8' });
    const match = out.match(/estab\s+(\d+)/);
    return match ? parseInt(match[1]) : 0;
  } catch (e) { return 0; }
}

function scanAndBlock() {
  const results = [];
  const cleaned = cleanupExpiredBlocks();
  if (cleaned > 0) results.push(`清理 ${cleaned} 个过期封禁`);

  const sshFailures = parseSSHFailures();
  for (const [ip, count] of Object.entries(sshFailures)) {
    if (count >= THRESHOLDS.ssh_fail_per_hour) {
      const result = blockIP(ip, `SSH暴力破解: ${count}次/小时`);
      results.push(`[${result.action}] ${ip} - SSH暴力破解 ${count}次`);
    }
  }

  const connections = getConnections();
  if (connections > THRESHOLDS.concurrent_connections) {
    results.push(`⚠️ 异常连接数: ${connections} (阈值: ${THRESHOLDS.concurrent_connections})`);
  }
  return results;
}

function generateReport() {
  const lines = [];
  lines.push('🛡️ Open Auto v3 - 安全报告');
  lines.push(`时间: ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`);
  lines.push('');

  const blocked = getBlockedIPs();
  const activeBlocks = Object.entries(blocked).filter(([, info]) => info.expires > Date.now());
  lines.push(`🚫 活跃封禁: ${activeBlocks.length} 个IP`);
  for (const [ip, info] of activeBlocks.slice(0, 10)) {
    const expires = new Date(info.expires).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
    lines.push(`  ${ip} - ${info.reason} (到期: ${expires})`);
  }

  const sshFailures = parseSSHFailures();
  const failCount = Object.values(sshFailures).reduce((a, b) => a + b, 0);
  lines.push('');
  lines.push(`🔑 SSH失败尝试: ${failCount} 次/小时`);
  const topAttackers = Object.entries(sshFailures).sort((a, b) => b[1] - a[1]).slice(0, 5);
  for (const [ip, count] of topAttackers) lines.push(`  ${ip}: ${count} 次`);

  const connections = getConnections();
  lines.push('');
  lines.push(`🔗 当前连接数: ${connections}`);
  return lines.join('\n');
}

function main() {
  const action = process.argv[2] || 'scan';
  if (action === 'scan') {
    console.log('🔍 扫描安全威胁...\n');
    const results = scanAndBlock();
    if (results.length > 0) results.forEach(r => console.log(r));
    else console.log('✅ 未发现安全威胁');
    console.log('\n' + generateReport());
  } else if (action === 'report') {
    console.log(generateReport());
  } else if (action === 'block') {
    const ip = process.argv[3];
    const reason = process.argv[4] || '手动封禁';
    if (!ip) { console.log('用法: security-guard.cjs block <ip> [reason]'); return; }
    console.log(JSON.stringify(blockIP(ip, reason), null, 2));
  } else if (action === 'unblock') {
    const ip = process.argv[3];
    if (!ip) { console.log('用法: security-guard.cjs unblock <ip>'); return; }
    console.log(JSON.stringify(unblockIP(ip), null, 2));
  } else if (action === 'list') {
    console.log(JSON.stringify(getBlockedIPs(), null, 2));
  } else {
    console.log('用法: node security-guard.cjs [scan|report|block|unblock|list]');
  }
}

if (require.main === module) main();
module.exports = { scanAndBlock, blockIP, unblockIP, generateReport, getBlockedIPs };
