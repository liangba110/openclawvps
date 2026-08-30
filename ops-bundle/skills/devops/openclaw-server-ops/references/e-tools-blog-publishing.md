# E 上 TOOLS 工具箱站 · 文章发布工作流（2026-08-17 实测）

openclaw 在 E 上维护的自媒体教程站（属 openclaw-sites 能力授权区，禁碰 ttdazi）。

## 站点参数

| 项 | 值 |
|---|---|
| 域名 | `http://tools.ttdazi.xyz`（80 端口） |
| 兜底 | `http://185.239.224.191:8099`（IP 直连用这个，80 端口裸 IP 会 404） |
| 根目录 | `/var/www/openclaw-sites/tools` |
| nginx conf | `/etc/nginx/openclaw-conf/tools-blog.conf`（upload 500m、uploads 禁 PHP、html 禁缓存） |
| 文章数据源 | `assets/js/posts.js`（`const POSTS = {design:[], media:[], ops:[]}`，新增文章 = 登记条目 + 建 html） |
| 文章目录 | `posts/<分类>/media-<slug>-video.html`（自媒体类；design/ops 同理） |

## 文章模板格式（参照 media-trad-culture-video.html，30-40KB）

完整工作流文章固定结构（新文章照抄这套骨架）：
`<head> 禁缓存 meta + title(含 · TOOLS 工具箱) + kawaii.css + 🎋/🥬 favicon` →
`site-nav 导航(自媒体页 .active)` → `<h1>标题 + post-date` →
① 你将得到什么（阶段/产出/耗时表格）→ ② 整体流程 ol →
③ 豆包生图提示词 pre/code + blockquote 技巧 →
④ 稿定排版 → ⑤ DeepSeek PPT 骨架提示词 → ⑥ 补图逐页提示词表格 →
⑦ 脚本提示词 → ⑧ 剪映出片 → ⑨ 剪映高级感剪辑（运镜对照表 + 前景/环境音/节奏/调色 + 逐页剪辑对照表 + 自查清单）→
⑩ 经验总结 ul → ⑪ 🎨 逐页背景图预览（grid 3 列 figure+figcaption）→
⑫ 📦 配套素材下载 ul → footer(返回自媒体)。

图片引用：`../../download/uploads/<前缀>-bg01.png`（下载中心图片预览）；素材下载：`../../flow/uploads/<前缀>-…视频.mp4` / `…PPT.pptx`（URL 编码中文）。

## 素材命名与存放规范（用户明确）

- 前缀：项目英文小写，如 `dabaicai-`（胶州大白菜）。用户确认过："大白菜建议用 dabaicai"
- 逐页背景图：`<前缀>-bg01.png` ~ `bg10.png` + `<前缀>-cover.jpg`
- **下载中心 download/uploads/ 只放图片**（bg + cover），不放 PPT/视频
- flow/uploads/ 放 PPT(.pptx) + 视频(.mp4) + 背景图，命名 `dabaicai-大白菜宣传PPT.pptx`、`dabaicai-大白菜宣传视频.mp4`

## 发布操作步骤（root SSH 直改，比等 openclaw 自己写可靠）

```bash
# 1. 拉模板（看结构）：sed -n '60,200p' tools/posts/media/media-trad-culture-video.html
# 2. 本地写新 html → scp 上传 → chown openclaw:openclaw + chmod 664
# 3. posts.js 登记：先 scp 拉回本地改（node --check 校验 JS 语法），再传回 + 备份
#    cp assets/js/posts.js assets/js/posts.js.bak-YYYYMMDD
#    node 在 openclaw 用户 nvm 路径，root 下 node 不存在 → su openclaw 跑
# 4. 验证：curl 带浏览器 UA 测 200（E 有 UA 分流防护，裸 UA 会 404/转 D）
#    for 文章页 + posts.js + media.html + 图片 + 素材视频 全部 200
# 5. 浏览器打开文章页：控制台 0 错误；media.html 列表页确认新卡片置顶
```

## 排查"openclaw 自己写不了文章"

- gateway 正常 + 模型 200 但 agent 只输出"现在执行"无 tool_calls → **会话上下文撑爆**（cacheRead >10 万 tokens），Control UI New Chat 即可。⚠️ E 实例已于 2026-08-17 配置根治方案（模型 contextTokens=131072 + agents.defaults.compaction 自动压缩，见主 SKILL「上下文自动压缩」章节），旧会话仍建议 New Chat，新会话会自动压缩不再退化
- 文章写到一半 `stopReason=length` → 模型缺 maxTokens（见主 SKILL 坑速查）
- 相关会话日志：`/home/openclaw/.openclaw/agents/main/sessions/*.jsonl`（看最后几条 assistant 消息是否只有 text）
