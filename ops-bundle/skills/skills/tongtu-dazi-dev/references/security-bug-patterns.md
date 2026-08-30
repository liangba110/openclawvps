# 安全 Bug 模式修复记录

## 🔴 聊天消息 XSS 漏洞

**发现**：`CustomerService.vue` 的 `v-html="formatMsg(msg.content)"` 直接渲染用户输入，`formatMsg` 仅替换 `\\n` 为 `<br>`，未转义 HTML 标签。

**修复**（双层防护）：
1. **前端**：`formatMsg()` 先对 HTML 特殊字符转义（`&` `<` `>` `"` `'`），再替换换行
2. **后端**：`chat.py send()` 中用 `re.sub(r'<[^>]*>', '', content)` 过滤所有 HTML 标签

```js
// 前端 XSS 防护样板
function formatMsg(text) {
  if (!text) return ''
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
  return escaped.replace(/\n/g, '<br>')
}
```

```python
# 后端 XSS 防护样板
import re
content = re.sub(r'<[^>]*>', '', content)
```

**检查方法**：
```bash
grep -rn 'v-html' /opt/ttdazi/frontend/src/ --include='*.vue'
grep -rn 'innerHTML' /opt/ttdazi/frontend/src/ --include='*.vue' --include='*.js'
```

## 🟡 微信支付私钥权限

**发现**：`apiclient_key.pem` 权限为 666（任何人可读）。

**修复**：`chmod 600`。所有 `.pem`/`.key` 文件都应 600。

**检查**：
```bash
ls -la /opt/ttdazi/payment_service/certs/*.pem
```

## 🟡 SSL 多域名冲突（default_server）

**场景**：Server B 上 `huizhiyunma` 站点配置了 `listen 443 ssl http2 default_server;`，导致 `dazi.openai2000.cn` 的 HTTPS 请求被 `openai2000.cn` 的证书拦截。

**根因**：
- `huizhiyunma` 设为 `default_server` 时，所有无匹配 server_name 的 HTTPS 连接都落到它上面
- `dazi.openai2000.cn` 的 `server_name` 无法触发，因为 Nginx 的 SNI 匹配不上

**修复**：
1. 从 `huizhiyunma` 的 `listen` 中去掉 `default_server`
2. 新域名配置正确的 `server_name` + `ssl_certificate`
3. 不要在新域名配置里加 `default_server`

## 🟡 Nginx 配置写入失败（sudo tee 陷阱）

**场景**：`sudo tee /etc/nginx/sites-enabled/ttdazi > /dev/null << 'NGINX'` 写入后文件仍为旧内容。

**根因**：
- `sites-enabled` 文件写入后可能被系统保护机制恢复
- 或者 `sudo` 的 shell 重定向权限问题
- 文件有 `e`（extent）属性但不影响写入

**可靠方法**：
```bash
# 先写入临时文件
cat > /tmp/ttdazi.conf << 'NGINX'
...
NGINX
# 然后用 sudo mv 替换
sudo mv /tmp/ttdazi.conf /etc/nginx/sites-enabled/ttdazi
sudo nginx -t && sudo nginx -s reload
```

## 🟢 安全头检查清单（完整）

刚部署的新站点必须验证以下响应头：

```bash
curl -sI https://dazi.openai2000.cn/ | grep -iE '
  strict-transport-security|
  x-frame-options|
  x-content-type-options|
  x-xss-protection|
  referrer-policy|
  permissions-policy'
```

### Nginx 安全头配置模板

```nginx
# 用于所有 HTTPS server block
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=(self)" always;
```

### 全局 Nginx 设置

```nginx
# /etc/nginx/nginx.conf 的 http 块中
server_tokens off;                   # 隐藏 Nginx 版本号
```

### 敏感文件保护

```nginx
location ~* \.(pem|key|crt|p12|sql|bak|backup|env|log|tar\.gz|zip)$ {
    deny all;
    return 404;
}
```

### 全站验证脚本

```bash
echo "=== SSL ==="
curl -sI https://dazi.openai2000.cn/ | grep -i 'strict\|frame\|xss\|content\|referrer\|permission'

echo "=== 敏感文件 ==="
for f in test.pem .env backup.zip; do
  code=$(curl -sk -o /dev/null -w '%{http_code}' https://dazi.openai2000.cn/$f)
  echo "$f: $code"  # 应返回 404
done
```

## 🔴 1Panel 覆盖 Nginx 配置（Server B 特有）

**场景**：手动写入 `/etc/nginx/sites-enabled/ttdazi` 的 HTTPS 配置被自动恢复为旧配置（ModSecurity + port 80 + server_name 82.157.202.24）。重复多次 `sudo tee`/`sudo mv` 写入新配置，Nginx 重载后仍恢复旧配置。

**根因**：Server B 安装了 **1Panel** 面板，1Panel 管理 Nginx 配置并定时恢复 sites-enabled 中的文件。新增站点的独立配置文件会被还原。

**修复**：将新域名的 server block **写入 1Panel 不管理的现有文件**（如 `huizhiyunma`），而非创建新文件。`huizhiyunma` 文件是 1Panel 在初始安装时创建的，1Panel 不会恢复它。

**步骤**：
```bash
# 1. 把新站点配置追加到 huizhiyunma 文件末尾
sudo cat /etc/nginx/sites-enabled/huizhiyunma > /tmp/hz_new
# 2. 编辑 /tmp/hz_new 追加新 server block
# 3. 替换
sudo cp /tmp/hz_new /etc/nginx/sites-enabled/huizhiyunma
# 4. 删除独立的配置文件（避免 SSL 冲突）
sudo rm -f /etc/nginx/sites-enabled/ttdazi
# 5. 重载
sudo nginx -t && sudo nginx -s reload
```

**注意**：
- `huizhiyunma` 在 sites-enabled 中是独立副本（非软链接），需直接修改它
- 新配置中**不要加** `default_server`
- 删除旧配置文件后，确认 sites-enabled 中没有 `/bt/` 或 `ttdazi` 等可能冲突的文件

## 🟢 iptables 持久化

Server A 的 iptables 规则重启后丢失。持久化方法：

```bash
sudo iptables-save > /etc/iptables.rules
# 或安装 iptables-persistent
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
```
