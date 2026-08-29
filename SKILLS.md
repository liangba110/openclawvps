# SKILLS —— 已验证方法库（可复用流程）

## [2026-08-28][经验] mimo 接入 Codex 中转方案
- 适用场景：把只兼容 chat/completions 的模型（如小米 MiMo Token Plan）接入只认 responses 协议的 Codex
- 步骤：
  1. 确认模型 base_url 与鉴权方式（token-plan-cn.xiaomimimo.com/v1，Bearer token）
  2. 写零依赖 node 代理（/opt/mimo-proxy/proxy.mjs），监听 127.0.0.1:8787
  3. 代理把 POST /v1/responses 转成 /v1/chat/completions（消息格式转换：developer→system、tool_calls 转换）
  4. 流式事件必须完整：response.created → output_item.added → output_text.delta → output_text.done → output_item.done → response.completed（带 usage.input_tokens）
  5. Codex config.toml 配 base_url=http://127.0.0.1:8787/v1，wire_api=responses
  6. systemd 托管代理（mimo-proxy.service，Restart=always）
- 坑：wire_api 只认 responses；max_tokens 至少 8000（推理模型 reasoning 吃 token）；缺 done 事件 Codex 不显示输出
- 状态：✅ 有效
- 复用次数：1

## [2026-08-28][经验] Codex 生成文章（流式输出提取法）
- 适用场景：用 Codex（mimo）生成 SEO 文章/长文本
- 步骤：
  1. 让 Codex 直接输出正文到 stdout（不要让它写文件，写文件需额外权限且推理模型工具调用不稳）
  2. 输出重定向到日志文件
  3. 用脚本提取正文：跳过 codex 标记行/警告行/tokens used 行，按"正文起点"开始收集
  4. 流式分片需重新拼接（每段是 delta 碎片，行间有 codex 标记）
  5. 清理尾部 token 计数杂质（如 "2,233吧"）
- 坑：mimo 回复前有 reasoning 过程（codex 前缀行）；max_tokens 不够会截断；正文前有标题拆片
- 状态：✅ 有效
- 复用次数：1

## [2026-08-13][经验] 前端页面问题排查流程
- 适用场景：前端页面报错/白屏/功能异常
- 步骤：
  1. curl 验证 API/静态资源/nginx 是否正常
  2. CDP 无头浏览器（127.0.0.1:9222）复现，注入 window.__errs 捕获控制台错误
  3. 定位压缩 JS 报错行列
  4. 对比源码与备份定位回归
  5. 修复后 CDP 全页面验证
- 坑：SPA 渲染错误只验 API 200 发现不了，必须真实浏览器验证
- 状态：✅ 有效
- 复用次数：2

## [2026-08-13][经验] 统一构建流程
- 适用场景：huizhiyunma 前端构建（vite + generate）
- 步骤：`sudo bash /data/web/huizhiyunma/build.sh`（全 www-data 身份，自动校验 dist 属主）
- 坑：root 与 www-data 混写 dist 导致 EACCES
- 状态：✅ 有效
- 复用次数：3

## [2026-08-13][经验] CDP 调试脚本模式
- 适用场景：需要抓页面 API 响应/控制台错误的调试
- 步骤：/tmp/cdp_*.js 模式（PUT /json/new 开标签、注入错误收集、Network 抓 API 响应体）
- 状态：✅ 有效
- 复用次数：2

## [2026-08-13][经验] 资料包新增流程（ai-ecom store）
- 适用场景：给 ai.openai2000.cn/store 新增付费资料包
- 步骤：
  1. 仿现有模板（如 ai-job-interview 的 HTML 结构：header/section-block/h2/h3/table/prompt-box/check-list）
  2. 用 Codex 生成原创内容（2026 工具、无广告法违禁词）
  3. 脚本 INSERT ... ON CONFLICT(slug) DO UPDATE（可重复执行，自动备份 DB）
  4. 验证：DB full_content 非空、toc_json 与正文一致、store 页 + 详情页 HTTP 200、违禁词扫描
- 坑：products 表 slug 是主键无 id；store 数据源是 DB 非 materials.json；data 目录属主 aiecom 需 sudo
- 状态：✅ 有效
- 复用次数：1
