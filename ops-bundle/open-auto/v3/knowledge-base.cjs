#!/usr/bin/env node
/*
 * 知识库：故障自动归档为案例，相似故障自动匹配历史方案，LLM生成运维手册
 * 每天运行一次，或在 heal-orchestrator 修复后调用
 */
const { execSync } = require("node:child_process");
const fs = require("fs");
const path = require("path");
const https = require("https");

const LOG_DIR = "/opt/ai-ecom-site/data/logs";
const LOG = path.join(LOG_DIR, "knowledge-base.log");
const KB_DIR = path.join(LOG_DIR, "knowledge-base");
const CASES_FILE = path.join(KB_DIR, "cases.json");
const MANUAL_FILE = path.join(KB_DIR, "ops-manual.md");
const DEEPSEEK_KEY = process.env.DEEPSEEK_KEY || "";

function log(m) {
  const line = "[" + new Date().toISOString().slice(0, 19).replace("T", " ") + "] " + m;
  console.log(line);
  fs.appendFileSync(LOG, line + "\n");
}

function run(cmd, timeout = 10000) {
  try { return execSync(cmd, { encoding: "utf8", timeout }).trim(); } catch { return ""; }
}

// 加载历史案例
function loadCases() {
  try { return JSON.parse(fs.readFileSync(CASES_FILE, "utf8")); } catch { return []; }
}

function saveCases(cases) {
  fs.writeFileSync(CASES_FILE, JSON.stringify(cases, null, 2));
}

// 从 heal-events 收集新故障
function collectNewEvents() {
  const eventsFile = path.join(LOG_DIR, "heal-events.json");
  try {
    const events = JSON.parse(fs.readFileSync(eventsFile, "utf8"));
    // 只取最近24小时的事件
    const cutoff = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
    return events.filter(e => e.ts > cutoff && e.result);
  } catch { return []; }
}

// 从日志收集错误模式
function collectErrorPatterns() {
  const patterns = [];
  const logFiles = [
    { file: path.join(LOG_DIR, "db-guard.log"), name: "数据库守护" },
    { file: path.join(LOG_DIR, "predictive-guard.log"), name: "预测维护" },
    { file: path.join(LOG_DIR, "security-guard.log"), name: "安全防护" },
    { file: path.join(LOG_DIR, "heal-orchestrator.log"), name: "自愈编排" }
  ];
  const cutoff = new Date(Date.now() - 24 * 3600 * 1000).toISOString().slice(0, 19).replace("T", " ");

  for (const lf of logFiles) {
    if (!fs.existsSync(lf.file)) continue;
    const lines = run(`tail -200 "${lf.file}"`, 5000);
    for (const line of lines.split("\n")) {
      if (line.includes("ERROR") || line.includes("RESTORE") || line.includes("⚠️") || line.includes("❌")) {
        const ts = (line.match(/\[(.+?)\]/) || [])[1] || "";
        if (ts >= cutoff) {
          patterns.push({ source: lf.name, line: line.slice(0, 300), ts });
        }
      }
    }
  }
  return patterns;
}

// 相似度匹配（简单关键词匹配）
function findSimilarCases(newCase, existingCases) {
  const keywords = newCase.description.split(/[\s,，。；\n]+/).filter(w => w.length > 1);
  const matches = [];
  for (const c of existingCases) {
    let score = 0;
    for (const kw of keywords) {
      if (c.description.includes(kw)) score++;
    }
    if (score > 0) matches.push({ ...c, score });
  }
  matches.sort((a, b) => b.score - a.score);
  return matches.slice(0, 3);
}

// LLM 生成运维手册章节
function llmGenerate(content) {
  return new Promise((resolve) => {
    const body = JSON.stringify({
      model: "deepseek-v4-flash",
      messages: [
        { role: "system", content: "你是运维专家。根据以下故障案例，生成简洁的中文运维手册章节。格式：### 故障现象\n### 原因分析\n### 处理步骤\n### 预防措施。每部分2-3句话，简洁实用。" },
        { role: "user", content }
      ],
      temperature: 0.3,
      max_tokens: 1500
    });
    const req = https.request({
      hostname: "api.deepseek.com", port: 443, path: "/chat/completions", method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + DEEPSEEK_KEY, "Content-Length": Buffer.byteLength(body) },
      timeout: 60000
    }, res => {
      let d = ""; res.setEncoding("utf8");
      res.on("data", c => d += c);
      res.on("end", () => {
        try { resolve(JSON.parse(d).choices[0].message.content || ""); } catch { resolve(""); }
      });
    });
    req.on("error", () => resolve(""));
    req.on("timeout", function() { this.destroy(); resolve(""); });
    req.write(body);
    req.end();
  });
}

// 生成运维手册
async function generateManual(cases) {
  if (cases.length === 0) return;
  log("生成运维手册，共 " + cases.length + " 个案例...");

  let manual = "# 运维手册（自动生成）\n\n";
  manual += "> 生成时间: " + new Date().toISOString().slice(0, 19).replace("T", " ") + "\n";
  manual += "> 案例数量: " + cases.length + "\n\n";

  // 按类型分组
  const groups = {};
  for (const c of cases) {
    const type = c.type || "其他";
    if (!groups[type]) groups[type] = [];
    groups[type].push(c);
  }

  for (const [type, items] of Object.entries(groups)) {
    manual += "## " + type + "\n\n";
    // 最多取最近5个同类案例生成手册
    for (const item of items.slice(-5)) {
      const section = await llmGenerate(
        "故障类型: " + item.type + "\n" +
        "描述: " + item.description + "\n" +
        "解决方案: " + (item.fix || "未知") + "\n" +
        "结果: " + (item.result || "未知")
      );
      if (section) manual += section + "\n\n";
    }
  }

  fs.writeFileSync(MANUAL_FILE, manual);
  log("运维手册已更新: " + MANUAL_FILE);
}

// 主流程
(async () => {
  try {
    fs.mkdirSync(KB_DIR, { recursive: true });
    const cases = loadCases();

    // 1. 收集新故障事件
    const events = collectNewEvents();
    log("新事件: " + events.length + " 条");

    for (const evt of events) {
      // 检查是否已归档（避免重复）
      const exists = cases.some(c => c.ts === evt.ts && c.site === evt.site);
      if (exists) continue;

      const newCase = {
        id: cases.length + 1,
        ts: evt.ts,
        site: evt.site,
        type: evt.issues.map(i => i.type).join(","),
        description: evt.issues.map(i => i.detail).join("; "),
        fix: evt.result === "fixed" ? "自动修复成功" : "修复失败",
        result: evt.result,
        attempts: evt.attempts
      };

      // 查找相似历史案例
      const similar = findSimilarCases(newCase, cases);
      if (similar.length > 0) {
        newCase.similarTo = similar[0].id;
        log("相似案例: #" + similar[0].id + " (相似度" + similar[0].score + ")");
      }

      cases.push(newCase);
      log("归档案例 #" + newCase.id + ": " + newCase.site + " / " + newCase.type);
    }

    // 2. 收集错误模式
    const patterns = collectErrorPatterns();
    log("错误模式: " + patterns.length + " 条");

    // 保存案例
    saveCases(cases);

    // 3. 每天生成一次运维手册（检查是否今天已生成）
    const today = new Date().toISOString().slice(0, 10);
    const manualDate = (() => {
      try { return fs.readFileSync(MANUAL_FILE, "utf8").match(/生成时间: (\d{4}-\d{2}-\d{2})/)?.[1]; } catch { return ""; }
    })();

    if (manualDate !== today && cases.length > 0) {
      await generateManual(cases);
    }

    log("OK 案例总数=" + cases.length + " 新增=" + events.length);
    process.exit(0);
  } catch (e) {
    log("ERROR " + e.message);
    process.exit(1);
  }
})();
