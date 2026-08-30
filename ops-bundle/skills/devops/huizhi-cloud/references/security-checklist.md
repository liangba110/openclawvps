# 安全部署检查清单（汇智云/Flask+Vue项目通用）

## Nginx 层

### 必需安全头
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```

### 速率限制
```nginx
# nginx.conf http {} 块
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_req_status 429;

# sites-available/* server {} 块
location /api/ {
    limit_req zone=api burst=50 nodelay;
}
```
> ⚠️ `limit_req_zone` 必须在 `http {}` 块，不能在 `server {}` 块！否则报错 `"limit_req_zone" directive is not allowed here`

### SSL
```nginx
ssl_protocols TLSv1.2 TLSv1.3;
```

## Flask 后端层

### 数据库连接池（DBUtils）
```python
from dbutils.pooled_db import PooledDB
_pool = PooledDB(
    creator=pymysql,
    mincached=2,       # 最少保持2个
    maxcached=10,      # 最多缓存10个
    maxconnections=20, # 最大连接数（抗并发）
    blocking=True,     # 无连接时等待
)
```
> MySQL 5.7 默认 max_connections=151，连接池 maxconnections 不能超过该值

### 密码哈希（bcrypt + SHA256兼容）
```python
def make_password(password):
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        # 兼容旧SHA256
        return hashlib.sha256(password.encode()).hexdigest() == hashed
```

### XSS 过滤中间件
```python
import re
_XSS_PATTERN = re.compile(
    r'<[^>]*script[^>]*>|<[^>]*on\\w+\\s*=|javascript\\s*:|<iframe|<embed|<object',
    re.I)

@app.before_request
def before_request():
    if request.method in ('POST', 'PUT') and request.content_type and 'json' in request.content_type:
        try:
            data = request.get_json(silent=True)
            if data:
                request.json_data = sanitize_dict(data)
        except Exception:
            pass
```
> ⚠️ 必须用 `request.get_json(silent=True)` 而非 `request.json`！`request.json` 在Content-Type不是application/json时会抛出415异常，即使try/except捕获了也会提前消耗请求体，导致后续路由的 `request.get_json()` 返回None。`silent=True` 在解析失败时返回None而不是抛异常。

### 路由内取值（必须做）
```python
# 优先使用经过XSS过滤的 json_data，否则回退到 get_json()
data = getattr(request, 'json_data', None) or request.get_json() or {}
phone = str(data.get('phone', '')).strip()
password = str(data.get('password', ''))
code = str(data.get('code', ''))
nickname = str(data.get('nickname', ''))[:20]  # 长度限制
```
> 不强制转 str 的话，None 值传到 SQL/比较时会出错

### 速率限制（Flask 端）
```python
_rate_limits = {}

def rate_limit(key, max_requests=60, window=60):
    now = time.time()
    if key not in _rate_limits:
        _rate_limits[key] = []
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]
    if len(_rate_limits[key]) >= max_requests:
        return False
    _rate_limits[key].append(now)
    return True

# 使用
ip = request.remote_addr or 'unknown'
if not rate_limit(f'reg:{ip}', max_requests=5, window=60):
    return fail('操作太频繁，请稍后重试')
```

## gunicorn 配置

```python
# gunicorn.conf.py
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
timeout = 60
keepalive = 5
max_requests = 1000           # 防内存泄漏
max_requests_jitter = 200     # 避免同时重启
accesslog = '/var/log/aiweb/access.log'
errorlog = '/var/log/aiweb/error.log'
```

## 前端层

### 输入框抖动（常见坑）
```css
/* ❌ 错误 */
.input { transition: all 0.3s; }
.card { transition: all 0.5s; }
.btn { transition: all 0.3s; }

/* ✅ 正确 */
.input { transition: border-color 0.2s, box-shadow 0.2s; }
.card { transition: border-color 0.3s, box-shadow 0.3s, transform 0.4s; }
.btn { transition: border-color 0.2s, box-shadow 0.2s, transform 0.3s; }
```
> `transition: all` 在页面因轮询/后台动画重渲染时会让所有属性变化产生动画，肉眼看起来就是"一直抖"

### Logo 点击
- 所有页面的Logo必须用 `<router-link to="/">` 包裹
- 在 `.page-header` 内需加 `position:relative; z-index:2` 避免被 `::before` 伪元素遮住

### JS 语法
- 使用 `catch(e) { ... }` 而非 `catch { ... }`（可选catch绑定在某些构建配置下可能导致finally不执行）
