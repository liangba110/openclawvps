#!/usr/bin/env node
/* 预测性维护：采集系统指标 → SQLite → 线性回归趋势分析 → 提前预警 */
const { execSync } = require("node:child_process");
const fs = require("fs");
const path = require("path");

const LOG_DIR = "/opt/ai-ecom-site/data/logs";
const LOG = path.join(LOG_DIR, "predictive-guard.log");
const METRICS_DB = path.join(LOG_DIR, "metrics.db");
const ALERT_FILE = path.join(LOG_DIR, "predictive-alerts.json");

const THRESHOLDS = { cpu: 90, memory: 85, disk: 75, responseMs: 5000 };
const PREDICT_HOURS = 6;

function log(m) {
  const line = "[" + new Date().toISOString().slice(0, 19).replace("T", " ") + "] " + m;
  console.log(line);
  fs.appendFileSync(LOG, line + "\n");
}

function run(cmd) {
  try { return execSync(cmd, { encoding: "utf8", timeout: 10000 }).trim(); } catch { return ""; }
}

function collectMetrics() {
  const cpu = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'");
  const memRaw = run("free | grep Mem");
  const memParts = memRaw.split(/\s+/);
  const memTotal = parseInt(memParts[1]) || 1;
  const memUsed = parseInt(memParts[2]) || 0;
  const memPct = Math.round(memUsed / memTotal * 100);
  const diskRaw = run("df / | tail -1");
  const diskPct = parseInt(diskRaw.split(/\s+/)[4]) || 0;
  const diskAvail = diskRaw.split(/\s+/)[3] || "0";
  let respMs = -1;
  try {
    const t0 = Date.now();
    execSync("curl -so /dev/null -w '%{http_code}' http://127.0.0.1:3000", { timeout: 10000 });
    respMs = Date.now() - t0;
  } catch { respMs = -1; }

  return {
    ts: Math.floor(Date.now() / 1000),
    cpu: parseFloat(cpu) || 0,
    memPct, memUsedMb: Math.round(memUsed / 1024),
    diskPct, diskAvailGb: Math.round(parseInt(diskAvail) / 1024 / 1024 * 10) / 10,
    respMs
  };
}

function initDb() {
  const { DatabaseSync } = require("node:sqlite");
  const db = new DatabaseSync(METRICS_DB);
  db.exec("PRAGMA journal_mode=WAL");
  db.exec(`CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    cpu REAL, memPct INTEGER, memUsedMb INTEGER,
    diskPct INTEGER, diskAvailGb REAL, respMs INTEGER
  )`);
  db.exec("CREATE INDEX IF NOT EXISTS idx_ts ON metrics(ts)");
  return db;
}

function storeMetric(db, m) {
  db.prepare("INSERT INTO metrics (ts,cpu,memPct,memUsedMb,diskPct,diskAvailGb,respMs) VALUES (?,?,?,?,?,?,?)")
    .run(m.ts, m.cpu, m.memPct, m.memUsedMb, m.diskPct, m.diskAvailGb, m.respMs);
}

function pruneOld(db) {
  const cutoff = Math.floor(Date.now() / 1000) - 7 * 86400;
  db.prepare("DELETE FROM metrics WHERE ts < ?").run(cutoff);
}

function linearSlope(values) {
  const n = values.length;
  if (n < 3) return 0;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
  for (let i = 0; i < n; i++) {
    sumX += i; sumY += values[i];
    sumXY += i * values[i]; sumX2 += i * i;
  }
  const denom = n * sumX2 - sumX * sumX;
  return denom === 0 ? 0 : (n * sumXY - sumX * sumY) / denom;
}

function predict(values, futurePoints) {
  const slope = linearSlope(values);
  return values[values.length - 1] + slope * futurePoints;
}

function analyze(db) {
  const alerts = [];
  const now = Math.floor(Date.now() / 1000);
  const since = now - 3 * 3600;
  const rows = db.prepare("SELECT cpu,memPct,diskPct,respMs FROM metrics WHERE ts > ? ORDER BY ts").all(since);
  if (rows.length < 5) { log("数据不足，跳过分析"); return alerts; }

  const cpus = rows.map(r => r.cpu);
  const mems = rows.map(r => r.memPct);
  const disks = rows.map(r => r.diskPct);
  const resps = rows.map(r => r.respMs).filter(r => r > 0);
  const futurePoints = PREDICT_HOURS * 60;

  const cpuPred = predict(cpus, futurePoints);
  const memPred = predict(mems, futurePoints);
  const diskPred = predict(disks, futurePoints);

  if (cpuPred > THRESHOLDS.cpu) alerts.push({ type: "cpu", current: cpus[cpus.length - 1].toFixed(1), predicted: cpuPred.toFixed(1), hours: PREDICT_HOURS, severity: "high" });
  if (memPred > THRESHOLDS.memory) alerts.push({ type: "memory", current: mems[mems.length - 1], predicted: Math.round(memPred), hours: PREDICT_HOURS, severity: "high" });
  if (diskPred > THRESHOLDS.disk) alerts.push({ type: "disk", current: disks[disks.length - 1], predicted: Math.round(diskPred), hours: PREDICT_HOURS, severity: "medium" });

  if (resps.length >= 5) {
    const respPred = predict(resps, 30);
    if (respPred > THRESHOLDS.responseMs) alerts.push({ type: "response", current: resps[resps.length - 1], predicted: Math.round(respPred), minutes: 30, severity: "high" });
  }

  const latest = rows[rows.length - 1];
  if (latest.cpu > THRESHOLDS.cpu) alerts.push({ type: "cpu", current: latest.cpu.toFixed(1), threshold: THRESHOLDS.cpu, severity: "critical" });
  if (latest.memPct > THRESHOLDS.memory) alerts.push({ type: "memory", current: latest.memPct, threshold: THRESHOLDS.memory, severity: "critical" });
  if (latest.diskPct > THRESHOLDS.disk) alerts.push({ type: "disk", current: latest.diskPct, threshold: THRESHOLDS.disk, severity: "critical" });

  return alerts;
}

function autoCleanupDisk() {
  log("磁盘预警，执行自动清理...");
  run("find /opt/ai-ecom-site/data/logs -name '*.log' -mtime +7 -delete");
  const backupDir = "/data/disk/backups";
  if (fs.existsSync(backupDir)) {
    const files = fs.readdirSync(backupDir).filter(f => f.endsWith(".tar.gz") || f.includes("site.db.bak-"));
    files.sort((a, b) => fs.statSync(backupDir + "/" + b).mtimeMs - fs.statSync(backupDir + "/" + a).mtimeMs);
    for (let i = 5; i < files.length; i++) {
      try { fs.unlinkSync(backupDir + "/" + files[i]); log("清理旧备份: " + files[i]); } catch {}
    }
  }
  run("journalctl --vacuum-time=3d 2>/dev/null");
  log("自动清理完成");
}

function saveAlerts(alerts) {
  if (alerts.length === 0) return;
  const existing = (() => { try { return JSON.parse(fs.readFileSync(ALERT_FILE, "utf8")); } catch { return []; } })();
  existing.push(...alerts.map(a => ({ ...a, ts: new Date().toISOString() })));
  while (existing.length > 100) existing.shift();
  fs.writeFileSync(ALERT_FILE, JSON.stringify(existing, null, 2));
}

try {
  fs.mkdirSync(LOG_DIR, { recursive: true });
  const db = initDb();
  const metrics = collectMetrics();
  storeMetric(db, metrics);
  pruneOld(db);
  const alerts = analyze(db);
  db.close();

  if (alerts.length > 0) {
    log("⚠️ 预警 " + alerts.length + " 条: " + JSON.stringify(alerts));
    saveAlerts(alerts);
    if (alerts.some(a => a.type === "disk")) autoCleanupDisk();
    process.exit(2);
  }
  log("OK cpu=" + metrics.cpu.toFixed(1) + "% mem=" + metrics.memPct + "% disk=" + metrics.diskPct + "% resp=" + metrics.respMs + "ms");
  process.exit(0);
} catch (e) {
  log("ERROR " + e.message);
  process.exit(1);
}
