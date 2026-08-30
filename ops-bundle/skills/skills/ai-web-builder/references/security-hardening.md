# 安全加固记录（2026-07-25）

## 改造清单

| 项目 | 之前 | 之后 |
|:----|:-----|:-----|
| 数据库连接 | 每次请求新建 PyMySQL 连接 | DBUtils 连接池（mincached=2, maxcached=10, maxconnections=20, blocking=True） |
| 密码哈希 | SHA256 | bcrypt，兼容旧 SHA256 |
| XSS 防护 | 无过滤 | before_request 对 POST/PUT JSON 做正则过滤 |
| 速率限制（Nginx） | 无限制 | API 30r/s + burst 50；登录 5次/分钟/IP |
| 安全头（Nginx） | 3 个 | 6 个（添加 XSS-Protection / HSTS / Permissions-Policy） |
| gunicorn workers | 4 固定 | CPU 核数 * 2 + 1 |
| Worker 生命周期 | 无限 | max_requests=1000 |
| 超时 | 无 | timeout=60s |

## before_request 陷阱（★★★）

**不可在 `@app.before_request` 中读取 `request.json` 或 `request.get_json()`。**

症状：所有 POST 接口在浏览器中无响应，但 curl 直接测试正常。

根因：`before_request` 消费了请求体后，后续路由 `request.get_json()` 返回空。

做法：`before_request` 只处理安全头，不碰请求体。XSS 过滤在具体路由内按需调用。
