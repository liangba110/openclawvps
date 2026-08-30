# AdminService 错误状态处理模式

## 问题背景
管理端客服页面 (`AdminService.vue`) 加载时 white screen，点击用户列表时报"页面加载错误，建议刷新"。

## 根因分析
1. **axios 401 跳转错误**: 管理端 token 过期 → 拦截器 `router.push('/login')` → 跳转到用户登录页而非管理端登录页 → 页面报错
2. **缺少加载/错误状态**: 原代码 `catch {}` 静默吞掉错误，无任何用户提示
3. **Nginx 缓存旧 index.html**: 部署后浏览器缓存旧版本，引用的 JS chunk 已改名 → 404 → 加载失败

## 修复方案

### 1. Axios 拦截器 — 区分用户/管理端 401 跳转
```js
// api/index.js — 两处修改 (res.data.code === 401 和 err.response.status === 401)
const isAdmin = location.hash.includes('/admin')
router.push(isAdmin ? '/admin/login' : '/login')
```

### 2. AdminService — 三态渲染 (loading / error / ready)
```vue
<!-- 加载/错误状态 -->
<div v-if="loadError" class="state-box error" @click="init()">
  ⚠️ {{ loadError }}<br><small>点击重试</small>
</div>
<div v-else-if="loading" class="state-box">加载中...</div>

<!-- 正常内容 -->
<template v-else>
  <cs-container>...</cs-container>
</template>
```

### 3. 防御性模板渲染
```vue
<!-- 消息字段空值兜底 -->
<div class="cs-msg-text">{{ m.content || '' }}</div>
<div class="cs-msg-time">{{ m.time || '' }}</div>

<!-- 空消息状态 -->
<div v-if="!messages.length" class="cs-no-msgs">暂无对话记录</div>
```

### 4. Nginx 禁止缓存 index.html
```nginx
location / {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    add_header Pragma "no-cache";
    expires 0;
    try_files $uri $uri/ /index.html;
}
```

## 调试步骤
1. curl API 确认后端正常: `curl -sH "Authorization: Bearer $TOKEN" http://127.0.0.1:5002/api/cs/admin/users`
2. 隐私窗口打开 + F12 Console 看具体错误
3. 检查 `localStorage.getItem('token')` 是否存在且有效
4. `python3.12 -c "from main import app; print('OK')"` 确认后端无导入错误
