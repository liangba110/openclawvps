# ERRORS —— 错误与正确做法（每次回答前扫一遍）

## 错误日志（新的在前）

### [2026-08-28] 错误：mimo 流式输出 content 为空
- 场景：Codex 接 mimo-v2.5-pro（推理模型）生成文章，回复内容为空
- 错误做法：max_tokens 设 200/300 太小，token 被 reasoning_content 推理阶段吃光
- 正确做法：max_tokens 至少 8000；代理层把 reasoning_content 作为 content 兜底
- 状态：✅ 已修正（max_tokens 8000 + 兜底逻辑）

### [2026-08-28] 错误：Codex 写文件被沙箱拦截
- 场景：Codex 用 mimo 生成文章要写 /tmp/test_article.md，显示 _write_blocked
- 错误做法：默认 sandbox=read-only，mimo 推理模型把"只读"当障碍不执行写命令
- 正确做法：写文件需 `-c 'sandbox_permissions="disk-REDACTED-read-access"'`；或让 Codex 直接输出 stdout 再提取
- 状态：✅ 已修正（改用 stdout 提取方案）

### [2026-08-28] 错误：Codex 代理流式事件序缺失导致输出不显示
- 场景：Codex 连 mimo 代理，tokens used 有计数但 assistant 输出不显示
- 错误做法：只发 response.created / output_text.delta / response.completed
- 正确做法：完整事件序 output_item.added → output_text.delta → output_text.done → output_item.done → response.completed（缺 done 事件 Codex 丢弃输出）
- 状态：✅ 已修正（代理补全 done 事件）

### [2026-08-28] 错误：Codex wire_api 不支持 chat_completions
- 场景：直接配 mimo 的 chat/completions 接口到 Codex
- 错误做法：wire_api = "chat_completions"（Codex 只认 responses）
- 正确做法：自写本地代理（/opt/mimo-proxy/proxy.mjs）把 responses 转 chat/completions，wire_api 仍用 responses
- 状态：✅ 已修正（代理中转方案）

### [2026-08-19] 错误：跨用户日志权限静默停摆
- 场景：PM2 服务/crontab 从 aiecom 迁到 ubuntu，cron 重定向写 aiecom 属主 775 日志被拒
- 错误做法：整条 cron 命令失败且无告警（告警也在失败日志里）→ 停摆 38h 无人知
- 正确做法：跨用户共享日志必须 666 或统一属主；告警通道与业务日志分离
- 状态：✅ 已修正（ubuntu 加入 aiecom 组 + 验证心跳）

### [2026-08-13] 错误：axios 响应层级少取一层
- 场景：取列表数据报错
- 错误做法：`res.data.list`（少一层）
- 正确做法：`res.data.data.list`（API 返回 {code, data:{list}}）
- 状态：✅ 已修正

### [2026-08-13] 错误：dist 权限混用
- 场景：vite build（www-data）与 generate.js（root）写同一目录
- 错误做法：root 生成的文件导致后续构建 EACCES
- 正确做法：所有写 dist 操作统一 www-data，用 build.sh
- 状态：✅ 已修正

### [2026-08-13] 错误：Codex 沙箱初始化失败
- 场景：默认沙箱 bwrap 报错（loopback RTM_NEWADDR）
- 错误做法：直接跑默认沙箱
- 正确做法：目录属主非 ubuntu 用 `-s danger-full-access --skip-git-repo-check`
- 状态：✅ 已修正

### [2026-08-13] 错误：前端改动未真实浏览器验证
- 场景：SPA 渲染错误，只验 API 200 不够
- 错误做法：只 curl API 验证
- 正确做法：改前端必须 CDP 无头浏览器（127.0.0.1:9222）实测渲染结果
- 状态：✅ 已修正
