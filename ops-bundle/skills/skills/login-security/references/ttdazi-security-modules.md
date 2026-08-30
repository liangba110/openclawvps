# 同途搭子安全模块实现参考 (Session 2026-07-05)

## 文件清单

| 模块 | 后端文件 | 前端文件 | 数据库表 |
|------|---------|---------|---------|
| v2 Token | `app/token_auth.py` | `api/index.js` (interceptor) | `refresh_token`, `login_log` |
| 审计日志 | `app/audit_log.py` | — | `audit_log` |
| 安全过滤 | `app/safety_filter.py` | — | — |
| 风控管控 | `app/risk_control.py` | — | `risk_blacklist` |
| 验证码 | `app/captcha.py` | Login.vue, Register.vue | 内存+session |
| 账号安全 | `app/security_api.py` | `views/Security.vue` | `refresh_token` |
| 平台审核 | `app/platform_review.py` | `views/VerifyIdentity.vue` | `verify_application`, `sensitive_words`, `reports` |
| 资金安全 | `app/payment_secure.py` | `views/CreateOrder.vue` | — |

## 异常处理配置 (main.py)

```python
app.config['PROPAGATE_EXCEPTIONS'] = False
app.config['DEBUG'] = False

@app.errorhandler(Exception)
def handle_exception(e):
    traceback.print_exc()
    return fail('服务器内部错误，请稍后重试')

@app.errorhandler(404)
def not_found(e):
    return jsonify({'code': 404, 'msg': '接口不存在', 'data': None}), 404
```

## 限流层 (ratelimit.py + captcha.py + risk_control.py)

| 规则 | 实现 | 阈值 |
|------|------|------|
| 登录IP限流 | `@login_ip_limit` decorator | 5次/分钟/IP |
| 密码错误锁定 | `check_pwd_lock`/`record_pwd_fail` | 3次锁定10分钟 |
| 验证码频率 | `check_code_limit` | 单账号60s, 单IP日20条 |
| 图形验证码(人机) | `@require_captcha` | 算术题 `3+7=?` |
| 批量注册 | `check_register_risk()` | 3/天/IP, 2/小时/IP |
| 高频下单 | `check_order_risk()` | 10单/天/用户, 20/IP, 3s间隔 |
| 优惠券防薅 | `FOR UPDATE` 行锁 | 1次/用户, 总量限制 |
| iptables防火墙 | `iptables -A INPUT -p tcp --dport 80` | 并发>100拒绝, 60次/60s封IP |

## 输入输出安全 (safety_filter.py)

```python
sanitize(text)          # XSS: 十种恶意标签+字符转义
sanitize_dict(data)     # 批量过滤指定字段
mask_phone(phone)       # 138****8000
mask_email(email)       # t***@qq.com
paginate(page, size)    # 强制合法化+上限50
paginated_response()    # {list, total, page, page_size, total_pages}
```

敏感词过滤 (platform_review.py):
- 20+ 默认敏感词: 色情/赌博/诈骗/微信/QQ/外挂/收款...
- 手机号检测: `r'\b1[3-9]\d{9}\b'`
- 集成到 `customer_service.py` 发送消息前

## 实名认证流程 (VerifyIdentity.vue)

步骤:
1. 隐私协议弹窗(引用网络安全法/个人信息保护法), 勾选同意
2. 上传身份证正反面 → `POST /api/review/v2/verify/upload-id`
3. 图片校验: 格式(JPG/PNG), 尺寸(≥640×480), 比例(≤2.0), 大小(≤10MB)
4. OCR识别(腾讯云IDCardOCR, 可选, 未配SDK可手动填写)
5. 有效期校验: 解析`YYYY.MM.DD`, 过期直接拦截
6. 提交审核: `POST /api/review/v2/verify/submit`

## 实名认证API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/review/v2/verify/upload-id` | POST | 上传身份证+OCR+校验 |
| `/api/review/v2/verify/submit` | POST | 提交审核 |
| `/api/review/v2/verify/status` | GET | 查询状态 |
| `/api/review/v2/verify/list` | GET | 管理端-待审列表 |
| `/api/review/v2/verify/approve` | POST | 通过 |
| `/api/review/v2/verify/reject` | POST | 拒绝(含原因) |
| `/api/review/v2/reports` | GET | 管理端-举报列表 |
| `/api/review/v2/report/handle` | POST | 处理举报 |
| `/api/review/report` | POST | 用户提交举报 |

## 部署顺序 (安全加固)

1. `main.py`: 关闭DEBUG, 加全局错误处理器
2. `captcha.py`: 图形验证码
3. `ratelimit.py`: 限流+锁定
4. `token_auth.py`: v2令牌+refresh+设备绑定
5. `audit_log.py`: 审计日志表+init
6. `safety_filter.py`: XSS+脱敏+分页
7. `payment_secure.py`: 价格加固+幂等锁
8. `risk_control.py`: 风控+IP封禁
9. `security_api.py`: 设备管理+改密
10. `platform_review.py`: 敏感词+实名+举报
11. `iptables`: 基础防火墙
