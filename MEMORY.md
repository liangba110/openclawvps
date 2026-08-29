# MEMORY —— 核心偏好与背景（永不删除）

## 关于我
- 称呼：老板
- 语言：中文（回复一律中文）
- 主工作目录：/home/ubuntu/.openclaw/workspace

## 偏好（永不删除）
- 先方案后执行：任务必须先出方案，确认后才动手
- 先联网搜索+GitHub查成熟方案，有则复用，禁止重复造轮子
- 简洁直接，不要客套，要点/列表输出
- 中文回复

## 禁忌（永不删除）
- 未确认方案前禁止执行
- 禁止编造；做不到就直说
- 禁止浪费token（重复原文、长篇解释）

## 本机环境
- Ubuntu（Linux 6.8.0-117-generic x64，腾讯云 VM）
- 主模型：deepseek/deepseek-v4-flash

---

## 代码规范（所有补丁用 Codex CLI）
- 重构/优化/调试/修bug一律用 Codex：`codex exec -C <目录> --skip-git-repo-check "任务"`
- 非ubuntu目录加 `-s danger-full-access`
- 任务失败 → `bash /data/disk/codex_fix.sh "任务名" "失败描述"`

## 网站运维铁律
- 操作前确认状态，操作中最小化停机，操作后验证恢复
- 能不停机就不停机（软链接/PM2 reload/nginx reload优先）
- 每一步验证网站仍正常（HTTP 200、API健康）再继续下一步
- 涉及密钥/token时不要输出到公开日志

---

## 公司架构（25人，2026-07-01更新）
```
👑 老板 → 📋 小丽(助理)
├── 技术产品部（小伟主管）：小伟、小Py、小美、小测、小程、小码
├── 市场运营部（小策主管）：小策、小雪、小薇、小言、小文、小东、小拍、小播
├── 设计部（小艺）
├── 法务合规部（小律主管+小审）← 直接向老板负责
└── 综合管理部（小东主管）：小东、小财、小味、小红、小玄、小HR
```
运营模式：老板群里发任务→我分配→主管安排员工执行→完成

## 账号信息
- 管理后台：https://www.openai2000.cn/login（Node 127.0.0.1:8081，pm2 huizhiyunma-api）
- 管理员：admin / HzyM2026!@
- 测试号：19900001001/1002/1003，密码123456
- 微信聊天ID：o9cq8082j1wexmhXHltQk4XvA-iU@im.wechat

## SEO脚本（每天3篇分时段）
- 路径：/data/web/huizhiyunma/backend/seo/
- 09:00/13:00/17:00 发布 → root crontab
- 手动运行：`bash run_generate_article.sh [1|2|3]`
- 关键教训：模型是推理模型，max_tokens需8000以上，太小会JSON解析失败
- site参数禁止encodeURIComponent（编码→400）

## 百度推送铁律
- site参数禁止编码，必须原样传递；token可以编码

## 备份与恢复
- 自动备份：每天08:00/14:00/22:00，保留7天
- 恢复：`sudo bash /data/disk/restore.sh`

## 品牌视觉（2026-06-30定稿，永不再改）
- Logo V3（6版本）、Favicon V4（蓝紫渐变+白色手柄）

## 近期项目
- 2026-08-26：全自动运维营销上线（SEO+案例包+营销草稿）
- 2026-08-27：小红书AI创作工具部署
- 2026-08-28：案例资料包上线+广告法修复
- 2026-08-29：ops-bundle安全修复4轮+V2智能运维上线+OpenClaw优化
