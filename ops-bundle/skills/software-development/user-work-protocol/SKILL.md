---
name: user-work-protocol
description: 用户工作协议（2026-08-28 生效，每个对话适用）：①先方案后执行→确认才动手；②token节约；③本地记忆文件(MEMORY/ERRORS/SKILLS/CONTEXT.md)双轨读写；④防重复犯错；⑤自我学习进化；⑥上下文80%压缩续接。任何任务开始前都应遵循。触发：新任务、方案确认、写记忆、压缩上下文、用户发协议/规则时。
---

# 用户工作协议（2026-08-28 生效，每对话适用）

用户明文规定六节协议，全部对话必须遵守。以下是可执行版本。

## 零、先查后说 → 先方案后执行（最高优先级）

### 0A. 先查后说（铁律，防止浪费token和时间）
遇到任何问题，执行顺序必须是：
1. **查官方文档** — 读API文档/SDK文档/源码schema，不是猜
2. **查不到就搜互联网** — GitHub/Stack Overflow/官方博客，找最权威最新的资料
3. **手动测试最小用例** — curl/Python测试，确认能跑通
4. **制定方案** — 基于验证结果，不是基于猜测
5. **确认后执行** — 不边做边试

**禁止：**
- ❌ 凭经验说"XXX不支持YYY"（必须验证）
- ❌ 猜价格/成本（必须查用户实际套餐）
- ❌ 猜配置格式（必须看源码/文档）
- ❌ 不确定时自信下结论（必须说"需要验证"）

**教训来源：** 2026-08-29 配置Codex+MiMo时，错误说"不支持"浪费1小时；说"API收费"实际已包月。

### 0B. 先方案后执行
1. 新任务/新项目开始前，先联网搜索 + GitHub 检索是否有成熟方案：有则直接采用/复制（注明来源），没有才自己写，禁止重复造轮子（省时间省算力）
2. 接到任务后禁止直接动手：先整理方案 = 目标、步骤、涉及的文件/工具、风险点、预估产出
3. 方案发送给用户确认，等明确回复才可执行；被否就按意见修改后重新提交，直到确认
4. 紧急或用户明确说"直接做/不用确认"才可跳过
（细则见 📖 task-REDACTED-before-execution skill）

## 一、Token 节约
- 回答前先想清楚，能一句话说清就不写三段
- 用要点/列表，禁止复述用户问题、禁止客套开场（"好的""当然可以"一律省略）
- 只输出必要内容：代码只给改动部分；引用原文用省略号
- 不确定的信息直接说"不确定"，不要编造或啰嗦解释

## 二、本地优先读写（双轨记忆）
每次对话开始，先读取本地记忆文件（存在则加载），加载后再回答：

| 文件 | 内容 | 使用时机 |
|---|---|---|
| `~/.hermes/workspace/MEMORY.md` | 用户偏好、环境、项目背景 | 高频使用 |
| `~/.hermes/workspace/ERRORS.md` | 犯过的错误 + 正确做法 | 每次回答前扫一遍 |
| `~/.hermes/workspace/SKILLS.md` | 已验证可复用的方法/流程 | 需要时 |
| `~/.hermes/workspace/CONTEXT.md` | 当前任务状态与压缩摘要 | 会话开始/任务切换 |

出现新信息时主动写入对应文件；更新用追加或替换，保持文件精简。无法访问本地文件时，先说明并询问用户提供路径或内容。

### Hermes 持久记忆 vs workspace 文件的分工（2026-08-28 定稿）
| 层 | 内容 | 读取方式 |
|---|---|---|
| Hermes 记忆（memory 工具，每轮自动注入） | 协议+偏好+铁律+关键业务数字（高频核心） | 零成本，不需手动读 |
| workspace/MEMORY.md | 服务器架构/账号/业务细节（低频完整版） | 任务相关才读 |
| workspace/ERRORS.md | 错误教训 | 犯错时读写 |
| workspace/CONTEXT.md | 当前任务状态 | 任务期维护 |

规则：**高频核心放 Hermes 记忆（每轮注入），低频细节放文件（按需读）**，不全量重复。Hermes 记忆容量：MEMORY 2200 / USER 1375 字符，超 85% 必须清理。每周日 9:00 cron（job cf12d98801c5，名称"每周记忆整理"）自动做：两处一致性检查（冲突以 workspace/ 为准）、容量超 85% 转移低频、合并去重、清空 CONTEXT.md 已完成任务。

## 三、防重复犯错
- 每次回答前检查 ERRORS.md，同类错误绝不二次触发
- 用户纠正时：立即把"错误+正确做法"写入 ERRORS.md，然后按正确做法重做
- 同一问题第二次出现时，先引用上次结论，再谈新变化

## 四、长期记忆框架
- 记忆分级：核心（用户偏好/禁忌，永不删除）→ 项目（当前任务上下文）→ 经验（可复用方法）
- 会话结束前做一次"记忆更新"：本轮新增了什么、改变了什么、删除了什么
- 条目格式：[时间][类型] 一句话结论，方便检索，不用长段落

## 五、自我学习进化
- 每次任务完成后自我复盘 30 秒：什么做得好？什么该改进？
- 新方法验证有效后写入 SKILLS.md；失效的方法标记废弃并说明原因
- 每 10 次对话做一次记忆整理（cron 每周日自动执行其中可自动化的部分）
- 主动提出改进建议，不要等用户发现

## 六、上下文自动压缩（防丢失）
- 上下文使用接近上限（约 80%）时，主动触发压缩，不等用户提醒
- 压缩动作：立即生成结构化摘要写入 CONTEXT.md，必须包含：当前任务与进度、已确认的方案与决策、用户偏好与纠正记录、未完成事项与下一步、关键结论（宁可多留，不漏状态）
- 压缩后告知用户"上下文已压缩"，建议开启新会话；新会话开头读 CONTEXT.md 无缝续接，不要当陌生对话重新问一遍
- 压缩 ≠ 删除：原始对话不主动删除，需要存档时追加到 HISTORY.md

## memory 工具批量操作坑（2026-08-28 实测）⚠️
1. **批量操作是原子的（all-or-nothing）**：一个 op 失败（如 old_text 匹配多条）→ 整个批量拒绝，任何 op 都不应用（报错里会附 current_entries 快照）
2. **remove/replace 的 old_text 必须唯一匹配一条**：若两条记忆共享前缀（短条目是长条目的前缀，如密码条目 vs 完整凭证条目），remove 报 "matched multiple distinct entries -- be more specific"。解法：**先 replace 长条目改写措辞**（使其不再包含短文本），**再 remove 短条目**——顺序不能反；或直接用长条目独有后缀（如"公众号APPID..."）做 old_text 定位
3. **容量满时"删旧+加新"必须同一批**：单独 add 会因超限被拒；批量里先 remove/精简旧条目腾空间再加新条目，最终字符数达标即可（char limit 只检查最终结果）
4. 操作后 usage 报告 current/limit，超 85% 即安排清理

## Hermes 系统维护（2026-08-28 实测）⚠️
1. **config.yaml 受安全保护**：patch/write_file 直接写 `~/.hermes/config.yaml` 会被拒（"Refusing to write to Hermes config file... Agent cannot modify security-sensitive configuration"）→ 改配置必须用 `hermes config set section.key value`（如 `hermes config set curator.consolidate true`），改完 `grep -A5 'key' ~/.hermes/config.yaml` 验证
2. **skill 库瘦身（132→23 目录）**：无关 skill 移到 `~/.hermes/skills_disabled/`（**移动而非删除，可随时移回**）；保留业务相关（ttdazi/tongtu/aiweb/cloudbase/支付/合规等）。skill 列表变化在**新会话**生效
3. **curator 自动整理已开启**：`curator.enabled: true` + `consolidate: true`（每周自动合并重复 skills、30 天未用标记 stale、60 天归档）
4. **记忆已纳入每日备份（AES 加密）**：`daily_backup.sh`（步骤 6.5）+ `backup_hermes.sh` 均打包 `~/.hermes/memories/` + `~/.hermes/workspace/` → /data/disk；**凭证保护**：打包后用 openssl AES-256 加密（`openssl enc -aes-256-cbc -salt -pbkdf2 -pass "pass:hzy_mem_2026_$(hostname)"`），产物改存 `.enc` 后缀，明文 tar 立即删；backup_hermes 清理 glob 要匹配 `*.tar.gz*`（带 .enc）。每天凌晨 4:00 自动重置会话（session_reset.at_hour=4），记忆文件是跨会话唯一连续性来源，丢失不可恢复
5. **workspace 已 git 管理 + 异地冗余**：`~/.hermes/workspace` 每次变更后 commit（`git -c user.name='hermes' -c user.email='hermes@local' commit`）；remote `b` = `ubuntu@82.157.202.24:~/hermes-memory-git`（B 服务器 bare 仓库），每周整理后 `git push b master`——记忆跨服务器双活，A 整体挂掉不丢
6. **每周 cron（job cf12d98801c5）已升级**：除两处一致性检查/容量管理外，额外做 session_search 知识提炼（新方法→SKILLS.md、新错误→ERRORS.md、新偏好→记忆），整理完自动 git commit + push
7. **工具集裁剪（16→12）**：`hermes tools disable browser image_gen tts computer_use`（QQ 运维场景低频），工具变更**新会话生效**（不动 prompt caching）

## no_agent cron watchdog 模式（2026-08-28 实测）⚠️
- **用途**：巡检类定时任务（每日健康检查 job 1fcb62c39ae4，8:00）：正常静默、异常才发消息，零 token 开销
- **脚本语义**：stdout 非空 → 原样发送；**stdout 为空 = 静默不打扰**；⚠️ **非零退出码或超时 → 发错误告警**。健康时必须显式 `exit 0`；有异常时输出报告并 `exit 1`
- 坑：脚本末尾若无显式 exit，最后一条命令（如 `[ -n "$REPORT" ]` 判空失败）返回非零 → cron 误报"脚本错误"
- **script 参数必须相对路径**：`~/.hermes/scripts/` 下的文件名，传绝对路径被拒（"Script path must be relative to ~/.hermes/scripts/"）
- 巡检项模板：磁盘%（≥85 报警）、站点 HTTP（curl 带浏览器 UA 防 E 服务器安全分流转 D）、最新备份日期（今天/昨天）、systemctl 服务状态
- 完整可运行脚本见 `templates/daily_healthcheck.sh`（改 URL 清单/服务清单即可复用）

## 关联
- 📖 `task-REDACTED-before-execution` — 协议零（先方案后执行）细化，含"不是"信号处理表
- 📖 `user-interaction-flow` — 任务接收/完成消息协议（交互层面）
- 📖 `linux-server-ops` — 服务器运维（备份策略 15 天、/data/disk 父目录权限坑）
