# Server B OpenClaw 运维指南

Server B (82.157.202.24) 上运行 OpenClaw Gateway 服务，负责 QQ bot、微信 bot、LightClawBot 等聊天通道。

## 架构概览

| 组件 | 详情 |
|------|------|
| 二进制路径 | `~/.nvm/versions/node/v22.23.0/bin/openclaw` |
| OpenClaw 版本 | 2026.6.11 (e085fa1) |
| 数据目录 | `~/.openclaw/`（配置、agent、记忆、日志） |
| 配置文件 | `~/.openclaw/openclaw.json` |
| Gateway 端口 | 38598 (bind=lan, 0.0.0.0) |
| 服务管理 | systemd user service |
| 服务文件 | `~/.config/systemd/user/openclaw-gateway.service` |
| 日志文件 | `/tmp/openclaw/openclaw-YYYY-MM-DD.log` |
| 启动日志 | `~/.openclaw/startup.log` |
| 重启日志 | `~/.openclaw/logs/gateway-restart.log` |
| Dashboard | http://10.2.0.8:38598/{hash}/ |

## 诊断流程（OpenClaw 停止运行时）

```bash
# 1. 检查进程
ps aux | grep openclaw | grep -v grep

# 2. 检查端口
ss -tlnp | grep 38598

# 3. 检查包装脚本是否指向有效路径
cat /usr/local/bin/openclaw 2>/dev/null
cat /home/ubuntu/.nvm/versions/node/v22.23.0/bin/openclaw

# 4. 检查 systemd 用户服务状态
systemctl --user status openclaw-gateway.service

# 5. 检查启动日志
tail -30 ~/.openclaw/startup.log

# 6. 检查服务日志
journalctl --user -u openclaw-gateway.service -n 50 --no-pager

# 7. 检查文件日志
tail -50 /tmp/openclaw/openclaw-$(date '+%Y-%m-%d').log
```

## 常见故障

### 🔴 包装脚本指向已删除的 pnpm 路径

**根因**：磁盘清理时删除了 `~/.local/share/pnpm/` 目录，而 `openclaw` 包装脚本指向该路径。

**症状**：
```
/usr/local/bin/openclaw: line 3: /home/ubuntu/.local/share/pnpm/openclaw: No such file or directory
```

**修复**：
```bash
# 1. 删除旧的包装脚本
sudo rm -f /usr/local/bin/openclaw
rm -f /home/ubuntu/.nvm/versions/node/v22.23.0/bin/openclaw

# 2. 清理残留 node_modules
rm -rf /home/ubuntu/.nvm/versions/node/v22.23.0/lib/node_modules/openclaw
rm -rf /home/ubuntu/.nvm/versions/node/v22.23.0/lib/node_modules/.openclaw-*

# 3. 通过 npm 重装
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
npm install -g openclaw

# 4. 验证安装结果（应为 symlink 到 openclaw.mjs，不是包装脚本）
file /home/ubuntu/.nvm/versions/node/v22.23.0/bin/openclaw
# 期望输出: symbolic link to ../lib/node_modules/openclaw/openclaw.mjs
```

### 🔴 Gateway 服务未安装或已损坏

**症状**：`openclaw gateway status` 报服务文件缺失或路径错误。

**修复**：
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# 安装/修复 systemd 用户服务
openclaw gateway install --force

# 启用并启动
openclaw gateway start

# 验证
openclaw gateway status
```

### 🔴 开机不自启

**根因**：Ubuntu 用户服务的 linger 未启用，用户退出登录后服务不启动。

**修复**：
```bash
sudo loginctl enable-linger ubuntu
```

验证：
```bash
loginctl show-user ubuntu | grep Linger
# 期望输出: Linger=yes
```

## 启动流程

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# 方式1: 通过 systemd（推荐）
openclaw gateway start

# 方式2: 前台运行（调试用）
openclaw gateway --bind lan --port 38598 run

# 方式3: 后台 nohup（备用）
nohup openclaw gateway --bind lan --port 38598 run > ~/.openclaw/gateway.log 2>&1 &
```

## 验证运行状态

```bash
# Gateway 状态
openclaw gateway status

# 通道状态（可能耗时较长，设置足够 timeout）
openclaw channels status

# 关键指标检查
# 1. Gateway: bind=lan (0.0.0.0), port=38598
# 2. Runtime: running (pid X, state active)
# 3. 端口 38598 在监听
# 4. 日志中看到 "ready" 和各 channel 连接成功
```

## 通道日志关键行

```log
[gateway] ready                                    ← Gateway 启动成功
[heartbeat] started                                ← 心跳正常
[qqbot] ✅ Access token obtained successfully      ← QQ bot 鉴权成功
[qqbot] WebSocket connected                        ← QQ bot 连接成功
[qqbot] Gateway ready                              ← QQ bot 就绪
[openclaw-weixin] weixin monitor started           ← 微信 bot 启动
[lightclawbot] Resolved botClientId: ...           ← LightClaw 就绪
```

## 注意事项

- 安装后不要手动编辑 systemd 服务文件，用 `openclaw gateway install` 自动修复
- 重装 npm 包后 `openclaw gateway install` 会自动更新服务文件路径
- OpenClaw 配置和对话数据（`~/.openclaw/`）在重装时**不会丢失**
- 磁盘清理时切勿删除 `~/.openclaw/` 数据目录
