# 数据盘备份记录日报（cron + 脚本）

## 用途
用户要求每天收到 Server A 数据盘备份记录。Hermes cron 每天早上 08:00 推送备份日报到 QQ。

## 配置（2026-07-31 建立）
- cron job：`数据盘备份记录日报`（no_agent=true，script=`data_disk_backup_report.py`，schedule `0 8 * * *`，deliver=origin）
- 脚本：`~/.hermes/scripts/data_disk_backup_report.py`（Python，SSH 到 Server A 读取备份目录）

## 脚本要点
- SSH 直连：`ssh -o BatchMode=yes root@42.193.113.230`（密钥认证，本机可直接连，无需密码）
- 读取 `/root/data/disk/daily_*`（Server A 每日备份目录：02:00 ttdazi / 03:30 aiweb 写入）
- 输出：最新备份内容明细（huizhiyun/aiweb 双库 SQL + 源码包 + 上传文件，含大小和空文件校验）、
  全部历史备份记录（du -sb 算各目录大小）、数据盘 df 使用率
- 失败时输出错误信息并 exit 1（cron no_agent 模式会推送错误告警）
- 时间解析：目录名 `daily_20260731_020002`，需去掉 `_` 再切分（`20260731` + `020002`）

## 备份体系背景
- Server A 数据盘 `/root/data/disk/`：`/opt/ttdazi/daily_backup.sh`（02:00，huizhiyun 库+ttdazi 程序+uploads，保留 7 天/3 份）、`/opt/aiweb/daily_backup.sh`（03:30，aiweb 库+程序，保留 90 天）
- 本机另有 `/home/ubuntu/backups/auto_*`（Hermes cron `每日自动备份`，6/14/22 点跑 auto_backup.sh，保留 7 天）——两者是不同备份，日报只报 Server A 数据盘

## 修改/验证
```bash
python3 ~/.hermes/scripts/data_disk_backup_report.py   # 手动跑一次看输出
# cron 管理：hermes cronjob list / update（job name: 数据盘备份记录日报）
```
