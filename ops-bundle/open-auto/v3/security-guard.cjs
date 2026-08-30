#!/usr/bin/env node
/* 安全自愈：监控nginx日志 → 检测攻击 → 自动封禁IP → SSL证书检查 */
const { execSync } = require("node:child_process");
const fs = require("fs");
const path = require("path");

const LOG_DIR = "/opt/ai-ecom-site/data/logs";
const LOG = path.join(LOG_DIR, "security-guard.log");
const BANNED_FILE = path.join(LOG_DIR, "banned-ips.json");
const NGINX_LOG = "/var/log/nginx/access.log";
const FAIL2BAN = "/usr/bin/fail2ban-client";

function log(m) {
  const line = "[" + new Date().toISOString().slice(0, 19).replace("T", " ") + "] " + m;
  console.log(line);
  fs.appendFileSync(LOG, line + "\n");
}

function run(cmd, timeout = 15000) {
  try { return execSync(cmd, { encoding: "utf8", timeout }).trim(); } catch { return ""; }
}

// 检测nginx日志中的异常请求
function analyzeNginxLog() {
  if (!fs.existsSync(NGINX_LOG)) return [];
  // 读取最近5000行
  const lines = run("tail -5000 " + NGINX_LOG, 20000);
  if (!lines) return [];

  const ipCounts = {};
  const attacks = [];
  const now = Date.now() / 1000;

  for (const line of lines.split("\n")) {
    const ip = line.split(" ")[0];
    if (!ip || ip === "127.0.0.1" || ip === "::1") continue;

    // SQL注入检测
    if (/union\s+(all\s+)?select|or\s+1\s*=\s*1|'\s*or\s*'|drop\s+table|insert\s+into|--\s*$|\/\*|\*\//i.test(line)) {
      attacks.push({ ip, type: "sql_injection", line: line.slice(0, 200) });
    }
    // XSS检测
    if (/<script|javascript:|onerror=|onload=|eval\(|document\.cookie/i.test(line)) {
      attacks.push({ ip, type: "xss", line: line.slice(0, 200) });
    }
    // 路径遍历
    if (/\.\.\/|\.\.\\|%2e%2e|%252e%252e/i.test(line)) {
      attacks.push({ ip, type: "path_traversal", line: line.slice(0, 200) });
    }
    // 扫描器特征（大量404）
    if (/ 404 /.test(line)) {
      ipCounts[ip] = (ipCounts[ip] || 0) + 1;
    }
  }

  // 404超过50次的IP视为扫描器
  for (const [ip, count] of Object.entries(ipCounts)) {
    if (count > 50) {
      attacks.push({ ip, type: "scanner", count });
    }
  }

  return attacks;
}

// 封禁IP（iptables）
function banIP(ip) {
  // 检查是否已封禁
  const existing = run("iptables -L INPUT -n 2>/dev/null | grep " + ip);
  if (existing.includes(ip)) return false;

  try {
    run("iptables -A INPUT -s " + ip + " -j DROP");
    log("🚫 封禁IP: " + ip);
    // 记录到文件
    const banned = (() => { try { return JSON.parse(fs.readFileSync(BANNED_FILE, "utf8")); } catch { return []; } })();
    banned.push({ ip, ts: new Date().toISOString(), reason: "auto-ban" });
    while (banned.length > 200) banned.shift();
    fs.writeFileSync(BANNED_FILE, JSON.stringify(banned, null, 2));
    return true;
  } catch (e) {
    log("封禁失败 " + ip + ": " + e.message);
    return false;
  }
}

// 解封IP（超过24小时自动解封）
function unbanOldIPs() {
  const banned = (() => { try { return JSON.parse(fs.readFileSync(BANNED_FILE, "utf8")); } catch { return []; } })();
  const now = Date.now();
  const keep = [];
  for (const entry of banned) {
    const age = now - new Date(entry.ts).getTime();
    if (age > 24 * 3600 * 1000) {
      try { run("iptables -D INPUT -s " + entry.ip + " -j DROP"); log("✅ 解封IP: " + entry.ip); } catch {}
    } else {
      keep.push(entry);
    }
  }
  fs.writeFileSync(BANNED_FILE, JSON.stringify(keep, null, 2));
}

// SSL证书检查
function checkSSL() {
  const domains = ["ai.openai2000.cn", "www.openai2000.cn", "dazi.openai2000.cn"];
  const alerts = [];
  for (const domain of domains) {
    const result = run(`echo | openssl s_client -servername ${domain} -connect ${domain}:443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null`);
    if (!result) { alerts.push({ domain, error: "无法获取证书信息" }); continue; }
    const match = result.match(/notAfter=(.+)/);
    if (!match) continue;
    const expiry = new Date(match[1]);
    const daysLeft = Math.floor((expiry - Date.now()) / 86400000);
    if (daysLeft < 7) {
      alerts.push({ domain, daysLeft, expiry: match[1], severity: daysLeft < 3 ? "critical" : "high" });
      // 尝试自动续签
      if (daysLeft < 3) tryAutoRenew(domain);
    }
  }
  return alerts;
}

function tryAutoRenew(domain) {
  log("⚠️ SSL证书即将到期，尝试续签: " + domain);
  try {
    run("certbot renew --cert-name " + domain + " --quiet", 60000);
    log("SSL续签命令已执行: " + domain);
  } catch (e) {
    log("SSL续签失败: " + e.message);
  }
}

// 检查SSH暴力破解
function checkSSHBruteForce() {
  const authLog = run("journalctl -u sshd --since '10 min ago' --no-pager 2>/dev/null | grep 'Failed password'");
  if (!authLog) return [];
  const ipCounts = {};
  for (const line of authLog.split("\n")) {
    const m = line.match(/from (\d+\.\d+\.\d+\.\d+)/);
    if (m) ipCounts[m[1]] = (ipCounts[m[1]] || 0) + 1;
  }
  const attackers = [];
  for (const [ip, count] of Object.entries(ipCounts)) {
    if (count > 10) {
      attackers.push({ ip, type: "ssh_brute_force", count });
      banIP(ip);
    }
  }
  return attackers;
}

// 主流程
try {
  fs.mkdirSync(LOG_DIR, { recursive: true });
  const allAlerts = [];

  // 1. Nginx日志分析
  const attacks = analyzeNginxLog();
  if (attacks.length > 0) {
    log("⚠️ 检测到 " + attacks.length + " 条攻击");
    // 按IP聚合去重，只封禁攻击次数>=3的IP
    const ipAttacks = {};
    for (const a of attacks) { ipAttacks[a.ip] = (ipAttacks[a.ip] || 0) + 1; }
    for (const [ip, count] of Object.entries(ipAttacks)) {
      if (count >= 3) banIP(ip);
    }
    allAlerts.push(...attacks);
  }

  // 2. SSH暴力破解检测
  const sshAttacks = checkSSHBruteForce();
  if (sshAttacks.length > 0) {
    log("⚠️ SSH暴力破解: " + sshAttacks.length + " 个IP");
    allAlerts.push(...sshAttacks);
  }

  // 3. 自动解封旧IP
  unbanOldIPs();

  // 4. SSL证书检查（每小时只在整点执行）
  const minute = new Date().getMinutes();
  if (minute < 5) {
    const sslAlerts = checkSSL();
    if (sslAlerts.length > 0) {
      log("⚠️ SSL告警: " + JSON.stringify(sslAlerts));
      allAlerts.push(...sslAlerts);
    }
  }

  if (allAlerts.length > 0) {
    log("总告警: " + allAlerts.length + " 条");
    process.exit(2);
  }
  log("OK 无安全威胁");
  process.exit(0);
} catch (e) {
  log("ERROR " + e.message);
  process.exit(1);
}
