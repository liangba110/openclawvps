# Nginx 恶意流量分流（蜜罐/惩罚节点）— 完整配置模板

场景：正常用户访问主服务器 E；识别出的恶意流量（爬虫/扫描器/高频攻击）由 E 反代转发到备用服务器 D 承担负载。攻击者无感知（客户端始终 200），D 侧 access log 持续记录恶意请求，E 保持干净。

实测部署：www.ttdazi.xyz（E=185.239.224.191 主，D=165.154.224.225 罚），2026-08-04 验证通过。

## 1. 规则文件 /etc/nginx/conf.d/ttdazi-guard.conf（http 上下文）

```nginx
# 恶意/爬虫 UA 黑名单
map $http_user_agent $bad_ua {
    default 0;
    ~*curl 1;
    ~*wget 1;
    ~*python-requests 1;
    ~*python-urllib 1;
    ~*go-http-client 1;
    ~*zgrab 1;
    ~*masscan 1;
    ~*nmap 1;
    ~*sqlmap 1;
    ~*nikto 1;
    ~*scrapy 1;
    ~*httpclient 1;
    ~*okhttp 1;
    ~*java/ 1;
    ~*phpstorm 1;
    ~*postman 1;
    ~*libwww 1;
    ~*perl 1;
    ~*ruby 1;
    ~*(ahrefs|semrush|mj12bot|dotbot|mauibot|petalbot|bytespider|yisou|dataprovider|rogerbot) 1;
}

# 攻击路径黑名单（纯前端站无 php/wp 等）
map $request_uri $bad_path {
    default 0;
    ~*^/wp-admin 1;
    ~*^/wp-login 1;
    ~*^/wp-content 1;
    ~*xmlrpc 1;
    ~*\.env 1;
    ~*\.git 1;
    ~*\.aws 1;
    ~*\.svn 1;
    ~*^/admin 1;
    ~*phpmyadmin 1;
    ~*^/manager 1;
    ~*^/config\.php 1;
    ~*^/shell 1;
    ~*\.php 1;
    ~*server-status 1;
    ~*^/\. 1;
    ~*\.sql 1;
    ~*\.bak 1;
}

# 全局限流: 单IP超30r/s视为异常(爬虫/攻击)
limit_req_zone $binary_remote_addr zone=ttdazi_guard:10m rate=30r/s;
```

## 2. server 块改动（sites-available/xxx 的 443 server）

```nginx
server {
    listen 443 ssl http2;
    server_name www.example.com;

    # ===== 安全分流 =====
    limit_req zone=ttdazi_guard burst=60 nodelay;
    error_page 503 = @bad_guard;
    if ($bad_ua = "1") { rewrite ^ /__guard__ last; }      # ⚠️ 不要拼 $request_uri！
    if ($bad_path = "1") { rewrite ^ /__guard__ last; }
    ...

    # 恶意流量内部转发点 → 备用服务器
    location = /__guard__ {
        internal;
        proxy_pass https://备用IP$request_uri;             # $request_uri 保留原始URI
        proxy_ssl_verify off;                              # 证书对备用机不验证
        proxy_ssl_server_name on;
        proxy_ssl_name www.example.com;                    # SNI 指定域名
        proxy_set_header Host www.example.com;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30s;
    }
    # 限流超限(异常高频) → 转D
    location @bad_guard {
        proxy_pass https://备用IP$request_uri;
        proxy_ssl_verify off;
        proxy_ssl_server_name on;
        proxy_ssl_name www.example.com;
        proxy_set_header Host www.example.com;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30s;
    }
}
```

## 3. ⚠️ 核心坑：rewrite 拼接 $request_uri 导致循环

错误写法：`if ($bad_ua = "1") { rewrite ^ /__guard__$request_uri last; }`
→ URI 变成 `/__guard__/.env`，**不匹配** `location = /__guard__`（精确匹配只认 `/__guard__` 本身）
→ 落入 SPA 的 `location / { try_files $uri $uri/ /index.html; }`
→ 报错 `rewrite or internal redirection cycle while internally redirecting to "/index.html"`，客户端 500

正确写法：`rewrite ^ /__guard__ last;`（固定 URI 命中精确匹配；`$request_uri` 是只读变量，proxy_pass 里仍拿到原始 URI）

## 4. 验证（必须绕开本机 DNS 缓存）

解析切到新机后，本机 `getent hosts 域名` 可能仍返回旧 IP（systemd-resolved 缓存），curl 全打到旧机 → 误判"分流没生效"。一律用 `--resolve`：

```bash
# 正常 UA → 应只出现在主服务器日志
curl -s --resolve www.example.com:443:主IP -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0' https://www.example.com/
# 恶意 UA → 应出现在备用机 access log（来源=主IP）
curl -s --resolve www.example.com:443:主IP -A 'python-requests/2.31.0' https://www.example.com/
curl -s --resolve www.example.com:443:主IP -A 'curl/7.68.0' https://www.example.com/
# 恶意路径（正常浏览器UA）
curl -s --resolve www.example.com:443:主IP -A 'Mozilla/5.0 Chrome/126' https://www.example.com/.env
curl -s --resolve www.example.com:443:主IP -A 'Mozilla/5.0 Chrome/126' https://www.example.com/wp-login.php
# 确认转发：备用机日志出现来自主IP的请求
ssh 备用机 "grep -c '主IP' /var/log/nginx/access.log"
```

注意：恶意请求客户端看到的也是 200（转发后备用机返回页面），**判断依据是备用机日志**，不是响应码。

## 5. 限流触发测试

burst=60 时 40 并发压测不会触发（全在 burst 容量内）。触发方法：

```bash
seq 1 300 | xargs -P 100 -I {} curl -s -o /dev/null -w '%{http_code}\n' -m 10 \
  --resolve www.example.com:443:主IP -A 'Mozilla/5.0 Chrome/126' https://www.example.com/ | sort | uniq -c
```

预期：客户端全 200；主服务器 error.log 出现 `limiting requests, excess: xx.xxx by zone "ttdazi_guard"`；备用机日志来自主 IP 的请求数增长（= 超限请求被 error_page 转到 @bad_guard）。

## 6. 收尾

- 主备两机 fail2ban jail.local 的 ignoreip 互相包含对方 IP（防 E→D 高频转发被 D 误封），改后 `systemctl restart fail2ban`
- 调整黑名单：误杀正常工具时改 map 规则（如去掉某 UA 行）后 `nginx -t && systemctl reload nginx`
- 备用机 access log 会持续增长（承接恶意流量），留意磁盘
