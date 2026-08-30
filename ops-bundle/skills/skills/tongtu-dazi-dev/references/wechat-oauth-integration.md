# 微信网页授权登录集成（公众号H5）

## 完整流程

```
用户点击「微信一键登录」
  → 后端重定向到微信 OAuth 授权页
    → 用户同意授权
      → 微信回调 /api/wechat/callback?code=xxx
        → 后端用 code 换 access_token + openid
          → 获取用户信息（nickname, avatar）
            → 查找/创建用户（wx_openid 字段）
              → 检查是否已绑定手机号
                → 未绑定 → 跳转 /#/bind-phone
                → 已绑定 → 跳转 /#/wx-login → 首页
```

## API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| /api/wechat/login | GET | 跳转微信 OAuth 授权页 |
| /api/wechat/callback | GET | OAuth 回调，登录+创建用户 |
| /api/wechat/config | GET | JS-SDK 配置签名 |
| /api/wechat/bind-phone-simple | POST | 直接绑定手机号（无需验证码） |
| /api/wechat/send-code | POST | 发送短信验证码（测试模式） |
| /api/wechat/bind-phone | POST | 验证码校验绑定手机 |
| /api/wechat/wxphone | POST | 微信手机号快速验证（解密） |

## 配置参数

```python
WX_APPID = 'wxd274e174ddadd4cb'
WX_SECRET = 'cfcb63c13fa5cfbb37316c83f51384a9'
REDIRECT_URI = 'https://dazi.openai2000.cn/api/wechat/callback'
```

## 数据库要求

`user` 表必须包含 `wx_openid` 字段：
```sql
ALTER TABLE `user` ADD wx_openid VARCHAR(64) DEFAULT '' COMMENT '微信openid';
ALTER TABLE `user` ADD INDEX idx_wx_openid (wx_openid);
```

已有的 `phone`、`phone_bound` 字段用于手机号绑定。

## 🔴 踩坑记录

### 1. `wx_openid` 字段不存在 → SQL 1054

**错误**：`pymysql.err.OperationalError: (1054, "Unknown column 'wx_openid' in 'where clause'")`

**修复**：添加字段和索引（见上方 SQL）。

### 2. `cur` 在 `with conn.cursor() as cur:` 块外使用

**错误**：`pymysql.err.OperationalError: while self.nextset()` / `Cursor closed`

**根因**：回调函数中，`SELECT phone_bound` 在 `with` 块结束后使用已关闭的 `cur`。

```python
# ❌ 错误
conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO user ...")
        conn.commit()
    # cur 已关闭！
    cur.execute("SELECT phone_bound FROM user WHERE id=%s", (user_id,))
    u = cur.fetchone()
finally:
    conn.close()

# ✅ 正确：所有 cur 操作在 with 块内
conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO user ...")
        cur.execute("SELECT phone_bound FROM user WHERE id=%s", (user_id,))
        u = cur.fetchone()
        conn.commit()
    # 块外使用变量，不使用 cur
    if u and not u['phone_bound']:
        return redirect(...)
finally:
    conn.close()
```

### 3. `verify_token` 函数不存在

**错误**：`ImportError: cannot import name 'verify_token' from 'app.utils'`

**修复**：使用 `decode_token`（utils.py 中真实存在的函数）：
```python
from app.utils import decode_token
payload = decode_token(token)
```

### 4. 回调 redirect_uri URL 编码

**正确**：用 `urllib.parse.quote(REDIRECT_URI)` 编码完整 URL。生成示例：
```
https://open.weixin.qq.com/connect/oauth2/authorize?appid=xxx&redirect_uri=https%3A//dazi.openai2000.cn/api/wechat/callback&response_type=code&scope=snsapi_userinfo&state=ttdazi#wechat_redirect
```

### 5. JS-SDK 配置签名

`/api/wechat/config` 端点需要：
1. 获取 Official Account `access_token`（`/cgi-bin/token`）
2. 用 `access_token` 获取 `jsapi_ticket`（`/cgi-bin/ticket/getticket`）
3. 用 `jsapi_ticket + noncestr + timestamp + url` 生成 SHA1 签名
4. 返回 `{ appId, timestamp, nonceStr, signature }`

⚠️ 之前的实现错误地使用 `wx_token` 表存储 `access_token`（复杂且易过期）。**正确做法**是每次请求实时获取。

### 6. 🔴 OAuth 回调必须用 v2 token 系统（generate refresh_token）

**错误**：`wechat_login.py` 回调中使用 `create_token(user_id, openid[:16])`（旧版 JWT，无 refresh_token）

**后果**：前端 WxLogin.vue 拿不到 refresh_token → 2小时后 token 过期无法续期 → 自动退出。更严重的是前端 `refreshToken` 变量未定义**直接崩溃白屏**。

**修复**：必须使用 `token_auth.py` 的 v2 系统同时生成 access_token 和 refresh_token，并且两个都通过 URL query 传递给前端。

```python
from app.token_auth import gen_token, gen_refresh_token
from urllib.parse import urlencode

device_id = f'wx_{openid[:8]}'
access_token = gen_token(user_id, device_id)
refresh_tok = gen_refresh_token(user_id, device_id)
params = urlencode({'token': access_token, 'refresh_token': refresh_tok, 'nickname': nickname})
return redirect(f'https://dazi.openai2000.cn/#/wx-login?{params}')
```

同时前端 WxLogin.vue 和 BindPhone.vue 必须从 `route.query.refresh_token` 读取并保存到 localStorage。

📖 完整修复流程见 `references/token-auth-refresh-fix.md`

## 前端页面

### BindPhone.vue

路由：`/#/bind-phone?token=xxx`

用户微信登录后，如果未绑定手机号则自动跳转此页。

### WxLogin.vue

路由：`/#/wx-login?token=xxx&nickname=xxx`

微信 OAuth 回调后跳转的中转页：存储 token 到 localStorage 后跳转首页。

## 微信公众平台配置要求

| 配置 | 位置 | 值 |
|------|------|-----|
| 网页授权域名 | 设置与开发 → 公众号设置 → 功能设置 | `dazi.openai2000.cn` |
| IP白名单 | 设置与开发 → 基本配置 | `42.193.113.230` |
| 手机号验证（可选） | 功能 → 手机号验证 | 需认证服务号 |
