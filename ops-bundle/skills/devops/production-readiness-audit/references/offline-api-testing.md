# 离线 API 端到端测试指南（浏览器不可用时）

当浏览器无法访问外网服务器（`ERR_BLOCKED_BY_CLIENT`、网络隔离、代理限制）时，使用终端工具替代浏览器验证。

## 核心方法

### 1. 生成 JWT Token 绕过验证码

```bash
cd /opt/ttdazi
PYTHONPATH="/home/ubuntu/.local/lib/python3.12/site-packages" python3.12 << 'PYEOF'
import sys
sys.path.insert(0, '/opt/ttdazi/backend')
sys.path.insert(0, '/home/ubuntu/.local/lib/python3.12/site-packages')
from app.utils import create_token

# 测试用户 token
user_token = create_token(10001, '13800138000')
with open('/tmp/user_token.txt', 'w') as f:
    f.write(user_token)

# 管理员 token
admin_token = create_token(10045, 'ops_admin')
with open('/tmp/admin_token.txt', 'w') as f:
    f.write(admin_token)

print(f'User token: {user_token[:40]}...')
print(f'Admin token: {admin_token[:40]}...')
PYEOF
```

### 2. 关键测试清单

```bash
TOKEN=$(cat /tmp/user_token.txt)
ADMIN_TOKEN=$(cat /tmp/admin_token.txt)

# 公开 API
curl -s "http://82.157.202.24/api/health"
curl -s "http://82.157.202.24/api/companion/list"
curl -s "http://82.157.202.24/api/game/list"
curl -s "http://82.157.202.24/api/demand/list"
curl -s "http://82.157.202.24/api/captcha/get"

# 用户端 API（需 token）
curl -s -H "Authorization: Bearer $TOKEN" "http://82.157.202.24/api/user/info"
curl -s -H "Authorization: Bearer $TOKEN" "http://82.157.202.24/api/message/count"
curl -s -H "Authorization: Bearer $TOKEN" "http://82.157.202.24/api/coupon/available"
curl -s -H "Authorization: Bearer $TOKEN" "http://82.157.202.24/api/review/my"

# 管理端 API（需 admin token）
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://82.157.202.24/api/admin/dashboard"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://82.157.202.24/api/admin/users"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://82.157.202.24/api/admin/playmates"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://82.157.202.24/api/admin/orders"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://82.157.202.24/api/admin/finance"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://82.157.202.24/api/admin/messages"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://82.157.202.24/api/admin/verifies"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://82.157.202.24/api/admin/reviews"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://82.157.202.24/api/admin/login-log"
```

### 3. 验证要点

- 所有 API 返回 `code: 0`
- 多方法路由需分别测试 GET/POST/PUT/DELETE
- 需要 Content-Type: application/json 的 POST 要加 `-H "Content-Type: application/json"`
- 需要请求体的 POST 要加 `-d '{"key":"value"}'`

### 4. 常见错误处理

| 现象 | 原因 | 修复 |
|------|------|------|
| 404 Not Found | URL 拼写错误或路由不存在 | 检查 main.py 或 blueprint 注册 |
| 405 Method Not Allowed | 前端调用方法不符 | 前端 api.post/put 改匹配后端 |
| 500 Internal Error | 后端异常 | 检查 gunicorn/systemd 日志 |
| 401 Unauthorized | Token 过期或无效 | 重新生成 token |
| captcha 验证失败 | 测试时未传验证码 | 用 token 生成绕过验证码 |
