# 安全模块参考（2026-07-05 会话新增 + 扩展）

## 1. Token 安全系统 (`app/token_auth.py`)

### v2 Token 格式
```
v2.{user_id}.{timestamp}.{ttl}.{sha256_signature[:24]}.{device_id}
```
- 30 分钟 TTL（ACCESS_TOKEN_TTL=1800）
- 签名使用 `hashlib.sha256`
- `login_required` 装饰器在 `app/utils.py` 中同时支持新旧两种格式

### refresh_token
- 48 位随机字符串，7 天有效期
- 存入 `refresh_token` 表，每用户最多 5 个设备
- `POST /api/user/refresh` — 用 refresh_token 换取新的 access_token
- 前端 axios 拦截器在 401 时自动刷新（`api/index.js`）

### 服务端登出
```python
@user_bp.route('/logout', methods=['POST'])
def logout():
    revoke_all_sessions(user['id'])  # DELETE FROM refresh_token
```

### 设备绑定与异地检测
- `get_device_id()` — 读取 `X-Device-Id` 头，降级为 UA+IP MD5
- `check_anomaly(user_id, device_id, ip)` — 对比历史登录 city，差异则标记告警
- 登录成功时返回 `anomaly_warn`，前端 `safeToast` 显示

### 表结构
```sql
CREATE TABLE refresh_token (
    user_id INT, token VARCHAR(255), device_id VARCHAR(100),
    ip VARCHAR(45), expires_at DATETIME
);
CREATE TABLE login_log (
    user_id INT, ip VARCHAR(45), device_id VARCHAR(100),
    user_agent VARCHAR(500), city VARCHAR(50),
    is_new_device TINYINT, is_new_city TINYINT
);
```

## 2. 资金安全模块 (`app/payment_secure.py`)

### DB 价格防篡改
```python
db_price, err = get_db_price(companion_id, service_type)
amount = db_price['price']  # 忽略前端传的 amount
```
- 从 `companion_game` 表读取真实价格
- `price_map = {1: price_1h, 2: price_2h, 3: price_night}`

### 幂等锁（@idempotent 装饰器）
```python
@idempotent('order')
def create():
    pass  # 30 秒内相同 idempotent_key 返回 409
```
- 前端自动生成 `idempotent_key: 'order_' + Date.now() + '_' + random`
- 装饰器维护线程安全 `_locks` 字典，30 秒过期

### 接口签名（require_sign 装饰器）
- 签名算法：`md5(sorted(data, key=value) + SECRET)`
- `PAYMENT_SECRET = 'ttdazi_payment_2026_secure'`

## 3. 审计日志系统 (`app/audit_log.py`)

`init_audit_table()` 在 Flask 启动时调用，创建 `audit_log` + `refresh_token` + `login_log` 三张表。

```python
from app.audit_log import log as audit_log
audit_log(user_id, 'login_success', detail={'username': username})
audit_log(0, 'login_fail', detail={'username': '138xxxx', 'reason': '用户不存在'})
```

字段：`user_id, action, target_type, target_id, ip, user_agent, detail(JSON), status, created_at`

## 4. 安全过滤模块 (`app/safety_filter.py`)

### XSS 过滤
```python
nickname = sanitize(data.get('nickname', ''), max_len=30)
data = sanitize_dict(data, fields=['nickname', 'intro', 'city'])
```
- `sanitize` 替换 <>"' 为全角字符，移除 script/iframe/onclick 等标签
- `sanitize_dict` 默认过滤：nickname/intro/remark/content/message/name/title/reply

### 脱敏
```python
mask_phone('13800138000')  # → '138****8000'
mask_email('test@qq.com')  # → 't***t@qq.com'
```

### 强制分页
```python
page, page_size, offset = paginate(request.args.get('page'), request.args.get('page_size', 10))
return success(paginated_response(items, total, page, page_size))
# √ `paginate` 限制 `max_size=50`
# √ `paginated_response` 返回 `{list, total, page, page_size, total_pages}`
```

## 5. 风控管控系统 (`app/risk_control.py`) — 2026-07-05 新增

### 批量注册防护
```python
from app.risk_control import check_register_risk
ok, msg = check_register_risk()  # 在 register 入口调用
```
- 内存计数：单 IP 每天 ≤3，每小时 ≤2
- 超限则 `ban_ip()` 封禁 24 小时 + 写入 Nginx 黑名单

### 高频下单防护
```python
from app.risk_control import check_order_risk
ok, msg = check_order_risk(user_id)  # 在 order/create 入口调用
```
- 数据库查询：单用户每天 ≤10 单，单 IP 每天 ≤20 单
- 内存间隔：同一用户两次下单间隔 ≥3 秒
- 超阈值 → `ban_ip()` 封禁 2 小时 + Nginx 同步

### IP 封禁（Nginx 层联动）
```python
ban_ip('1.2.3.4', '批量注册', minutes=1440)
# 1. 写入 risk_blacklist 表（持久化）
# 2. SSH 到 Server B → /etc/nginx/ip_blacklist.conf 追加
# 3. nginx -s reload → 实时生效，返回 403
```

### 优惠券防薅
```python
from app.risk_control import check_coupon_limit
ok, msg = check_coupon_limit(user_id, coupon_id)
```
- `FOR UPDATE` 行锁防止并发超领

### risk_blacklist 表
```sql
CREATE TABLE risk_blacklist (
    ip VARCHAR(45) NOT NULL UNIQUE,
    reason VARCHAR(200),
    expires_at DATETIME,
    created_at TIMESTAMP
);
```

### 限流配置 (`app/ratelimit.py`)
```python
@login_ip_limit  # IP 1分钟5次登录
check_pwd_lock(username)     # 密码错误3次锁定10分钟
check_code_limit(phone, ip)  # 单账号60s间隔 + 单IP日20条
```

## 6. 人机验证 CAPTCHA (`app/captcha.py`) — 2026-07-05 新增

- `GET /api/captcha/get` — 返回 base64 算术图片 + key
- `require_captcha(key, answer)` — 校验函数，登录/注册入口调用

> ⚠️ Pillow 安装：`sudo apt install -y python3-pil`（不能用 pip，PEP 668 限制）

## 7. 账号安全模块 (`app/security_api.py`) — 2026-07-05 新增

### 设备管理
```
GET  /api/security/devices              # 设备列表
POST /api/security/device/revoke         # {device_id} 下线 / {all:true} 全部下线
```

### 修改密码（需邮箱验证）
```
POST /api/security/change-password
{old_password, new_password, confirm_password, code}
```
- 验证邮箱验证码 → 验证旧密码 → 改密 → 销毁所有 refresh_token

## 8. 平台审核系统 (`app/platform_review.py`) — 2026-07-05 新增

### 实名认证 API（路由前缀 `/api/review/v2`）
```
POST /verify/upload-id     # 上传身份证 + 图片校验 + OCR
POST /verify/submit        # 提交认证
GET  /verify/status        # 查询认证状态
GET  /verify/list          # 管理端待审核列表
POST /verify/approve       # 管理端通过
POST /verify/reject        # 管理端拒绝
```

### 图片合规校验
| 校验项 | 规则 |
|--------|------|
| 格式 | JPG/PNG，文件头校验 |
| 尺寸 | ≥640×480 |
| 比例 | 宽高比 ≤2.0（防歪斜翻拍） |
| 大小 | ≤10MB |

### OCR 识别
- 集成腾讯云 `IDCardOCR`（可选），从 `TENCENT_SECRET_ID/KEY` 读取
- 自动解析有效期 `YYYY.MM.DD`，过期拦截；"长期"标识 ✅

### 敏感词过滤
```python
from app.platform_review import check_content, require_content_clean
ok, reason = check_content(text)
```
- 20+ 默认敏感词，正则检测手机号
- 集成在聊天/陪玩申请/简介等入口

### 举报投诉
```
POST /api/review/v2/report     # {target_type, target_id, reason}
GET  /api/review/v2/reports    # 管理端举报列表
POST /api/review/v2/report/handle  # 处理
```

### 审核表
```sql
CREATE TABLE verify_application (user_id, real_name, id_card, status);
CREATE TABLE sensitive_words (word VARCHAR(100) UNIQUE);
CREATE TABLE reports (reporter_id, target_type, target_id, status);
CREATE TABLE rank_verify (companion_id, game_id, screenshot_url, claimed_rank, status);
```

## 9. Nginx 层 WAF — 2026-07-05 新增

### 限流配置
```
api_limit:  30r/s, burst=50     — 全站 API 限流
login_limit: 5r/m, burst=3      — 登录/验证码更严格
conn_limit: 50                  — 单 IP 并发连接
```

### IP 黑名单（动态封禁）
```nginx
geo $blacklist { default 0; include /etc/nginx/ip_blacklist.conf; }
if ($blacklist) { return 403; }
```

### 管理命令
```bash
ip_ban ban 1.2.3.4   # 封禁
ip_ban unban 1.2.3.4 # 解封
ip_ban list          # 查看
```

## 10. 全局异常拦截（`main.py`）
```python
@app.errorhandler(Exception) → return fail('服务器内部错误，请稍后重试')
@app.errorhandler(404) → jsonify({code:404, msg:'接口不存在'}), 404
@app.errorhandler(405) → jsonify({code:405, msg:'请求方法不允许'}), 405
```

## 关键陷阱

### ⚠️ Blueprint 名称冲突
`app/review.py` 和 `app/platform_review.py` 都定义了 `review_bp`，同一 URL 前缀 `/api/review`。
→ 新得用前缀 `/api/review/v2`，并且 import 时用别名。

### ⚠️ verify_codes 表用 phone 列存邮箱
`send_email_code()` 将 `email` 写入 `verify_codes.phone` 字段。查询时用 `WHERE phone=%s`。

### ⚠️ init_audit_table() 必须在 create_app() 中调用
在 `app.register_blueprint(audit_log_bp)` 之后立即调用。

### ⚠️ 风控 IP 来源
必须用 `X-Forwarded-For` 而非 `request.remote_addr`（后者永远是 Server A 的 IP）。
