# 邮箱注册 → 手机号注册 改造记录（2026-08-04）

用户需求："把邮箱注册改成手机号注册"。改造涉及前后端 4 处 + 3 个隐藏坑。

## 背景（改造前现状）

- 前端已有 `Register.vue`（含"微信注册/手机注册"两个 tab，手机注册表单完整：手机号+昵称+密码+确认密码+算术验证码）
- 独立邮箱注册页 `EmailRegister.vue`（路由 `/email-register`），登录页"邮箱注册"链接指向它
- **后端 `/api/user/register` 被 `return fail('仅支持微信登录')` 挡住**——手机号注册代码完整存在（phone/password/风控/captcha/查重/插入/token）但函数体不可达

## 改动清单

| # | 文件 | 改动 |
|---|------|------|
| 1 | `backend/app/user.py` | `/register` 删除 `return fail('仅支持微信登录')`（该行在函数体第一行，docstring 之前）→ 重启 ttdazi service |
| 2 | `src/router/index.js` | 加 `{ path: '/register', name: 'Register', component: () => import('@/views/Register.vue') }` |
| 3 | `src/views/Login.vue` | "邮箱注册"→"手机注册"；`goRegister()` 从 `router.push('/email-register')` 改 `router.push('/register')` |
| 4 | `src/views/Register.vue` | `const mode = ref('wechat')` → `ref('phone')`（默认手机注册 tab） |

## 坑1：Register.vue 从未接入路由（白屏根因）

**症状**：改完登录页入口后浏览器打开 `/#/register` → 页面空白，`app` innerHTML 只剩 `<!----><!---->`（Vue 注释占位），console 无任何 JS 错误。

**根因**：router 里**从来没有 /register 路由**（只有 `/email-register`、`/companion/register`）。vite 只打包 router 引用的组件——Register.vue 未被引用 → **dist 里根本没有它的 chunk** → 懒加载失败 → 空白。

**排查链**：
```bash
grep -n "path: '/register'" src/router/index.js      # 无结果 = 未接入
ls dist/assets/ | grep -i register                     # 只有 CompanionRegister/EmailRegister = Register 未被引用
# 入口 JS 引用检查（正则要用 [A-Za-z]+- 开头，别用宽松子串匹配）
curl -s https://dazi.openai2000.cn/assets/index-*.js | grep -oE '[A-Za-z]+-[A-Za-z0-9_]+\.js' | grep -i register
```

**通用教训**：`router.push('/xxx')` 指向不存在的路由 = 白屏。改任何入口跳转前先确认目标路由在 router 里注册。

## 坑2：浏览器工具缓存旧 index.html

**症状**：部署新构建后 `browser_navigate` 打开页面仍是旧版（`document.scripts` 显示旧 hash 的 index JS）→ 页面空白或旧内容。curl 验证文件都是新版。

**根因**：browser 工具会话内缓存了 index.html（引用旧入口 JS hash）。hash 路由下往 URL 加 query（`#/register?fresh=1`）**不能**打破 index.html 缓存（query 在 hash 内，不影响文档加载）。

**打破缓存**：
```javascript
// 1. 导航到带 query 参数的 URL（query 在路径上 → 新文档请求 → 绕过缓存）
browser_navigate('https://dazi.openai2000.cn/?fresh=20260804')
// 2. 再跳到目标页
browser_console(() => { location.hash = '#/register'; return 'ok' })
// 3. 验证加载的是新入口 JS
browser_console(() => [...document.scripts].map(s => s.src.split('/').pop()).join(','))
```

## 坑3：手机注册无短信验证

`/user/register` 只有算术验证码（`require_captcha`）+ 风控（`check_register_risk`），**没有短信验证码**。后端 `/api/wechat/send-code` 是测试模式（验证码直接返回在响应里，未接真实短信服务）。手机号+密码即可注册（username 字段存手机号，查重防重复注册）。

如需验证手机号真实性（短信），需接入短信服务商——告知用户此限制，不要默认已具备。

## 验证清单

```bash
# 后端：手机号注册链路（应返回"请输入验证码"= 逻辑启用，非 404/仅微信）
curl -s -X POST http://127.0.0.1:5002/api/user/register -H 'Content-Type: application/json' \
  -d '{"phone":"13900001111","password":"test123456","nickname":"测试"}'
# → {"code":1,"msg":"请输入验证码"}  ✅

# 前端浏览器验证：
# 1. 注册页默认"手机注册" tab（.tab-item.active 文本）
# 2. input[type="tel"] 存在（手机号输入框）
# 3. 登录页链接文本="手机注册"（非"邮箱注册"）

# 双端部署（用户铁律：主站修改必须同步国际站 E）
# B + E 各 rsync --delete --exclude='landing.html' dist/ + chown www-data
```

## 后端 register 完整逻辑（启用后）

- phone + password 必填、密码 ≥6 位
- `check_register_risk()` 注册风控
- `require_captcha(key, answer)` 算术验证码（前端 Register.vue 传 captcha_key/captcha_answer）
- `username = phone` 查重（重复返回"该手机号已注册"）
- INSERT user（username=phone, phone=phone, role=user）
- `create_token(user_id, phone)` 注册即登录
