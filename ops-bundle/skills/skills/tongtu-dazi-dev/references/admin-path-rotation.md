# 管理后台路径每日轮换

## 架构

```
每天 7:00 cron → rotate_admin_path.sh → 更新 DB admin_route 表
       ↓
Hermes cron (daily_admin_push.py) → 调 /api/admin/path → QQ 推送
       ↓
用户打开管理页 → App.vue fetch /api/admin/path → sessionStorage
```

## 轮换脚本

`/opt/ttdazi/rotate_admin_path.sh` — 每天 3:00 ubuntu crontab 执行。
生成 `op-manage-{MMDD}-{6位随机}` 格式路径，写入 `admin_route` 表。

## 前端路由模式（重要！）

前端使用 **`createWebHashHistory()`**（hash 路由模式），所有管理后台 URL 必须带 `#/` 前缀：

```
✅ 正确: https://dazi.openai2000.cn/#/op-xxx/login
❌ 错误: https://dazi.openai2000.cn/op-xxx/login
❌ 错误: https://dazi.openai2000.cn/#op-xxx/login  （漏了反斜杠）
```

hash 路由模式下，`/op-xxx/login` 作为常规 URL 路径不会被 SPA 识别——Nginx 会 fallback 到 index.html 然后 SPA 显示首页。

## 🔴 轮换脚本已知 Bug（每次手动必须修复）

### Bug 1: `const defaultPrefix` 遗漏

rotate 脚本的 sed 只替换 URL 路径中的旧路径（`/$OLD_PATH/` 模式），但 `router/index.js` 第36行有：

```javascript
const defaultPrefix = 'op-xxx'
```

这是一个源代码级的 `sessionStorage` fallback 常量。sed 找不到它（因为它不在 URL 路径引用中），所以每次旋转后这行仍然是旧值。

**后果**：新用户首次访问（`sessionStorage` 为空）时，路由表用 `defaultPrefix` 做前缀，路径不匹配 → Vue Router 找不到路由 → 显示首页而非管理登录页。

**修复方法**（每次旋转后必须执行）：

```bash
# 1. 手动更新 defaultPrefix（router/index.js 中的常量）
sed -i "s|const defaultPrefix = 'op-旧路径'|const defaultPrefix = 'op-新路径'|g" \
  /opt/ttdazi/frontend/src/router/index.js

# 2. 同时更新 rotate 脚本的 fallback 值，确保下次旋转正确
sed -i "s|echo \"op-旧路径\"|echo \"op-新路径\"|g" \
  /opt/ttdazi/rotate_admin_path.sh

# 3. 重构建 + 部署
cd /opt/ttdazi/frontend && npm run build && bash /opt/ttdazi/deploy.sh
```

**根本修复（待实施）**：在 rotate 脚本的 sed 命令中追加匹配 `const defaultPrefix` 的正则：
```bash
sed -i "s|defaultPrefix = '$OLD_PATH'|defaultPrefix = '$NEW_PATH'|g" \
  /opt/ttdazi/frontend/src/router/index.js
```

### Bug 2: `CURRENT_PATH` 追踪失效

脚本顶部：
```bash
OLD_PATH=$(grep "^CURRENT_PATH" /opt/ttdazi/rotate_admin_path.sh 2>/dev/null \
  | head -1 | cut -d= -f2 || echo "op-manage-7x2d9")
```

- `grep "^CURRENT_PATH"` 查找脚本中 `CURRENT_PATH=xxx` 的行——但脚本本身不持久化此变量
- fallback `op-manage-7x2d9` 是硬编码的初始值，不是上一次旋转后的值
- 当 fallback 被触发时，sed 模式基于**错误的旧路径**去替换，导致部分引用漏替换

**修复**：每次旋转后在脚本中更新 fallback 值：
```bash
sed -i 's|echo "op-旧路径"|echo "op-新路径"|g' /opt/ttdazi/rotate_admin_path.sh
```

**2026-07-16 手动旋转记录**：旧路径 `op-ztHWaT-0706` → 新路径 `op-1MQujA-0716`。缺陷：
- `defaultPrefix` 未被 rotate 脚本替换，手动 `sed -i` 修复
- rotate 脚本的 `CURRENT_PATH` fallback 已随手动替换更新为 `op-1MQujA-0716`
- 旧 hash 文件 `index-IfjKIlos.js` 残留于 Server B，`rsync --delete` 后清理

### Bug 3: deploy.sh 超时中断

rotate 脚本内部调用 `bash deploy.sh`，但同步到 Server B 的 rsync 可能因终端超时(30s)被截断。Server B 上残留旧 hash 的 index-*.js 文件。

**症状**：脚本输出 `✓ built in Xs`（构建成功），但 Server B 仍是旧文件。

**排查**：
```bash
# 看 Server B 上实际部署了什么路径
ssh ubuntu@82.157.202.24 \
  "grep 'op-' /home/ubuntu/ttdazi-frontend/assets/index-*.js | sort -u"
# 看数据库中的路径
MYSQL_PWD='huizhiyun2026' mysql -h127.0.0.1 -uroot huizhiyun \
  -e "SELECT * FROM admin_route WHERE id=1;"
```

**修复**：脚本执行完后，单独补跑部署：
```bash
bash /opt/ttdazi/deploy.sh
```

## 验证新路径是否可用

```bash
# 1. 后端 API 返回正确路径
curl -s https://dazi.openai2000.cn/api/admin/path | python3 -m json.tool
# 期望: {"code":0,"data":{"path":"op-新路径", ...}}

# 2. 前端页面可访问（注意 hash 路由格式！）
# curl 检查服务端是否返回 index.html（200 OK 不代表 SPA 路由正常）
curl -s -o /dev/null -w "%{http_code}" "https://dazi.openai2000.cn/op-新路径/login"

# 3. 浏览器验证（必须！curl 验证不够）
# 在浏览器中打开 https://dazi.openai2000.cn/#/op-新路径/login
# 确认显示管理登录页（带账号/密码/验证码输入框），不是首页热门搭子
```

### ⚠️ curl 与浏览器的差异

curl 访问 `/op-xxx/login` 返回 200 不代表管理后台正常：
- curl 只是得到 Nginx 返回的 `index.html`（200 OK）
- 但 SPA 加载后可能找不到对应路由，显示的是首页
- **必须用真正的浏览器打开 `/#/op-xxx/login` 验证**

## 前端动态路由

- 路径存在 `sessionStorage.getItem('admin_route_path')` 中
- 路由在 `router/index.js` 通过 `createAdminRoutes(prefix)` 动态生成
- 路径变化时 `window.location.reload()` 刷新全应用
- `router.beforeEach` 守卫把旧 `/admin/` 路径重定向到当前路径

## 🔴 每日推送脚本陷阱

`/home/ubuntu/.hermes/scripts/daily_admin_push.py`（Hermes cron, 7:00）推送新路径。

⚠️ **必须用 127.0.0.1:5002 而不是 82.157.202.24**：
```python
# ✅ 正确
req = urllib.request.Request('http://127.0.0.1:5002/api/admin/path')
# ❌ 错误 — Server B Nginx huizhiyunma 站点域名白名单拦截 IP 请求返回 403
req = urllib.request.Request('http://82.157.202.24/api/admin/path')
```

Server B 的 `huizhiyunma` Nginx 配置监听 80/443 且只接受 `openai2000.cn` 域名，直接走 IP 访问会被 403 拦截。
