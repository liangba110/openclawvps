# Captcha 调试与自动化测试

## 验证码机制

后端使用 PIL 生成数学题图片存入 `captcha_log` 表：

```python
# captcha.py 三种题型
text = f'{a} + {b} = ?'
text = f'{max(a,b)} - {min(a,b)} = ?'  
text = f'{a} × {b} = ?'
```

API 响应（前端收到，自动解包后是 `data` 对象）：
```json
{"code": 0, "data": {"image": "data:image/png;base64,...", "key": "xxx"}}
```

**答案仅存数据库，不返回前端。** 表结构：
```sql
captcha_log (`key`, answer, expires_at, used, created_at)
```

## 自动化测试：从 DB 查答案

通过 API 获取验证码后，直接从数据库读取答案：

```bash
# 1. 获取 captcha
CAPTCHA=$(curl -s "http://127.0.0.1:5002/api/captcha/get")
KEY=$(echo "$CAPTCHA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('key',''))")

# 2. 查答案（注意 api 返回的 key 在 captcha_log.key 字段匹配）
ANSWER=$(MYSQL_PWD='huizhiyun2026' mysql -h127.0.0.1 -uroot huizhiyun \
  -e "SELECT answer FROM captcha_log WHERE \`key\`='$KEY' ORDER BY created_at DESC LIMIT 1;" 2>/dev/null | tail -1)

# 3. 用答案登录
curl -s "http://127.0.0.1:5002/api/user/login" -X POST \
  -H "Content-Type: application/json" \
  -d "{\"phone\":\"13800138000\",\"password\":\"123456\",\"captcha_key\":\"$KEY\",\"captcha_answer\":\"$ANSWER\"}"
```

## 常见问题

### captcha_key 为空

如果 KEY 取不到值，检查 response 解包层级：
- 后端直接返回：`{"code":0, "data":{"image":"...", "key":"xxx"}}`
- 前端 api 拦截器自动返回 `data.data` = `{"image":"...", "key":"xxx"}`
- 但 curl 测试时需手动取 `d.get('data',{}).get('key','')`

### answer 为空

- dev 模式不返回 answer（安全设计）
- 必须从 MySQL `captcha_log` 表查询
- 注意 `ORDER BY created_at DESC LIMIT 1` 取最新一条

### 验证码过期

- `captcha_log.expires_at` 是 Unix timestamp
- 默认有效期：60秒
- 过期后自动被清理脚本删除

### 跳过验证码（开发/测试用）

推荐方式：直接从后端生成 token 绕过登录流程：

```python
python3 -c "
import sys; sys.path.insert(0, '/opt/ttdazi/backend')
from app.utils import create_token
print(create_token(10001, '13800138000'))
"
```
