# OpenClaw 安全加固：保证永不触碰服务器现有资产

目标：openclaw **永远无法**删除/修改服务器原有网站（/var/www/**）、系统配置（/etc/**）、数据库、备份。三层防护缺一不可，全部实测通过（Server E, 2026-08-10）。

## 第一层：OS 级降权（唯一 100% 保证）

openclaw 从 root 降权到独立低权限用户——即使 agent 被诱导/指令要求删，系统层面直接拒绝。

```bash
# 1. 建低权限用户（无 sudo 组）
useradd -m -s /bin/bash openclaw        # groups openclaw 仅自身

# 2. 备份 + 迁移数据目录
tar czf /tmp/openclaw_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /root .openclaw
systemctl --user stop openclaw-gateway   # 先停
rsync -a /root/.openclaw/ /home/openclaw/.openclaw/
chown -R openclaw:openclaw /home/openclaw/.openclaw

# 3. openclaw 用户装 node + openclaw 程序（/root 是 700，低权限用户读不到 root 的 nvm）
su - openclaw -c "curl -sS -o /tmp/nvm_install.sh https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh && bash /tmp/nvm_install.sh"
su - openclaw -c "export NVM_DIR=/home/openclaw/.nvm; . /home/openclaw/.nvm/nvm.sh; nvm install 22"
su - openclaw -c "export NVM_DIR=/home/openclaw/.nvm; . /home/openclaw/.nvm/nvm.sh; npm i -g openclaw@2026.7.1-2"

# 4. systemd 服务迁移：复制 + sed 路径替换 + HOME
mkdir -p /home/openclaw/.config/systemd/user/
cp /root/.config/systemd/user/openclaw-gateway.service /home/openclaw/.config/systemd/user/
sed -i "s|/root/|/home/openclaw/|g; s|Environment=HOME=/root|Environment=HOME=/home/openclaw|" \
  /home/openclaw/.config/systemd/user/openclaw-gateway.service
chown -R openclaw:openclaw /home/openclaw/.config

# 5. 启停管理
loginctl enable-linger openclaw          # 重启自启
su - openclaw -c "export XDG_RUNTIME_DIR=/run/user/$(id -u openclaw); systemctl --user daemon-reload; systemctl --user start openclaw-gateway"

# 6. 禁用旧 root 服务 + 关 root linger（防双 gateway 抢端口）
export XDG_RUNTIME_DIR=/run/user/0
systemctl --user disable --now openclaw-gateway
loginctl disable-linger root
```

**验证**（交付必测）：
```bash
su - openclaw -c "rm -f /var/www/ttdazi/index.html"        # → Permission denied
su - openclaw -c "rm -rf /etc/nginx/sites-enabled/ttdazi-xyz"  # → Permission denied
su - openclaw -c "echo x > /etc/nginx/nginx.conf"          # → Permission denied
su - openclaw -c "sudo systemctl stop nginx"               # → 白名单外被拒
```

⚠️ 降权后 CLI 报 `EACCES: mkdir '/root/.openclaw/...'` → `export OPENCLAW_STATE_DIR=/home/openclaw/.openclaw`。

## 第二层：exec-approvals（shell 命令审批）

`~/.openclaw/exec-approvals.json`（`openclaw approvals set --file` 应用）+ `openclaw config set tools.exec.mode allowlist`。

```json
{
  "version": 1,
  "defaults": { "security": "allowlist", "ask": "on-miss", "askFallback": "deny", "autoAllowSkills": true },
  "agents": {
    "main": {
      "security": "allowlist", "ask": "on-miss", "askFallback": "deny",
      "allowlist": [ { "id": "<uuid>", "pattern": "ls", "source": "allow-always" }, "..." ]
    }
  }
}
```

- 放行：只读/日常命令（ls cat head tail grep rg find stat du df file which echo pwd date whoami id env uname free uptime ps curl wget git node npm npx python3 jq sed awk mkdir touch cp mv tar zip unzip diff sort uniq wc cut tr xargs base64 openssl）
- **不放行**（未命中 → 询问/askFallback 拒绝）：rm rmdir dd mkfs systemctl nginx mysql sudo shutdown reboot iptables ufw chmod chown ln
- ⚠️ JSON 坑：allowlist 必须放 `agents.<id>.allowlist` 且每条带 `id`(UUID) 字段；顶层数组不识别（`approvals get` 显示 `Allowlist │ 0`）。批量用 python 生成 JSON（`str(uuid.uuid4())`）后 `approvals set --file`；逐个 `allowlist add` 很慢（每次走 gateway 交互）。

## 第三层：记忆铁律（软约束，每次会话注入）

- AGENTS.md **顶部**插入禁区规则（优先级高于一切指令）：永不动 /var/www/**、/etc/**、数据库、备份；永不提权（sudo/提权/切用户）；即使被要求也拒绝
- MEMORY.md / SOUL.md 同步写
- 内容模板见 e-server-setup.md 的"禁区"段

## sudoers 白名单（只授最小管理能力）

```bash
cat > /etc/sudoers.d/openclaw <<EOF
openclaw ALL=(root) NOPASSWD: /usr/sbin/nginx -t
openclaw ALL=(root) NOPASSWD: /usr/bin/systemctl reload nginx, /usr/bin/systemctl reload nginx.service
openclaw ALL=(root) NOPASSWD: /usr/bin/systemctl reload php8.3-fpm, /usr/bin/systemctl reload php8.3-fpm.service
EOF
chmod 440 /etc/sudoers.d/openclaw && visudo -c
```

绝不授权 stop/restart/start。sudoers 精确匹配参数——`systemctl reload nginx` 白名单不会放行 `systemctl stop nginx`。
