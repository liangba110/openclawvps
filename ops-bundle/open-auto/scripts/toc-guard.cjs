#!/usr/bin/env node
/*
 * TOC Guard: store 产品 toc_json L2 完整性巡检 + 自动修复
 *
 * 背景: store 页产品卡片「资料包含」预览只取 toc_json 中 level===2 的条目。
 *       曾发生 ai-job-interview 的 toc_json 全是 level:3、无 level:2,
 *       导致卡片版式异常。本脚本作为兜底巡检, 防止内容模板变化后复发。
 *
 * 巡检规则（每个产品）:
 *   - h2  = full_content 中完整 <h2>...</h2> 开闭配对数（与 extractTOC 可提取量一致；
 *           内容里未闭合的 <h2> 无法被 TOC 提取，不计为真实章节标题，避免反复误修）
 *   - ct  = full_content 中 <div class="chapter-title">...</div> 开闭配对个数
 *   - L2  = toc_json 中 level===2 条目数
 *   异常判定: (h2>0 且 L2!==h2) 或 (ct>0 且 L2!==ct) 或 (L2===0 且 (h2>0 或 ct>0))
 *
 * 异常时自动重建 toc_json（与 app/api/products/refresh/route.ts 的 extractTOC
 * 同源: h2/h3 + chapter-title div; 文本去标签、<80 字符; L2 过滤 20xx 年份标题）。
 * 注意: 数字开头过滤仅应用于 chapter-title div（排除 "2026 职业技能进阶" 等页级
 * 标题）；h2 不做数字过滤，兼容 "一、核心概念" 与 "01AI写作..." 等既有模板——
 * 否则对中文数字模板重建后 L2=0，会反复误报 FIXED 且破坏 store 卡片预览。
 *
 * 退出码: 0 = 全部正常(输出 OK)  2 = 有修复(输出 FIXED)  1 = 脚本失败
 */
const { DatabaseSync } = require("node:sqlite");
const fs = require("fs");
const path = require("path");

const DB = process.env.TOC_GUARD_DB || "/opt/ai-ecom-site/data/site.db";
const LOG = process.env.TOC_GUARD_LOG || "/opt/ai-ecom-site/data/logs/toc-guard.log";

// 与 route.ts extractTOC 保持同源（结构一致，仅数字过滤范围限定为 chapter-title div）
function extractTOC(html) {
  const headings = [];
  // 单遍扫描保持文档顺序: h2/h3 + <div class="chapter-title">(视为 L2)
  const regex = /<h([23])[^>]*>([\s\S]*?)<\/h\1>|<div class="chapter-title[^"]*">([\s\S]*?)<\/div>/gi;
  let match;
  while ((match = regex.exec(html)) !== null) {
    const isDiv = match[1] === undefined;
    const level = isDiv ? 2 : parseInt(match[1], 10);
    const raw = isDiv ? match[3] : match[2];
    const text = raw.replace(/<[^>]+>/g, "").trim();
    if (!text || text.length >= 200) continue;
    // 20xx 年份标题一律不作为 L2（h2 与 chapter-title 都过滤）
    if (level === 2 && /^20\d\d/.test(text)) continue;
    // chapter-title div 还须以章节数字开头（过滤 "2026 职业技能进阶" 等页级标题）
    if (isDiv && level === 2 && !/^[1-9]/.test(text)) continue;
    headings.push({ level, text });
  }
  return headings;
}

function log(m) {
  const line = "[" + new Date().toISOString().slice(0, 19).replace("T", " ") + "] " + m;
  console.log(line);
  fs.appendFileSync(LOG, line + "\n");
}

let fixed = 0;
try {
  fs.mkdirSync(path.dirname(LOG), { recursive: true });
  const db = new DatabaseSync(DB);
  db.exec("PRAGMA busy_timeout = 5000");
  const rows = db.prepare("SELECT slug, full_content, toc_json FROM products").all();
  // 统计完整开闭配对，保证与 extractTOC 的可提取数量一致（防止未闭合标签导致永远 FIXED）
  const h2Re = /<h2[^>]*>[\s\S]*?<\/h2>/gi;
  const ctRe = /<div class="chapter-title[^"]*">[\s\S]*?<\/div>/gi;

  for (const row of rows) {
    const slug = row.slug;
    const content = row.full_content || "";
    let toc = [];
    try {
      toc = JSON.parse(row.toc_json || "[]");
    } catch {
      toc = [];
    }
    if (!Array.isArray(toc)) toc = [];
    const l2 = toc.filter((t) => t && t.level === 2).length;
    const h2 = (content.match(h2Re) || []).length;
    const ct = (content.match(ctRe) || []).length;

    const abnormal =
      (h2 > 0 && l2 !== h2) ||
      (ct > 0 && l2 !== ct) ||
      (l2 === 0 && (h2 > 0 || ct > 0));

    if (!abnormal) {
      log("OK " + slug + " L2=" + l2 + " h2=" + h2 + " chapter-title=" + ct);
      continue;
    }

    const rebuilt = extractTOC(content);
    const rebuiltL2 = rebuilt.filter((t) => t.level === 2).length;
    // 兜底：重建后 L2 仍不足原始 h2 数，说明有 h2 被过滤，放宽过滤重试
    let finalToc = rebuilt;
    let finalL2 = rebuiltL2;
    if (rebuiltL2 < h2 && h2 > 0) {
      const fallbackRegex = /<h([23])[^>]*>([\s\S]*?)<\/h\1>/gi;
      const fallback = [];
      let fm;
      while ((fm = fallbackRegex.exec(content)) !== null) {
        const lvl = parseInt(fm[1], 10);
        const txt = fm[2].replace(/<[^>]+>/g, '').trim();
        if (txt && txt.length < 500) fallback.push({ level: lvl, text: txt });
      }
      const fbL2 = fallback.filter(t => t.level === 2).length;
      if (fbL2 >= h2) {
        finalToc = fallback;
        finalL2 = fbL2;
      }
    }
    db.prepare("UPDATE products SET toc_json = ? WHERE slug = ?").run(
      JSON.stringify(finalToc),
      slug
    );
    log(
      "FIXED " + slug +
        " L2=" + l2 + " h2=" + h2 + " chapter-title=" + ct +
        " -> rebuilt L2=" + finalL2
    );
    fixed++;
  }
  db.close();

  if (fixed > 0) {
    log("FIXED total=" + fixed);
    console.log("FIXED");
    process.exit(2);
  }
  log("OK products=" + rows.length);
  console.log("OK");
  process.exit(0);
} catch (e) {
  const msg = (e && e.message) || String(e);
  try {
    log("ERROR " + msg);
  } catch {}
  console.error("ERROR " + msg);
  process.exit(1);
}
