# MySQL连接池优化模式

## 问题模式

Flask + pymysql 项目中，`db/__init__.py` 的 `get_connection()` 每次调用 `pymysql.connect()` 创建全新TCP连接。

**泄漏检测公式**：
```
泄漏数 = grep -c "get_connection" app/*.py 减去 grep -c "conn.close" app/*.py
```

同途搭子项目实测：299 处调用，243 处关闭，**56 处潜在泄漏**。

## 根因

1. **无连接池** — 每个请求新建 TCP 连接，不复用
2. **缺少 finally: conn.close()** — 异常路径下连接不释放
3. **max_connections 默认151** — 高并发下迅速耗尽

## 修复方案：DBUtils PooledDB

### 安装

```bash
# PEP 668 系统（Ubuntu 24.04+）
pip3 install --break-system-packages DBUtils

# 验证安装（必须在目标Python版本下验证）
/usr/bin/python3.12 -c "from dbutils.pooled_db import PooledDB; print('OK')"
```

**PEP 668 陷阱**：系统 Python 被标记为 externally-managed，直接 `pip3 install` 会报错。必须加 `--break-system-packages`。

### 配置参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| maxconnections | workers × 25 | gunicorn 2 workers → 50 |
| mincached | 5 | 启动预建，避免冷启动延迟 |
| maxcached | 20 | 空闲回收，防止内存泄漏 |
| blocking | True | 池满排队，不报错 |
| ping | 1 | 获取时检测死连接 |

### 运行时调整 max_connections

无需重启 MySQL：
```sql
SET GLOBAL max_connections = 300;
```

验证：
```sql
SHOW VARIABLES LIKE 'max_connections';
SHOW STATUS LIKE 'Threads_connected';
```

## 验证清单

- [ ] 服务重启后无 ImportError
- [ ] API 正常响应（curl 测试）
- [ ] MySQL Threads_connected 稳定（不持续增长）
- [ ] journalctl 无错误日志

## 同途搭子实施记录（2026-08-29）

- 安装 DBUtils 3.2.0 到 `/home/ubuntu/.local/lib/python3.12/site-packages/`
- 改造 `backend/db/__init__.py` 使用 PooledDB
- max_connections 151 → 300
- 重启 ttdazi.service，验证正常
- 3 个 MySQL 连接数工单全部 done
