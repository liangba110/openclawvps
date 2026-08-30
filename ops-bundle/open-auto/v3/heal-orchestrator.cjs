#!/usr/bin/env node
/*
 * 自愈编排引擎：健康检查 → 诊断 → 修复 → 验证 → 回滚
 * 每3小时运行一次
 */
const { execSync } = require("node:child_process");
const fs = require("fs");
const path = require("path");

const LOG_DIR = "/opt/ai-ecom-site/data/logs";
const LOG = path.join(LOG_DIR, "heal-orchestrator.log");
const EVENTS_FILE = path.join(LOG_DIR, "heal-events.json");
const MAX_FIX_ATTEMPTS = 3;

function log(m) {
  const line = "[" + new Date().toISOString().slice(0, 19).replace("T", " ") + "] " + m;
  console.log(line);
  fs.appendFileSync(LOG, line + "\n");
}

function run(cmd, timeout = 30000) {
  try { return execSync(cmd, { encoding: "utf8", timeout, stdio: ["ignore", "pipe", "pipe"] }).trim(); } catch (e) { return "ERR: " + (e.stderr || e.message || "").slice(0, 200); }
}

function loadEvents() { try { return JSON.parse(fs.readFileSync(EVENTS_FILE, "utf8")); } catch { return []; } }
function saveEvent(evt) {
  const events = loadEvents();
  events.push({ ...evt, ts: new Date().toISOString() });
  while (events.length > 500) events.shift();
  fs.writeFileSync(EVENTS_FILE, JSON.stringify(events, null, 2));
}

function getPM2Status(pm2Name) {
  const raw = run("pm2 jlist 2>/dev/null");
  if (!raw || raw.startsWith("ERR")) return { ok: false, status: "unknown" };
  try {
    const list = JSON.parse(raw);
    const proc = list.find(p => p.name === pm2Name);
    if (!proc) return { ok: false, status: "not_found" };
    return { ok: proc.pm2_env?.status === "online", status: proc.pm2_env?.status || "unknown" };
  } catch { return { ok: false, status: "parse_error" }; }
}

// 健康检查：200/301/302都算HTTP正常
function healthCheck() {
  const sites = [
    { name: "ai-ecom", url: "https://ai.openai2000.cn", pm2: "ai-ecom-site", optional: true },
    { name: "huizhiyunma", url: "https://www.openai2000.cn", pm2: "huizhiyunma-api" }
  ];
  const results = [];
  for (const site of sites) {
    const code = run(`curl -so /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 10 "${site.url}"`);
    const httpOk = ["200", "301", "302"].includes(code);
    const pm2 = getPM2Status(site.pm2);
    // ai-ecom-site 不在PM2里，只看HTTP
    const healthy = site.optional ? httpOk : (httpOk && pm2.ok);
    results.push({ ...site, httpOk, httpCode: code, pm2Ok: pm2.ok, pm2Status: pm2.status, healthy });
  }
  return results;
}

function diagnose(site) {
  const issues = [];
  if (!site.pm2Ok && !site.optional) {
    const logs = run(`pm2 logs ${site.pm2} --lines 20 --nostream 2>&1`, 10000);
    if (logs.includes("EADDRINUSE")) issues.push({ type: "port_conflict", detail: "端口被占用" });
    else if (logs.includes("MODULE_NOT_FOUND")) issues.push({ type: "missing_module", detail: "依赖缺失" });
    else issues.push({ type: "process_crash", detail: "进程崩溃" });
  }
  if (!site.httpOk) {
    issues.push({ type: "http_error", detail: "HTTP=" + site.httpCode });
  }
  return issues;
}

function fix(site, issue) {
  log("🔧 修复 " + site.name + " / " + issue.type);
  if (site.optional) return false; // 不自动修复可选站点
  run(`pm2 restart ${site.pm2}`);
  run("sleep 10");
  const code = run(`curl -so /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 10 "${site.url}"`);
  if (["200", "301", "302"].includes(code)) { log("✅ 修复成功: " + site.name); return true; }
  log("❌ 修复失败: " + site.name + " code=" + code);
  return false;
}

try {
  fs.mkdirSync(LOG_DIR, { recursive: true });
  const sites = healthCheck();
  let totalFixed = 0, totalFailed = 0;

  for (const site of sites) {
    if (site.healthy) { log("✅ " + site.name + " 健康 (HTTP=" + site.httpCode + " PM2=" + site.pm2Status + ")"); continue; }
    log("⚠️ " + site.name + " 异常: HTTP=" + site.httpCode + " PM2=" + site.pm2Status);
    const issues = diagnose(site);
    if (issues.length === 0) continue;
    let fixed = false;
    for (const issue of issues) { fixed = fix(site, issue); if (fixed) break; }
    saveEvent({ site: site.name, issues, result: fixed ? "fixed" : "failed" });
    if (fixed) totalFixed++; else totalFailed++;
  }

  if (totalFailed > 0) { log("⚠️ 修复完成: 成功=" + totalFixed + " 失败=" + totalFailed); process.exit(2); }
  if (totalFixed > 0) log("✅ 修复成功: " + totalFixed);
  else log("✅ 所有站点健康");
  process.exit(0);
} catch (e) { log("ERROR " + e.message); process.exit(1); }
