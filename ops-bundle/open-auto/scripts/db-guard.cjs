#!/usr/bin/env node
/* DB Guard: 每分钟检查文章完整性，异常自动从有效备份恢复 */
const { DatabaseSync } = require("node:sqlite");
const { execSync } = require("node:child_process");
const fs = require("fs");

const DB = "/data/disk/ai-ecom/data/site.db";
const PM2 = "/home/ubuntu/.nvm/versions/node/v22.23.0/bin/pm2";
const ENV = "PATH=/home/ubuntu/.nvm/versions/node/v22.23.0/bin:/usr/sbin:/usr/bin:/sbin:/bin";
const LOG = "/opt/ai-ecom-site/data/logs/db-guard.log";

function log(m) {
  const line = "[" + new Date().toISOString().slice(0, 19).replace("T", " ") + "] " + m;
  console.log(line);
  fs.appendFileSync(LOG, line + "\n");
}

function readStats() {
  try {
    const db = new DatabaseSync(DB);
    const posts = db.prepare("SELECT count(*) as n FROM posts").get().n;
    const seo = db.prepare("SELECT count(*) as n FROM posts WHERE slug LIKE 'seo-kw%'").get().n;
    db.close();
    return { ok: true, posts, seo };
  } catch (e) {
    return { ok: false, err: e.message };
  }
}

function latestGoodBackup() {
  const dir = "/data/disk/ai-ecom/data";
  const files = fs.readdirSync(dir).filter(f => f.startsWith("site.db.bak-") && !f.includes("shm") && !f.includes("wal") && !f.includes("broken"));
  // Sort by mtime desc, verify seo>=8
  files.sort((a, b) => fs.statSync(dir + "/" + b).mtimeMs - fs.statSync(dir + "/" + a).mtimeMs);
  for (const f of files) {
    try {
      const db = new DatabaseSync(dir + "/" + f);
      const seo = db.prepare("SELECT count(*) as n FROM posts WHERE slug LIKE 'seo-kw%'").get().n;
      db.close();
      if (seo >= 8) return dir + "/" + f;
    } catch {}
  }
  return null;
}

function backupNow() {
  const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "");
  execSync("cp " + DB + " " + DB + ".bak-" + stamp + " && chmod 644 " + DB + ".bak-" + stamp);
}

function restore(bak) {
  log("RESTORE from " + bak);
  execSync("env " + ENV + " " + PM2 + " stop ai-ecom-site");
  execSync("rm -f " + DB + " " + DB + "-wal " + DB + "-shm");
  execSync("cp " + bak + " " + DB);
  execSync("chown ubuntu:ubuntu " + DB);
  execSync("env " + ENV + " " + PM2 + " start ai-ecom-site");
  execSync("env " + ENV + " " + PM2 + " save");
}

const s = readStats();
if (!s.ok) {
  log("DB ERROR: " + s.err + " -> restoring");
  const bak = latestGoodBackup();
  if (bak) restore(bak); else log("NO GOOD BACKUP");
  process.exit(0);
}
if (s.posts < 30 || s.seo < 8) {
  log("LOW DATA posts=" + s.posts + " seo=" + s.seo + " -> restoring");
  const bak = latestGoodBackup();
  if (bak) restore(bak); else log("NO GOOD BACKUP");
  process.exit(0);
}
// Normal: backup every 10 min (check minute)
const min = new Date().getMinutes();
if (min % 10 === 0) {
  try { backupNow(); log("backup OK posts=" + s.posts + " seo=" + s.seo); } catch(e) { log("backup fail " + e.message.slice(0,60)); }
}
