---
name: openclaw-ops
description: openclaw 服务器部署与运维。覆盖：openclaw 安装、配置、升级、插件管理、API 对接、故障排查。
version: 1.0.0
author: hermes
---

# OpenClaw 运维 Skill

## 触发条件
- 用户提到 openclaw、claw、E 服务器
- 部署/配置/升级 openclaw

## 服务器信息
- **地址**：E 服务器 185.239.224.191（东京，2核3.8G/40G）
- **系统**：Ubuntu，root 密钥 SSH，fail2ban
- **用户**：openclaw（降权用户，无 sudo）
- **UI 端口**：IP:18789 / oc3385
- **域名**：E 服务器开放（国际站），openclaw 是全新个人助理（业务记忆已清空）
- **数据库**：自建库 openclaw，密码见 /etc/openclaw-db-credentials
- **站点目录**：/var/www/openclaw-sites/ + 自建库 openclaw + php8.3

## 关键操作

### 部署
1. SSH 到 E 服务器（root@185.239.224.191，用 ~/.ssh/id_ed25519）
2. 确认 nvm/node 版本（v22+）
3. `pnpm install && pnpm build`（如果源码目录）
4. 配置 systemd 服务（openclaw 用户运行）
5. 配置 Caddy/Nginx 反代（如有域名）

### 升级
```bash
cd /path/to/openclaw
git pull
pnpm install && pnpm build
systemctl restart openclaw
```

### 安全
- 用户 openclaw 无 sudo（降权）
- 禁碰 /var/www/ttdazi（同途搭子站点）
- fail2ban 已启用（SSH 防暴力破解）
- E 服务器安全分流：恶意 UA/路径 → 反代 D(/__guard__)，curl 必须带浏览器 UA

### 常见问题
- **openclaw 连接失败**：检查 systemd 状态、端口监听、防火墙
- **数据库连接错误**：确认 /etc/openclaw-db-credentials 密码正确
- **升级后不生效**：清缓存 + rebuild

## 注意事项
- E 服务器是海外，curl 测试必须带浏览器 UA（否则被安全分流转 D 旧版）
- openclaw 是全新个人助理，业务记忆已清空
- 可自建站 /var/www/openclaw-sites/，但禁碰 /var/www/ttdazi
