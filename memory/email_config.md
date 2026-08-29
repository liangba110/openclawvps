# 邮件配置

## 163 邮箱（SMTP 发件账号，主站后端 mailer.js 使用）
- 邮箱: idc8000com@163.com
- SMTP 服务器: smtp.163.com
- SMTP 端口: 465 (SSL)
- SMTP 授权码: XRCVGXzqQfFK8qSB（2026-08-09 04:36 更新，为最新有效密钥；旧码 SHc4s3A78DaC5kpZ / GZgELw9Zqy9nhfDN 均已验证仍有效，备用）
- 收件人（通知目标）: 964539086@qq.com
- 配置位置: /data/web/huizhiyunma/backend/.env（已备份 .bak_20260809_0435）
- 验证状态: ✅ 认证成功 + 实测发信成功（messageId 96744983...）

## QQ邮箱（收件箱）
- 邮箱: 964539086@qq.com
- SMTP 服务器: smtp.qq.com
- SMTP 端口: 465 (SSL)
- SMTP 授权码: (未设置，当前仅作收件箱使用；如需从 QQ 发信需生成授权码)

## ai-ecom 站点邮件模块（2026-08-09 搭建）
- 模块：/data/disk/ai-ecom/lib/mail.ts（TypeScript，nodemailer 9.0.5 + @types/nodemailer）
- 接入：/data/disk/ai-ecom/app/api/pay/notify/route.ts（支付成功 → 发通知邮件）
- 配置：/data/disk/ai-ecom/.env（SMTP_HOST/PORT/USER/PASS/NOTIFY_EMAIL，备份 .env.bak_20260809_0440）
- 进程：aiecom 用户 pm2 ai-ecom-site（属主 aiecom:aiecom）
- ⚠️ 写文件/装依赖需用 Codex 通道（ubuntu 无写权限，sudo 被 allowlist 拦）
