# 微信网页授权登录（公众号OAuth）

## 架构

用户在微信内打开 dazi.openai2000.cn
  → 跳转 https://open.weixin.qq.com/connect/oauth2/authorize?...
  → 用户授权 → 回调到 /api/wechat/callback
  → 后端获取 access_token + 用户信息（nickname, headimgurl）
  → 查找/创建用户 → 生成 token → 跳转回前端

## 配置清单

### 微信公众平台设置

| 项目 | 值 |
|------|------|
| 公众号 APPID | wxd274e174ddadd4cb |
| AppSecret | 在 mp.weixin.qq.com → 设置与开发 → 基本配置 查看 |
| 网页授权域名 | dazi.openai2000.cn（需下载 MP_verify_xxx.txt 上传到网站根目录） |
| JSAPI支付回调域名 | dazi.openai2000.cn |
| IP白名单 | 42.193.113.230（Server A） |

### 域名验证文件上传

每次在公众号后台添加新域名时，会要求上传 MP_verify_*.txt 文件：

```bash
# dazi.openai2000.cn 根目录
scp MP_verify_xxx.txt ubuntu@82.157.202.24:/home/ubuntu/ttdazi-frontend/
# openai2000.cn 根目录（如需）
scp MP_verify_xxx.txt ubuntu@82.157.202.24:/data/web/huizhiyunma/frontend/dist/
```

验证：`https://dazi.openai2000.cn/MP_verify_xxx.txt`

## 后端文件

- `/opt/ttdazi/backend/app/wechat_login.py` — OAuth + JSAPI支付 + wx.config
- 在 main.py 注册 `wx_bp`（url_prefix=/api/wechat）

## OAuth 回调后的手机号绑定

OAuth 成功后自动检查 `phone_bound`，未绑定则跳转 `/bind-phone`。

### 简化绑定（当前正在使用）

无需短信验证码，用户手动输入手机号直接保存。提供「跳过」选项。

```
微信授权登录 → 未绑定手机
  → 跳转 /bind-phone?token=xxx
  → 输入手机号 → 确认绑定 → POST /api/wechat/bind-phone-simple → 跳转首页
  → 或跳过 → 直接进入首页
```

关键点：
- token 通过 URL query 传递（非仅靠 localStorage）
- 校验手机号是否已被绑定
- 不校验手机号真实性，仅做格式检查（11位数字）
- 前端用 alert() 提示，不使用 Vue 插件

### 短信验证码（API 已实现但未启用）

```json
POST /api/wechat/send-code → {"code":0,"data":{"code":"728868"}}
POST /api/wechat/bind-phone → 校验 token + 验证码 → 绑定
```

### 微信手机号快速验证（需认证服务号，未启用）

1. 微信公众平台开启「功能 → 手机号验证」
2. 前端 WeChat JS-SDK `wx.getPhoneNumber` 获取加密 code
3. 后端 POST 到 `https://api.weixin.qq.com/wxa/business/getuserphonenumber` 解密

API `POST /api/wechat/wxphone` 已实现，等待认证后可用。

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/wechat/login | GET | 跳转微信授权页 |
| /api/wechat/callback | GET | 微信授权回调（自动注册/登录） |
| /api/wechat/bind-phone-simple | POST | 简化绑定手机号（无验证码，需 token + phone） |
| /api/wechat/bind-phone | POST | 短信验证码绑定（已实现未使用） |
| /api/wechat/send-code | POST | 发送验证码（测试模式） |
| /api/wechat/wxphone | POST | 微信快速验证（需认证，未启用） |
| /api/wechat/jsapi/pay | POST | JSAPI 支付（需 openid） |
| /api/wechat/config | GET | JS-SDK 配置签名 |

## 前端

### Login.vue

仅保留微信登录按钮，移除密码/验证码登录。按钮使用微信 SVG 双气泡图标。

### BindPhone.vue

绑定页（路由 `/bind-phone`），接收 URL token 参数：
- 手机号输入框 + 确认绑定按钮
- 「暂不绑定，跳过」链接
- alert() 消息提示

### WxLogin.vue

OAuth 成功回调页（路由 `/wx-login`），从 URL 取 token 存 localStorage，1.5 秒后跳首页。

## 数据库

```sql
ALTER TABLE `user` ADD COLUMN `wx_openid` VARCHAR(64) DEFAULT '' COMMENT '微信openid';
ALTER TABLE `user` ADD INDEX `idx_wx_openid` (`wx_openid`);

CREATE TABLE IF NOT EXISTS wx_token (
  id INT PRIMARY KEY DEFAULT 1,
  access_token VARCHAR(512) NOT NULL,
  expires_at DATETIME NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 常见问题

| 问题 | 原因 | 修复 |
|------|------|------|
| 提示「微信错误」跳回首页 | 数据库 user 表缺 wx_openid 字段 | `ALTER TABLE user ADD wx_openid VARCHAR(64)` |
| 提示「登录已过期」 | token 无效或过期 | 重新走 OAuth 流程 |
| 微信提示「不安全」 | SSL 证书错配（server_name 不匹配） | 正确配置 server_name + ssl_certificate |
| 提示「服务器内部错误」 | cursor 在 with 块外被使用 | 将所有 cur 操作移到 with 块内 |
| 回调返回空/白屏 | cur 已关闭导致 500 | 同上 |

## 🔴 cursor 作用域陷阱

OAuth 回调函数中，`phone_bound` 检查查询必须放在 `with conn.cursor() as cur:` 块**内部**。块结束后 `cur` 被自动关闭，再调用 `cur.execute()` 会报 `while self.nextset()` 或 `Cursor closed`。

```python
# ❌ 错误
with conn.cursor() as cur:
    cur.execute("INSERT INTO user ...")
    conn.commit()
# cur 已关闭！下面这行会报错
cur.execute("SELECT phone_bound FROM user ...")
u = cur.fetchone()

# ✅ 正确
with conn.cursor() as cur:
    cur.execute("INSERT INTO user ...")
    cur.execute("SELECT phone_bound FROM user ...")  # 在块内查询
    u = cur.fetchone()
    conn.commit()
# 块外使用变量而不是 cur
if u and not u['phone_bound']:
    return redirect(...)
```
