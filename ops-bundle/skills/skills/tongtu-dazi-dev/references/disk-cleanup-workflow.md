# 服务器磁盘清理标准流程

当用户要求"检测/清理磁盘"时，按以下层次逐步排查。

## 标准排查步骤

```bash
# 第1层：整体使用
df -h /

# 第2层：大目录排行（需逐个检查 /home /var /tmp /opt /usr /etc）
du -sh /home /var /tmp /opt 2>/dev/null | sort -rh

# 第3层：逐层钻取最大目录
du -sh /home/ubuntu/* 2>/dev/null | sort -rh | head -20
du -sh /home/ubuntu/.* 2>/dev/null | sort -rh | head -15  # 隐藏文件

# 第4层：/tmp 大文件
ls -lhS /tmp/ 2>/dev/null | head -10

# 第5层：日志占用
du -sh /var/log/* 2>/dev/null | sort -rh | head -10
journalctl --disk-REDACTED 2>/dev/null
```

## 常见可清理项

| 文件/目录 | 说明 | 安全删除 |
|-----------|------|---------|
| `/tmp/backup.tar.gz` | 旧临时备份 | ✅ 安全 |
| `~/.cache/` | pip/npm 缓存 | ✅ 安全，自动再生 |
| `~/.npm/` | npm 缓存 | ✅ 安全，npm install 时再生 |
| `/var/log/journal` | 系统日志 | ✅ `journalctl --vacuum-size=200M` |
| `~/.local/share/` | pip 缓存 | ✅ 可清 |
| `/tmp/*.bak` | 代码备份文件 | ✅ 安全 |

## 需要确认的目录

| 目录 | 常见内容 | 确认方式 |
|------|---------|---------|
| `~/hui_zhi_yun/` | 其他项目副本 | 问用户是否保留 |
| `~/python_site/` | 其他项目副本 | 问用户 |
| `~/myweb/` | 其他项目副本 | 问用户 |
| `~/.openclaw/` | Hermes Agent 文件 | ⚠️ 谨慎，可能影响代理功能 |

## 日志清理

```bash
# journal 日志限制到 200M
sudo journalctl --vacuum-size=200M

# 压缩旧日志
sudo logrotate -f /etc/logrotate.conf
```

## 安全规则

- 不清除 `~/.ssh/`、SSL 证书目录
- 不清除项目源码 `/opt/*`（除非确认不需要）
- `/var/log/journal` 用 vacuum-size 而不是直接 rm
- 对用户项目目录（`hui_zhi_yun`, `python_site`, `myweb`）先问用户再操作
