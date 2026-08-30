# 财务数据每日备份

每日三次自动备份所有财务数据到 `app/backups/finance_backup_{日期}_{时段}.json`：

| 时段 | 时间 | 文件名后缀 |
|------|------|-----------|
| 🌅 早 | 08:00 | `_早.json` |
| 🌤 中 | 14:00 | `_中.json` |
| 🌙 晚 | 22:00 | `_晚.json` |

## 备份内容

- money_log 财务日志
- orders 订单金额/抽成/收入
- withdraw 提现记录
- wallet_recharge 充值记录
- user.balance 用户余额

## 脚本位置

`/opt/ttdazi/scripts/finance_backup.py` / `~/.hermes/scripts/finance_backup.py`

## 存储位置

`/opt/ttdazi/backend/app/backups/finance_backup_*.json`（可通过下载页面密码验证后下载）

## 输出格式

JSON 文件：export_time + period + data（含全部字段）
