# WxLogin.vue Bug 链分析（2026-07-18 修复）

## Bug 1: `refreshToken` 未定义变量

**文件**: `frontend/src/views/WxLogin.vue`

原始代码  → 修复后
`refreshToken || ''`  →  `route.query.refresh_token || ''`
`refreshToken` 从未声明 → ES Module 严格模式 → ReferenceError → App.vue onErrorCaptured → 「页面加载出错」

## Bug 2: 后端未生成 refresh_token

**文件**: `backend/app/wechat_login.py`

原始代码使用旧版 `create_token()` 纯 JWT，修复后用 `gen_token()` + `gen_refresh_token()` 并 URL 传递

## Bug 3: WxLogin.vue 未保存用户数据

只保存 token，未调 `/user/profile` → localStorage 中 `user` 为 `'{}'` → CompanionRegister.vue 读 `verify_status` 为 undefined → 重定向到实名认证页

## Bug 4: order/create 强制 companion.status=1

原始 `WHERE id=%s AND status=1` 阻止了 status=0 的搭子续期，修复为 companion_activate 类型放宽限制