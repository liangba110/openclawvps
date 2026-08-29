# 智云互联AI 项目常驻记忆（每次对话自动加载）

## 我是谁 / 用户是谁
- 用户：技术型老板，专注"智云互联AI"站点全自动运营
- 站点：https://ai.openai2000.cn（AI工具导航+教程+专题+资料包变现）
- 服务器：腾讯云 82.157.202.24，Ubuntu，aiecom用户

## 当前项目状态（2026-08-11）
- 9大赛道AI工具导航站 + AI专题栏目
- 40篇文章（含SEO长尾词），全部Markdown格式完整内容
- 4个付费资料包（¥29.9/39.9/99），内容7-12KB
- 15个本地Codex + 15个云端自动化任务（互监控）
- 百度统计+百度推送已配置
- 自建analytics数据面板（/admin）

## AI专题栏目（2026-08-11 新增）
- 专题列表：/topics
- 21款AI工具：13款国内（DeepSeek/豆包/通义/文心/Kimi/智谱/讯飞/元宝/即梦/可灵/海螺/天工/纳米AI）+ 8款国外（ChatGPT/Claude/Gemini/Midjourney/Sora/Copilot/SD/Perplexity）
- 每个工具：下载安装页 + 3篇新闻页 + 3篇教程页
- 数据文件：data/ai-topics.json（21款，含news_articles和tutorials字段）
- 页面结构：
  - /topics（列表）
  - /topics/[slug]（工具详情：下载/安装/教程/动态）
  - /topics/[slug]/news（新闻列表）
  - /topics/[slug]/news/[newsSlug]（新闻详情）
  - /topics/[slug]/tutorials（教程列表）
  - /topics/[slug]/tutorials/[tutorialSlug]（教程详情）
- 198个静态页面已生成
- 新闻/教程内容正在DeepSeek批量生成（/tmp/gencontent2.js，服务器后台运行）

## 每日任务时间表（北京时间）
01竞品研究 | 02赛道发现 | 03教程生成 | 04资料包刷新 | 05 SEO分析
07:30发布①(2篇) | 09百度推送 | 10变现优化 | 11热点① | 13:30发布②(1篇)
14内容补充 | 16热点② | 19:30发布③(2篇) | 19/22健康 | 23日报 | 周日03周报
SEO发布策略：每天5篇，分3批(07:30/13:30/19:30)，每批≤2篇

## 关键规则（必须遵守）
1. 每次代码修改后全面检测：14页面200 + checkout API 201 + 中文无乱码 + API端点
2. 禁止服务器npm run build（3.6GB RAM必OOM），只本地Windows构建
3. 禁止用\uXXXX转义写中文（会乱码），用真实中文
4. 数据库加列必须同步ALTER TABLE（CREATE TABLE IF NOT EXISTS不改已有表）
5. 部署tar必须排除DB：--exclude=data/site.db --exclude=data/*.db-* --exclude=.next/standalone/data/site.db
6. 内容禁用广告词（最好/第一/唯一/100%/稳赚/必涨），年份统一2026
7. 绝不触碰其他站点（dazi.openai2000.cn/openai2000.cn/aiweb）
8. 文章内容为Markdown格式，渲染用lib/markdown.ts转换器
9. 关键脚本部署后必须验证：publish-daily.mjs(4728B)/fallback-orchestrator/watchdog/auto-ops/consume-daily/push-all-to-baidu

## 已修复问题记录
- publish-daily.mjs被本地损坏版覆盖（4639B→4728B已修复，本地+服务器双目录）
- 24篇短文章（<1KB）已重新生成为完整Markdown教程（2-3.8KB）
- 文章Markdown渲染已修复（lib/markdown.ts转换器）
- OpenClaw模型配置：仅DeepSeek（flash默认+pro备用），qwen已删除
- OpenClaw主agent记忆已建立（AGENT.md）

## 生产路径（重要）
- 真正生产环境：/data/disk/ai-ecom（PM2进程CWD）
- 源码/配置：/opt/ai-ecom-site
- 生产DB：/data/disk/ai-ecom/data/site.db
- 备份：site.db.bak-20260810-FULLCONTENT

## 模型配置
- 仅DeepSeek：deepseek-v4-flash（默认）+ deepseek-v4-pro
- API key: sk-REDACTED_WITH_SECRET

## 用户沟通偏好
- 非紧急走"AI先行修复+事后告知"
- 每次改动要一次性全面完成，不留尾巴
- 内容必须图文并茂、有实际价值
- 全自动24小时运营网站，任一端离线另一端接管
- 所有修复和任务状态要同步给OpenClaw（防丢记忆）
