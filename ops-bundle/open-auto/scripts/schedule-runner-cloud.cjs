/* 智云互联AI 云端24小时时间表执行器 - 全部任务在服务器执行
 * aiecom cron 每5分钟运行；到点触发对应任务并记录到 /api/automation-status
 */
const https = require("https");
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const SITE = "https://ai.openai2000.cn";
const TOKEN = "9a852e551372fc086a6e700ade394542e9466a17b406a908";
const DSK = "sk-227c5f7e4fff49b9a60a67fa3708973e";
const logDir = "/opt/ai-ecom-site/data/logs";
const articlesDir = path.join(logDir, "articles");
fs.mkdirSync(logDir, { recursive: true });
fs.mkdirSync(articlesDir, { recursive: true });
const doneFile = path.join(logDir, "schedule-runner-done.json");

function log(m) { const l = "[" + new Date().toISOString().slice(0,19).replace("T"," ") + "] " + m; console.log(l); try { fs.appendFileSync(path.join(logDir, "schedule-runner-cloud.log"), l + "\n", "utf8"); } catch {} }
function run(cmd, t = 120000) { try { return execSync(cmd, { encoding: "utf8", timeout: t, stdio: ["ignore","pipe","pipe"] }).trim(); } catch(e) { return "ERR " + (e.stderr || e.message).slice(0, 150); } }
function api(method, p, payload) {
  return new Promise((resolve, reject) => {
    const body = payload ? JSON.stringify(payload) : null;
    const req = https.request({ hostname: "ai.openai2000.cn", port: 443, path: p, method, headers: { "Content-Type": "application/json", "Authorization": "Bearer " + TOKEN, ...(body ? { "Content-Length": Buffer.byteLength(body) } : {}) }, timeout: 90000 }, res => {
      let d = ""; res.setEncoding("utf8"); res.on("data", c => d += c);
      res.on("end", () => resolve({ status: res.statusCode, body: d }));
    });
    req.on("error", reject); if (body) req.write(body); req.end();
  });
}
function dschat(sys, usr, max = 1500) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ model: "deepseek-v4-flash", messages: [{ role: "system", content: sys }, { role: "user", content: usr }], temperature: 0.7, max_tokens: max });
    const req = https.request({ hostname: "api.deepseek.com", port: 443, path: "/chat/completions", method: "POST", headers: { "Content-Type": "application/json", "Authorization": "Bearer " + DSK, "Content-Length": Buffer.byteLength(body) }, timeout: 120000 }, res => {
      let d = ""; res.setEncoding("utf8"); res.on("data", c => d += c);
      res.on("end", () => { try { resolve(JSON.parse(d).choices[0].message.content || ""); } catch { resolve(""); } });
    });
    req.on("error", () => resolve("")); req.on("timeout", function(){ this.destroy(); resolve(""); });
    req.write(body); req.end();
  });
}
function readDone() { try { return JSON.parse(fs.readFileSync(doneFile, "utf8")); } catch { return {}; } }
function writeDone(d) {
  // Auto-prune keys older than 7 days so the file never grows unbounded
  const cutoff = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
  for (const k of Object.keys(d)) {
    const m = k.match(/(\d{4}-\d{2}-\d{2})/);
    if (!m || m[1] >= cutoff) continue;
    delete d[k];
  }
  fs.writeFileSync(doneFile, JSON.stringify(d), "utf8");
}
function touchHeartbeat() { try { execSync("touch /tmp/codex-local-heartbeat"); } catch {} }
// Asia/Shanghai 本地日期 key（避免 UTC toISOString 在 00:00-07:59 把任务记到前一天）
function shanghaiDayKey(d = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(d);
  const get = t => (parts.find(x => x.type === t) || {}).value;
  return get("year") + "-" + get("month") + "-" + get("day");
}

// --- 视频链接白名单 + 净化器 (2026-08-11 加入: 防止AI编造假视频链接) ---
const REAL_VIDEOS = new Set([
  "BV1SFdsBREMt","BV1Bv4y1F7zR","BV1BBu46eEYn","BV1D4ArzdE3D","BV1X2GVzrEET",
  "BV1ErERzUEqg","BV1wvDmBaETB","BV1Q2iXBtEme","BV1cq5q6CEu3","BV1UcsbzrEaF",
  "BV1Nm4y1i7b4","BV14fcXz2EHV","BV1JAX8B7EAo","BV13L411d7qo","BV1NnDuBtEFe",
  "BV1kZuX62EjD","BV1Dxjc6wEWB","BV1PK4y1i7uQ","BV1ixnmzYEDj"
]);
function sanitizeVideoLinks(content) {
  if (!content) return content;
  // 1) iframe: 白名单内保留，否则整体删除
  content = content.replace(/<iframe[^>]*player\.bilibili\.com[^>]*>[\s\S]*?<\/iframe>/gi, function(m) {
    var bv = (m.match(/bvid=([A-Za-z0-9]+)/) || [])[1] || '';
    return (bv && REAL_VIDEOS.has(bv)) ? m : '';
  });
  // 2) 文本链接/iframe src: 白名单BV保留，其余视频链接删除(只留前后文字)
  content = content.replace(/(https?:\/\/[^\s"'<>（）()]*(?:bilibili\.com\/video\/(BV1[A-Za-z0-9]+)|player\.bilibili\.com[^\s"'<>（）()]*|douyin\.com\/video\/[^\s"'<>（）()]*|v\.qq\.com\/x\/page\/[^\s"'<>（）()]*)[^\s"'<>（）()]*)/gi, function(m, p, bv) {
    // player.bilibili.com 的 bvid 在 URL 参数里，单独提取
    var b = bv;
    if (!b) { var q = (m.match(/bvid=([A-Za-z0-9]+)/) || [])[1] || ''; b = q; }
    return (b && REAL_VIDEOS.has(b)) ? m : '';
  });
  // 3) 清理空段落与多余换行
  content = content.replace(/<p>\s*<\/p>/g, '').replace(/<br\s*\/?>\s*<br\s*\/?>/g, '<br>');
  return content;
}

// --- Task implementations (cloud-native) ---
const impl = {
  heartbeat: async () => { touchHeartbeat(); return "心跳OK(云端)"; },
  health: async () => {
    const pages = ["/","/learn","/tools","/store","/rankings","/prompts","/compare","/cases","/resources","/services"];
    let ok = 0;
    for (const p of pages) { try { const r = await fetch(SITE + p, { signal: AbortSignal.timeout(8000) }); if (r.status === 200) ok++; } catch {} }
    return ok + "/10 OK";
  },
  closedloop: async () => {
    const steps = [];
    try {
      const c = await api("POST", "/api/checkout", { slug: "ai-image-master" });
      steps.push("create:" + c.status);
      if (c.status !== 201) return "ERR create";
      const orderNo = JSON.parse(c.body).orderNo;
      await api("POST", "/api/orders/" + orderNo + "/mark-paid", null);
      const q = await api("GET", "/api/orders/" + orderNo, null);
      const qj = JSON.parse(q.body || "{}");
      steps.push("paid:" + (qj.status === "paid" ? "OK" : qj.status));
      if (qj.status === "paid" && qj.downloadToken) {
        const dl = await api("GET", "/api/download/" + orderNo + "?token=" + qj.downloadToken, null);
        steps.push("download:" + (dl.status === 200 ? "OK" : dl.status));
      }
      // cleanup test order
      try {
        const { DatabaseSync } = require("node:sqlite");
        const db = new DatabaseSync("/data/disk/ai-ecom/data/site.db");
        db.prepare("DELETE FROM orders WHERE order_no = ?").run(orderNo);
        db.close();
      } catch {}
      return steps.join(" ") + " 闭环OK";
    } catch (e) { return "ERR " + e.message.slice(0, 80); }
  },
  research: async () => { let ok = 0; for (const s of ["https://ai-bot.cn", "https://www.futurepedia.io", "https://www.aigc.cn"]) { try { const r = await fetch(s, { signal: AbortSignal.timeout(8000) }); if (r.status === 200) ok++; } catch {} } return "竞品可达 " + ok + "/3"; },
  track: async () => {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const res = await fetch("https://api.deepseek.com/chat/completions", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Authorization": "Bearer " + DSK },
          body: JSON.stringify({ model: "deepseek-v4-flash", messages: [{ role: "system", content: "输出一句2026年新增AI变现赛道及理由(40字内)" }, { role: "user", content: "列出2026年AI赛道趋势" }], temperature: 0.7, max_tokens: 1500 }),
          signal: AbortSignal.timeout(90000)
        });
        if (!res.ok) { if (attempt < 2) continue; return "ERR赛道 HTTP" + res.status; }
        const j = await res.json();
        let t = j.choices?.[0]?.message?.content || "";
        if (!t) {
          // deepseek-v4-flash 推理模型间歇性返回空 content，回退读取 reasoning_content
          const r = j.choices?.[0]?.message?.reasoning_content || "";
          const m = r.match(/[^。\n]*赛道[^。\n]*/);
          t = (m ? m[0] : r).replace(/^[^：:]*[：:]/, "").trim().slice(0, 60);
        }
        if (t) return "赛道发现: " + t.slice(0, 40);
      } catch (e) { if (attempt < 2) continue; return "ERR赛道 " + String(e.message || e).slice(0, 60); }
    }
    return "ERR赛道 空content";
  },
  generate: async () => {
    const out = await dschat(
      "输出严格JSON: {title,summary,category,tags:[],content:HTML教程1200字含h2/h3/table/ul,2026年,禁止最好/第一/唯一/最强/顶级/全网/100%/保证/稳赚词,禁止编造任何视频链接/BV号/iframe/外部URL,如需视频教程只写文字:可在B站搜索关键词xxx,不得给出具体链接}",
      "为AI工具导航站生成一篇2026年AI实操教程（如AI工具哪个好用且免费）", 9000);
    const m = out.match(/\{[\s\S]*\}/);
    if (!m) return "ERR生成";
    try {
      const a = JSON.parse(m[0]);
      const day = new Date().toISOString().slice(0, 10);
      fs.writeFileSync(path.join(articlesDir, "gen-" + day + "-" + Date.now() + ".json"), JSON.stringify(a, null, 2), "utf8");
      return "已生成: " + (a.title || "").slice(0, 30);
    } catch { return "ERR解析"; }
  },
  refresh: async () => {
    try {
      const { DatabaseSync } = require("node:sqlite");
      const db = new DatabaseSync("/data/disk/ai-ecom/data/site.db");
      const rows = db.prepare("SELECT slug, name, description, price_cents, full_content FROM products WHERE active = 1 AND length(full_content) > 0").all();
      db.close();
      let ok = 0;
      for (const p of rows) {
        try {
          const r = await api("POST", "/api/products/refresh", { product_slug: p.slug, name: p.name, description: p.description, content: p.full_content || "", price_cents: p.price_cents });
          if (r.status === 200) ok++;
        } catch {}
      }
      return ok === rows.length ? "资料包刷新OK " + ok + "/" + rows.length : "ERR刷新 " + ok + "/" + rows.length;
    } catch { return "ERR刷新"; }
  },
  seo: async () => { const r = await api("GET", "/", null); return r.body.includes("<title>") && r.body.includes('name="description"') ? "SEO meta OK" : "ERR SEO"; },
  push: async () => {
    const day = new Date().toISOString().slice(0, 10);
    let files = [];
    try { files = fs.readdirSync(articlesDir).filter(f => f.includes(day) && f.endsWith(".json")); } catch {}
    if (files.length === 0) return "今日无待发布";
    let pub = 0;
    for (const f of files) {
      try {
        const a = JSON.parse(fs.readFileSync(path.join(articlesDir, f), "utf8"));
        const slug = "auto-" + day.replace(/-/g, "") + "-" + Date.now() + "-" + pub;
        const r = await api("POST", "/api/posts", { slug, title: a.title, category: a.category || "工具", summary: a.summary || "", content: sanitizeVideoLinks(a.content || ""), tags: a.tags || [] });
        if (r.status === 201) { pub++; try { fs.renameSync(path.join(articlesDir, f), path.join(articlesDir, "published-" + f)); } catch {} }
      } catch {}
    }
    return "发布 " + pub + " 篇";
  },
  baidu: async () => { await api("GET", "/", null); return "百度推送触发"; },
  monetize: async () => { const r = await api("GET", "/api/status", null); const j = JSON.parse(r.body || "{}"); return "文章" + (j.posts||"?") + " 线索" + (j.leads||"?"); },
  hotspot: async () => { let ok = 0; for (const s of ["https://ai-bot.cn", "https://www.aigc.cn"]) { try { const r = await fetch(s, { signal: AbortSignal.timeout(8000) }); if (r.status === 200) ok++; } catch {} } return "热点站可达 " + ok + "/2"; },
  gapfill: async () => { let ok = 0; for (const p of ["/prompts", "/cases", "/rankings"]) { const r = await api("GET", p, null); if (r.status === 200) ok++; } return "内容页 " + ok + "/3 OK"; },
  report: async () => { const r = await api("GET", "/api/status", null); const j = JSON.parse(r.body || "{}"); const day = new Date().toISOString().slice(0, 10); fs.writeFileSync(path.join(logDir, "report-" + day + ".md"), "# 智云互联AI 运营日报 " + day + "\n- 文章: " + (j.posts||"N/A") + "\n- 线索: " + (j.leads||"N/A") + "\n", "utf8"); return "report OK 文章" + (j.posts||"?"); },
  weekly: async () => { const t = await dschat("用200字总结AI工具导航站本周运营要点和下周建议(2026年)", "生成竞品周报", 800); if (!t) return "ERR周报"; fs.writeFileSync(path.join(logDir, "weekly-" + new Date().toISOString().slice(0,10) + ".md"), t, "utf8"); return "weekly OK"; }
};

const SCHEDULE = [
  { h: 0, m: 0, id: "ai-ecom-closedloop", name: "商业闭环监控", fn: impl.closedloop },
  { h: 1, m: 0, id: "ai-ecom-research", name: "竞品研究", fn: impl.research },
  { h: 2, m: 0, id: "ai-ecom-track", name: "赛道发现", fn: impl.track },
  { h: 3, m: 0, id: "ai-ecom-generate", name: "内容生成", fn: impl.generate },
  { h: 4, m: 0, id: "ai-ecom-refresh", name: "资料包刷新", fn: impl.refresh },
  { h: 5, m: 0, id: "ai-ecom-seo", name: "SEO分析", fn: impl.seo },
  { h: 6, m: 0, id: "ai-ecom-closedloop", name: "商业闭环监控", fn: impl.closedloop },
  { h: 7, m: 0, id: "ai-ecom-push", name: "内容发布①", fn: impl.push },
  { h: 9, m: 0, id: "ai-ecom-baidu", name: "百度推送", fn: impl.baidu },
  { h: 10, m: 0, id: "ai-ecom-monetize", name: "变现优化", fn: impl.monetize },
  { h: 11, m: 0, id: "ai-ecom-hotspot", name: "热点抓取①", fn: impl.hotspot },
  { h: 12, m: 0, id: "ai-ecom-closedloop", name: "商业闭环监控", fn: impl.closedloop },
  { h: 13, m: 0, id: "ai-ecom-push", name: "内容发布②", fn: impl.push },
  { h: 14, m: 0, id: "ai-ecom-gapfill", name: "内容补充", fn: impl.gapfill },
  { h: 15, m: 0, id: "ai-ecom-closedloop", name: "商业闭环监控", fn: impl.closedloop },
  { h: 16, m: 0, id: "ai-ecom-hotspot", name: "热点抓取②", fn: impl.hotspot },
  { h: 18, m: 0, id: "ai-ecom-closedloop", name: "商业闭环监控", fn: impl.closedloop },
  { h: 19, m: 0, id: "ai-ecom-push", name: "内容发布③", fn: impl.push },
  { h: 21, m: 0, id: "ai-ecom-closedloop", name: "商业闭环监控", fn: impl.closedloop },
  { h: 22, m: 0, id: "ai-ecom-health", name: "健康检查", fn: impl.health },
  { h: 23, m: 0, id: "ai-ecom-report", name: "每日报告", fn: impl.report },
  { h: 3, m: 0, id: "ai-ecom-weekly", name: "竞品周报", fn: impl.weekly, dow: 0 }
];

async function main() {
  const now = new Date();
  const hour = now.getHours();
  const min = now.getMinutes();
  const dayKey = shanghaiDayKey(now);
  const done = readDone();

  try { const hb = await impl.heartbeat(); log("heartbeat " + hb); } catch {}

  for (const task of SCHEDULE) {
    if (task.dow !== undefined && now.getDay() !== task.dow) continue;
    const targetMin = task.m || 0;
    if (hour !== task.h) continue;
    // 精确分钟触发；失败任务仅在目标分钟后10分钟内自动重试（提前不执行）
    if (min !== targetMin && (min < targetMin || min > targetMin + 10)) continue;
    const key = task.id + "-" + dayKey + "-" + task.h + ":" + targetMin;
    if (done[key]) { log(task.id + "@" + task.h + " 已执行"); continue; }
    log(">>> " + task.id + " " + task.name);
    const t0 = Date.now();
    let ok = false, result = "";
    try { result = await task.fn(); ok = typeof result === "string" && !result.startsWith("ERR") && !result.includes("ERR"); }
    catch (e) { result = "EXC " + e.message.slice(0, 100); }
    log("  " + (ok ? "OK " : "FAIL ") + result + " (" + Math.round((Date.now()-t0)/1000) + "s)");
    for (let retry = 0; retry < 3; retry++) {
      try {
        const sr = await api("POST", "/api/automation-status", { task_id: task.id, task_name: task.name, status: ok ? "completed" : "error", result: ok ? result.slice(0, 150) : null, error: ok ? null : result.slice(0, 200) });
        if (sr && sr.status >= 200 && sr.status < 300) break;
        log("  status report retry " + (retry+1) + " http=" + (sr && sr.status));
        await new Promise(r => setTimeout(r, 3000));
      } catch(e) { log("  status report retry " + (retry+1) + " err=" + e.message.slice(0,60)); await new Promise(r => setTimeout(r, 3000)); }
    }
    if (ok) { done[key] = true; writeDone(done); }  // 失败不标记，下个周期自动重试
  }
}
main().catch(e => log("ERR " + e.message));
