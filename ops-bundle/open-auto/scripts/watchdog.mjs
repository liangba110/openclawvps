#!/usr/bin/env node
/**
 * 云端 Watchdog — 监控本地Codex心跳 + 自动故障切换
 * 运行在: 82.157.202.24 (OpenClaw定时调度)
 * 
 * 逻辑:
 *   本地Codex每5分钟SSH touch /tmp/codex-local-heartbeat
 *   本脚本每分钟检查心跳文件时间
 *   超过10分钟无心跳 → 进入FALLBACK模式，独立执行每日任务
 *   心跳恢复 → 退出FALLBACK，交还控制权
 */

import { appendFileSync, existsSync, statSync, writeFileSync, mkdirSync, renameSync } from 'node:fs';
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import path from 'node:path';

// ESM 下无全局 require，用 createRequire 保持 readState 里 require('fs') 写法兼容可用
const require = createRequire(import.meta.url);

const HEARTBEAT_FILE = '/tmp/codex-local-heartbeat';
const STALE_THRESHOLD_MS = 10 * 60 * 1000; // 10分钟无心跳=判定离线
const LOG_FILE = '/opt/ai-ecom-site/data/logs/watchdog.log';
const STATE_FILE = '/opt/ai-ecom-site/data/logs/watchdog-state.json';
const SITE_URL = 'https://ai.openai2000.cn';
const DEEPSEEK_KEY = process.env.DEEPSEEK_API_KEY || '';
const AUTO_TOKEN = process.env.AUTOMATION_TOKEN || '';

mkdirSync(path.dirname(LOG_FILE), { recursive: true });

function log(msg) {
  const ts = new Date().toISOString().slice(0, 19).replace('T', ' ');
  const line = `[${ts}] ${msg}`;
  console.log(line);
  // 日志写失败不能反噬主流程：降级到 stderr（会进 watchdog-cron.log），绝不 throw
  try {
    appendFileSync(LOG_FILE, line + '\n');
  } catch (e) {
    console.error(`[${ts}] WATCHDOG LOG WRITE FAILED: ${e.message?.slice(0, 120)}`);
  }
}

function readState() {
  try { return JSON.parse(existsSync(STATE_FILE) ? require('fs').readFileSync(STATE_FILE, 'utf8') : '{}'); }
  catch { return {}; }
}

function writeState(state) {
  // 原子写：先写同目录 .tmp 再 rename，避免并发/中断导致 JSON 半截损坏；
  // 目录缺失时递归创建；失败只记日志不 throw，防止状态写失败升级成 CRASH
  try {
    mkdirSync(path.dirname(STATE_FILE), { recursive: true });
    const tmp = STATE_FILE + '.tmp';
    writeFileSync(tmp, JSON.stringify({ ...state, updated: new Date().toISOString() }, null, 2));
    renameSync(tmp, STATE_FILE);
  } catch (e) {
    log('STATE WRITE ERROR: ' + (e.message || e).slice(0, 120));
  }
}

function isLocalAlive() {
  try {
    if (!existsSync(HEARTBEAT_FILE)) return false;
    const age = Date.now() - statSync(HEARTBEAT_FILE).mtimeMs;
    return age < STALE_THRESHOLD_MS;
  } catch (e) {
    // existsSync/statSync 之间存在极小竞态（文件被删/权限变化），一律按离线处理
    return false;
  }
}

async function healthCheck() {
  const pages = ['/', '/learn', '/store', '/tools', '/rankings'];
  const results = [];
  for (const p of pages) {
    try {
      const res = await fetch(SITE_URL + p, { signal: AbortSignal.timeout(8000) });
      results.push(p + ':' + res.status);
    } catch (e) {
      results.push(p + ':DOWN');
    }
  }
  return results;
}

async function generateAndPublish() {
  log('FALLBACK: Generating content via DeepSeek...');
  try {
    const res = await fetch('https://api.deepseek.com/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + DEEPSEEK_KEY },
      body: JSON.stringify({
        model: 'deepseek-v4-flash',
        messages: [
          { role: 'system', content: '输出JSON: {title,summary,category,tags,content:HTML教程800字含表格+步骤,2026年}' },
          { role: 'user', content: '为AI工具导航站生成一篇2026年AI实操教程。禁止最好/第一等广告词。' }
        ],
        temperature: 0.7, max_tokens: 4096
      })
    });
    const data = await res.json();
    const text = data.choices[0].message.content;
    const m = text.match(/\{[\s\S]*\}/);
    if (!m) { log('FALLBACK: Failed to parse JSON'); return; }

    const article = JSON.parse(m[0]);
    const pubRes = await fetch(SITE_URL + '/api/posts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + AUTO_TOKEN },
      body: JSON.stringify({ ...article, source: 'watchdog-fallback' })
    });
    
    if (pubRes.ok) {
      log('FALLBACK: Published: ' + article.title);
      // Checkpoint
      // site.db 属主是 aiecom，ubuntu 打开后 checkpoint 会报 readonly，必须以 aiecom 身份执行
      execSync("sudo -n -u aiecom /home/aiecom/.nvm/versions/node/v22.23.2/bin/node -e \"const{DatabaseSync}=require('node:sqlite');const db=new DatabaseSync('/data/disk/ai-ecom/data/site.db');db.exec('PRAGMA wal_checkpoint(TRUNCATE)')\"", { timeout: 30000 });
    } else {
      log('FALLBACK: Publish failed ' + pubRes.status);
    }
  } catch (e) {
    log('FALLBACK: Error: ' + e.message?.slice(0, 100));
  }
}

async function main() {
  const state = readState();
  const localAlive = isLocalAlive();

  if (localAlive) {
    // Local Codex is running → normal mode
    if (state.mode === 'fallback') {
      log('RECOVERY: Local Codex is back! Exiting fallback mode.');
      writeState({ mode: 'normal', lastFallback: state.lastFallback });
    }
    // Just do health check
    const results = await healthCheck();
    const fails = results.filter(r => r.includes('DOWN') || !r.includes('200'));
    if (fails.length > 0) {
      log('HEALTH WARNING: ' + fails.join(', '));
      // Auto-restart PM2
      try {
        execSync('env PATH="/home/ubuntu/.nvm/versions/node/v22.23.0/bin:/usr/sbin:/usr/bin:/sbin:/bin" /home/ubuntu/.nvm/versions/node/v22.23.0/bin/pm2 restart ai-ecom-site', { timeout: 30000 });
        log('Auto-restarted PM2');
      } catch (e) {
        // 重启失败不能升级成 watchdog 自身 CRASH，记 WARNING 即可
        log('HEALTH WARNING: PM2 restart failed: ' + (e.message || e).slice(0, 120));
      }
    }
    writeState({ ...state, mode: 'normal', lastCheck: new Date().toISOString(), health: results.join(', ') });
  } else {
    // Local Codex is DOWN → fallback mode
    if (state.mode !== 'fallback') {
      log('ALERT: Local Codex offline! Entering FALLBACK mode.');
    }
    
    // Health check first
    const results = await healthCheck();
    log('FALLBACK health: ' + results.join(', '));
    
    // Generate and publish content to keep site alive
    const now = new Date();
    const hour = now.getUTCHours();
    // Publish at 08:05 and 18:00 CST (00:05 and 10:00 UTC)
    if ((hour === 0 && now.getUTCMinutes() >= 5 && now.getUTCMinutes() < 10) ||
        (hour === 10 && now.getUTCMinutes() < 5)) {
      await generateAndPublish();
    }
    
    writeState({ mode: 'fallback', lastFallback: new Date().toISOString(), health: results.join(', ') });
  }
}

main().catch(e => log('CRASH: ' + e.message));
