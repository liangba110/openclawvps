# 安全加固记录 2026-07-25

## 改动

### 1. 数据库连接池（DBUtils）
- 文件: `backend/db.py`
- 之前: 每次请求新建 PyMySQL 连接
- 之后: PooledDB 连接池，`mincached=2, maxcached=10, maxconnections=20, blocking=True`
- 依赖: 安装 `DBUtils` 包

### 2. 密码哈希升级（bcrypt）
- 文件: `backend/utils.py`
- 之前: `hashlib.sha256(password.encode()).hexdigest()`
- 之后: `bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()`
- 兼容: `check_password()` 捕获 bcrypt 异常后降级到 SHA256 比对
- 依赖: 安装 `bcrypt` 包
- 注意: 旧密码哈希在首次登录时仍然可用（兼容降级），但新注册用户使用 bcrypt

### 3. Nginx 安全头
- 文件: `server_b_nginx.conf`
- 添加:

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```

```nginx
# 限制在 nginx.conf http {} 块中定义
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_req_status 429;
```

### 4. Flask 速率限制（后端）
- 文件: `backend/main.py` — `rate_limit()` 函数
- 注册接口: 5次/分钟/IP
- 文件: `backend/app/auth.py` — 调用 `rate_limit(f'reg:{ip}', 5, 60)`

### 5. gunicorn 配置
- 文件: `backend/gunicorn.conf.py`
- workers: `cpu_count() * 2 + 1`（自动适配服务器）
- max_requests: 1000（每个 worker 处理 1000 请求后自动重启）
- 日志: `/var/log/aiweb/`

### 6. XSS 过滤（输入清洗）
- 文件: `backend/main.py` — `sanitize_dict()` 和 `_XSS_PATTERN`
- 过滤正则: `r'<[^>]*script[^>]*>|<[^>]*on\w+\s*=|javascript\s*:|<iframe|<embed|<object'`
- ⚠️ 注意: 不要在 `@app.before_request` 中访问 `request.json`，这会消费请求体。在路由函数内按需调用。

### 7. 输入类型强制
- 所有路由处理函数改为: `str(data.get('key', ''))` 而非 `data.get('key')`
- 避免 None/null 导致 DB 查询异常

## 验证命令

```bash
# 检查安全头
curl -skI https://aiweb.openai2000.cn/api/health | grep -i 'x-\|strict\|referrer\|permission'

# 检查 DB 连接池
curl -s http://127.0.0.1:5003/api/health

# 检查 gunicorn workers
ps aux | grep gunicorn

# 重新加载 Nginx
ssh ubuntu@82.157.202.24 "sudo nginx -t && sudo systemctl reload nginx"
```

## 陷阱记录

### before_request 消费请求体
- 在 `@app.before_request` 中访问 `request.json` 会消费请求体
- 导致所有 POST 接口（注册、登录、生成）在浏览器中无响应
- curl 测试正常（因为直接测试不会触发 before_request 的 JSON 解析问题）
- **修复:** `before_request` 只处理安全头，不碰请求体

### systemd gunicorn 路径
- ❌ `ExecStart=/usr/local/bin/gunicorn` → Error 203/EXEC
- ✅ `ExecStart=/opt/aiweb/venv/bin/gunicorn` + `Environment=PATH=/opt/aiweb/venv/bin:...`
