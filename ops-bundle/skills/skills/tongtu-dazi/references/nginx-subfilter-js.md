# Nginx sub_filter 破坏 JavaScript 的调试记录

## 问题

用 `sub_filter` 做登录页文字中文化时，JS 代码被破坏，导致 `fetch('/auth/password-login')` 变 `fetch('/auth/密码-login')`，`input[name=username]` 变 `input[name=用户名]`。

## 根因

`sub_filter` 是**纯文本替换**，不区分 HTML 标签内部 vs `<script>` 标签内部。它扫描响应体所有字节进行替换。

## 破坏模式

| 替换规则 | 被破坏的代码片段 | 后果 |
|---------|----------------|------|
| `'Password' → '密码'` | `fetch('/auth/password-login')`→`fetch('/auth/密码-login')` | 请求404 |
| `'Username' → '用户名'` | `input[name=username]`→`input[name=用户名]` | querySelector失败 |
| `'Next' → '下一步'` | `data.next`→`data.下一步` | 属性访问undefined |

## 安全模式

```nginx
# ✅ 完整HTML标签包围，不会误伤JS
sub_filter '<title>Original Title</title>' '<title>新标题</title>';

# ✅ >文本< 边界（仅匹配HTML标签间的文本）
sub_filter '>Sign in<' '>登录<';

# ✅ 加属性选择器前缀
sub_filter 'placeholder="Username"' 'placeholder="用户名"';
sub_filter 'placeholder="Password"' 'placeholder="密码"';

# ❌ 永远不要做裸文本替换
sub_filter 'Password' '密码';  # BAD
sub_filter 'Username' '用户名';  # BAD
sub_filter 'Sign in' '登录';  # RISKY
```

## 验证

```bash
# 检查JS是否被破坏
curl -sk 'https://domain/login' | grep -A30 '<script>' | grep -E 'password-login|password|username'

# 检查HTML属性
curl -sk 'https://domain/login' | grep -o 'input\[name=[^]]*\]'

# 确认替换后POST仍正常工作
curl -sk -X POST 'https://domain/auth/password-login' \
  -H 'Content-Type: application/json' \
  -d '{"provider":"basic","username":"admin","password":"admin_165623","next":"/"}'
```
