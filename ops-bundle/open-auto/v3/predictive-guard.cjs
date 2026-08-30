#!/usr/bin/env node
'use strict';

/**
 * Open Auto v3 - Predictive Guard
 * 预测性维护模块：资源指标采集 + 趋势预测 + 告警
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const METRICS_DIR = '/tmp/open-auto-metrics';
const HISTORY_FILE = path.join(METRICS_DIR, 'history.json');
const ALERT_FILE = path.join(METRICS_DIR, 'alerts.json');
const MAX_HISTORY = 168;

const THRESHOLDS = {
  disk: { warn: 75, crit: 85 },
  memory: { warn: 80, crit: 90 },
  cpu: { warn: 70, crit: 90 },
  load: { warn: 2.0, crit: 4.0 },
  inode: { warn: 80, crit: 90 }
};

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function collectMetrics() {
  const now = new Date().toISOString();
  const metrics = { ts: now };
  try {
    const dfOut = execSync('df -h / | tail -1', { encoding: 'utf-8' }).trim();
    const dfParts = dfOut.split(/\s+/);
    metrics.diskPercent = parseInt(dfParts[4]) || 0;
    metrics.diskUsed = dfParts[2];
    metrics.diskAvail = dfParts[3];

    const memOut = execSync("free | awk '/Mem:/ {printf \"%d %d %d\", $3, $2, $7}'", { encoding: 'utf-8' }).trim();
    const [memUsed, memTotal, memAvail] = memOut.split(/\s+/).map(Number);
    metrics.memoryPercent = Math.round((memUsed / memTotal) * 100);
    metrics.memoryUsedMB = Math.round(memUsed / 1024);
    metrics.memoryTotalMB = Math.round(memTotal / 1024);
    metrics.memoryAvailMB = Math.round(memAvail / 1024);

    const cpuOut = execSync("top -bn1 | head -5 | awk '/Cpu/ {print $2}'", { encoding: 'utf-8' }).trim();
    metrics.cpuPercent = parseFloat(cpuOut) || 0;

    const loadOut = execSync('cat /proc/loadavg', { encoding: 'utf-8' }).trim();
    const loadParts = loadOut.split(/\s+/);
    metrics.load1 = parseFloat(loadParts[0]) || 0;
    metrics.load5 = parseFloat(loadParts[1]) || 0;
    metrics.load15 = parseFloat(loadParts[2]) || 0;

    const inodeOut = execSync('df -i / | tail -1', { encoding: 'utf-8' }).trim();
    metrics.inodePercent = parseInt(inodeOut.split(/\s+/)[4]) || 0;

    metrics.processes = parseInt(execSync('ps aux | wc -l', { encoding: 'utf-8' }).trim()) || 0;
  } catch (e) {
    metrics.error = e.message;
  }
  return metrics;
}

function loadHistory() {
  try {
    if (fs.existsSync(HISTORY_FILE)) return JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf-8'));
  } catch (e) {}
  return [];
}

function saveHistory(history) {
  ensureDir(METRICS_DIR);
  if (history.length > MAX_HISTORY) history = history.slice(-MAX_HISTORY);
  fs.writeFileSync(HISTORY_FILE, JSON.stringify(history, null, 2));
}

function linearRegression(values) {
  const n = values.length;
  if (n < 2) return { slope: 0, intercept: values[0] || 0 };
  let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
  for (let i = 0; i < n; i++) {
    sumX += i; sumY += values[i];
    sumXY += i * values[i]; sumXX += i * i;
  }
  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

function predict(history, field, hoursAhead = 24) {
  const values = history.map(m => m[field]).filter(v => v != null);
  if (values.length < 3) return null;
  const { slope, intercept } = linearRegression(values);
  const predicted = slope * (values.length - 1 + hoursAhead) + intercept;
  return {
    current: values[values.length - 1],
    predicted: Math.round(predicted * 10) / 10,
    trend: slope > 0.5 ? 'rising' : slope < -0.5 ? 'falling' : 'stable',
    hoursAhead,
    confidence: values.length >= 12 ? 'medium' : 'low'
  };
}

function checkAlerts(metrics, history) {
  const alerts = [];
  for (const [metric, threshold] of Object.entries(THRESHOLDS)) {
    const value = metrics[`${metric}Percent`] || metrics[metric];
    if (value == null) continue;
    if (value >= threshold.crit) alerts.push({ level: 'critical', metric, value, threshold: threshold.crit, msg: `${metric} 当前 ${value}% 超过临界阈值 ${threshold.crit}%` });
    else if (value >= threshold.warn) alerts.push({ level: 'warning', metric, value, threshold: threshold.warn, msg: `${metric} 当前 ${value}% 超过警告阈值 ${threshold.warn}%` });
  }
  const diskPred = predict(history, 'diskPercent', 24);
  if (diskPred && diskPred.predicted >= THRESHOLDS.disk.crit && diskPred.trend === 'rising')
    alerts.push({ level: 'warning', metric: 'disk_trend', msg: `磁盘预计24h后达到 ${diskPred.predicted}%（当前 ${diskPred.current}%）` });
  const memPred = predict(history, 'memoryPercent', 12);
  if (memPred && memPred.predicted >= THRESHOLDS.memory.crit && memPred.trend === 'rising')
    alerts.push({ level: 'warning', metric: 'memory_trend', msg: `内存预计12h后达到 ${memPred.predicted}%（当前 ${memPred.current}%）` });
  return alerts;
}

function generateReport(metrics, history, alerts) {
  const lines = [];
  lines.push('📊 Open Auto v3 - 系统指标报告');
  lines.push(`时间: ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`);
  lines.push('');
  lines.push('📈 当前状态:');
  lines.push(`  磁盘: ${metrics.diskPercent}% (${metrics.diskUsed}/${metrics.diskAvail})`);
  lines.push(`  内存: ${metrics.memoryPercent}% (${metrics.memoryUsedMB}MB/${metrics.memoryTotalMB}MB)`);
  lines.push(`  CPU: ${metrics.cpuPercent}%`);
  lines.push(`  负载: ${metrics.load1} / ${metrics.load5} / ${metrics.load15}`);
  lines.push(`  Inode: ${metrics.inodePercent}%`);
  lines.push(`  进程数: ${metrics.processes}`);
  lines.push('');
  lines.push('🔮 趋势预测:');
  for (const [field, label] of [['diskPercent', '磁盘'], ['memoryPercent', '内存'], ['cpuPercent', 'CPU']]) {
    const pred = predict(history, field, 24);
    if (pred) lines.push(`  ${label}: ${pred.current}% → ${pred.predicted}% (24h) [${pred.trend}]`);
  }
  if (alerts.length > 0) {
    lines.push('');
    lines.push('⚠️ 告警:');
    for (const alert of alerts) lines.push(`  ${alert.level === 'critical' ? '🔴' : '🟡'} ${alert.msg}`);
  } else {
    lines.push('');
    lines.push('✅ 无告警');
  }
  return lines.join('\n');
}

function main() {
  const action = process.argv[2] || 'collect';
  if (action === 'collect') {
    const metrics = collectMetrics();
    const history = loadHistory();
    history.push(metrics);
    saveHistory(history);
    const alerts = checkAlerts(metrics, history);
    if (alerts.length > 0) {
      ensureDir(METRICS_DIR);
      fs.writeFileSync(ALERT_FILE, JSON.stringify(alerts, null, 2));
      console.log(`⚠️ ${alerts.length} 个告警触发`);
      for (const alert of alerts) console.log(`  [${alert.level}] ${alert.msg}`);
    } else {
      console.log('✅ 指标正常');
    }
    console.log('\n' + generateReport(metrics, history, alerts));
  } else if (action === 'report') {
    const history = loadHistory();
    if (history.length === 0) { console.log('⚠️ 无历史数据'); return; }
    const metrics = history[history.length - 1];
    console.log(generateReport(metrics, history, checkAlerts(metrics, history)));
  } else if (action === 'predict') {
    const field = process.argv[3] || 'diskPercent';
    const hours = parseInt(process.argv[4]) || 24;
    const pred = predict(loadHistory(), field, hours);
    console.log(pred ? JSON.stringify(pred, null, 2) : '⚠️ 数据不足');
  } else {
    console.log('用法: node predictive-guard.cjs [collect|report|predict]');
  }
}

if (require.main === module) main();
module.exports = { collectMetrics, predict, checkAlerts, generateReport };
