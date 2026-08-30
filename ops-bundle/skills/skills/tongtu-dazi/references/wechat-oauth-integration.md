# 微信网页授权集成

## 文件

- 后端：`/opt/ttdazi/backend/app/wechat_login.py`（`wx_bp`, url_prefix=`/api/wechat`）
- 前端：`/opt/ttdazi/frontend/src/views/Login.vue`、`/opt/ttdazi/frontend/src/views/WxLogin.vue`、`/opt/ttdazi/frontend/src/views/BindPhone.vue`

## API 清单

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/wechat/login` | 跳转微信 OAuth 授权页 |
| GET | `/api/wechat/callback` | OAuth 回调：获取用户信息、创建/更新用户、返回 token |
| POST | `/api/wechat/bind-phone-simple` | 微信用户绑定手机号（直接保存，无需验证码） |
| POST | `/api/wechat/bind-phone` | 带验证码校验的绑定方式 |
| POST | `/api/wechat/send-code` | 发送短信验证码（测试模式直接返回） |
| POST | `/api/wechat/wxphone` | 通过微信开放标签获取手机号 |
| GET | `/api/wechat/config` | 获取 JS-SDK 配置（signature） |
| POST | `/api/wechat/jsapi/pay` | 公众号内 JSAPI 支付 |

## 数据库字段

```sql
ALTER TABLE user ADD COLUMN wx_openid VARCHAR(64) DEFAULT '' COMMENT '微信openid';
ALTER TABLE user ADD INDEX idx_wx_openid (wx_openid);
-- phone_bound 字段已存在
```

## OAuth 回调处理

```python
# wechat_login.py wx_callback()
# 流程：获取 code → 换 access_token → 获取用户信息 → 查找/创建用户 → 检查手机绑定
```

关键注意：`cur` 必须在 `with conn.cursor() as cur:` 块内使用，不可在块外引用。

## 前台页面

| 路由 | 组件 | 说明 |
|------|------|------|
| `/login` | Login.vue | PC 默认扫码登录，微信内默认 OAuth 登录 |
| `/wx-login` | WxLogin.vue | 微信授权成功后跳转页，存 token 跳首页 |
| `/bind-phone` | BindPhone.vue | 首次登录时引导绑定手机号 |

## ⚠️ 关键陷阱：PC 浏览器不能用微信 OAuth 登录

### 问题

微信 OAuth 授权（`snsapi_userinfo`）**只能在微信内置浏览器**（X5 内核）中打开。在 PC 浏览器上访问 `https://open.weixin.qq.com/connect/oauth2/authorize?appid=...` 会显示：

> "Oops! Something went wrong:("

用户点击「微信一键登录」按钮后会跳转到这个错误页，无法返回网站。

### 修复方案

在 `Login.vue` 中：

```javascript
// 检测是否在微信浏览器内
const isWechatBrowser = /MicroMessenger/i.test(navigator.userAgent)

// 默认登录模式：PC→扫码登录，微信内→OAuth登录
const loginMode = ref(isWechatBrowser ? 'wechat' : 'scan')
```

**三项防护措施：**

1. **默认登录方式** — PC 默认显示扫码登录（QR code），微信内默认显示微信一键登录
2. **隐藏无用标签** — PC 上 `v-show="isWechatBrowser"` 隐藏「微信登录」标签页
3. **兜底保护** — `wxLogin()` 函数检测非微信浏览器时自动切到扫码登录：

```javascript
function wxLogin() {
  if (!isWechatBrowser) {
    loginMode.value = 'scan'
    createQrCode()
    return
  }
  window.location.href = '/api/wechat/login'
}
```

### 扫码登录流程

PC 端用 `/api/login/scan/create` 创建扫码会话，生成 QR code（使用 `api.qrserver.com` 作为备用 QR 码生成），用户用手机微信扫码后通过 `/api/login/scan/confirm` 确认。前端轮询 `/api/login/scan/status` 获取登录结果。

```javascript
// 扫码登录 API
POST /api/login/scan/create   → 返回 { code, code_url }
GET  /api/login/scan/status   → 返回 { status: 0/1/2, token? }
POST /api/login/scan/confirm  → 手机端确认，返回 token
```

后端模块：`/opt/ttdazi/backend/app/scan_login.py`

## 微信开放平台配置清单

- 网页授权域名：`dazi.openai2000.cn`（已验证）
- JS接口安全域名：`dazi.openai2000.cn`
- IP白名单：`42.193.113.230`（Server A）
- 手机号验证功能：需认证服务号开启
