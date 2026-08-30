# 安全加固

## 已实施的6项安全措施

### 1. 密码管理
- MySQL密码移到.env（权限600）
- config.py统一加载，不再硬编码

### 2. SQL注入防护
- 禁止DROP/DELETE/TRUNCATE/ALTER/UPDATE/INSERT
- 只允许SELECT只读查询

### 3. LLM自动执行白名单
- 只允许: systemctl, mysql, nginx, df, free, top, ps, ss, curl
- 禁止: rm -rf, DROP, DELETE等危险操作

### 4. IP封禁白名单
- 保护: 127.0.0.1, 42.193.113.230, 82.157.202.24等
- 永不封禁自有服务器IP

### 5. 回滚机制
- 操作前自动Git快照
- 失败时自动回滚到快照

### 6. 统一配置
- config.py从.env加载所有配置
- 路径/密码/API Key统一管理
