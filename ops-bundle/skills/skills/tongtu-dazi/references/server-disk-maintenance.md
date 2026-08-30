# 服务器磁盘清理维护

## 场景

服务器磁盘告警（≥90%），需排查并清理无用文件。Server B（Nginx）是常见瓶颈点。

## 标准排查流程

### 1. 整体概况

```bash
df -h /
```

### 2. 大目录排行

```bash
# 粗筛
du -sh /home/* /var/* /tmp/* /opt/* 2>/dev/null | sort -rh | head -20

# 隐藏文件（home 下 .local .cache .npm 等）
du -sh /home/ubuntu/* /home/ubuntu/.* 2>/dev/null | sort -rh | head -30
```

### 3. 日志清理

```bash
# systemd journal 保留近3天
sudo journalctl --rotate --vacuum-time=3d

# 或限制最大用量
sudo journalctl --vacuum-size=200M
```

### 4. 构建/包缓存

| 缓存路径 | 命令 | 安全 |
|---------|------|------|
| `~/.cache/` | `rm -rf ~/.cache/*` | ✅ pip/npm 缓存，可重建 |
| `~/.npm/_cacache` | `npm cache clean --force; rm -rf ~/.npm/_cacache` | ✅ 可重建 |
| `~/.local/share/pnpm/` | `rm -rf ~/.local/share/pnpm` | ✅ pnpm 缓存，可重建 |
| `node_modules/` | 保留（可删但需 `npm install` 恢复） | ⚠️ 代码必须保留 |

### 5. 临时备份文件

```bash
# 常见残留
rm -vf /tmp/*.tar.gz /tmp/*.bak /tmp/*.bak.*
```

### 6. 不相关项目

Server B 上可能残留旧项目副本，与 ttdazi 无关：

| 典型目录 | 说明 |
|---------|------|
| `~/hui_zhi_yun/` | 旧汇智云项目（另一个系统） |
| `~/python_site/` | 陪玩系统副本 |
| `~/myweb/` | 其他 Web 项目（含 venv） |
| `~/.transparent-background/` | AI 抠图模型，与网站无关 |

确认无关后删除：
```bash
rm -rf ~/hui_zhi_yun ~/python_site ~/myweb ~/.transparent-background
```

### 7. 代理工具临时文件

`.openclaw/` 是 Hermes/OpenClaw 核心，只清理 workspace 临时文件：

```bash
rm -rf ~/.openclaw/workspace/output
rm -rf ~/.openclaw/workspace/1panel-*
rm -f ~/.openclaw/workspace/*.mp4
```

## 典型结果

| 阶段 | 措施 | 释放 |
|------|------|------|
| 1 | `/tmp/` 临时备份 | ~4.6G |
| 2 | `.cache` + `.npm` + pnpm | ~2.7G |
| 3 | journal 日志 | ~250M |
| 4 | 不相关项目 | ~800M |
| 5 | workspace 临时文件 | ~270M |
| **合计** | | **~7-10G** |

## 常见陷阱

- **必须确认目录与当前项目无关再删除** — 先 `ls` 查看内容，确认不是 ttdazi 或其依赖
- **`.openclaw/agents/` 和 `.openclaw/extensions/` 不可删** — Hermes 核心组件
- **SCP 大文件传输超时** — 99MB 以上用 background 模式传输
- **deploy 后检查构建产物** — `npm run build` 末尾必须有 `✓ built in Xs`
