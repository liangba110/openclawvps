# 业务端口内网化统一入口架构 — 完整配置与验证清单

2026-08-04 服务器 A（42.193.113.230，核心数据服务器：主站 Flask 5002 / aiweb 5003 / 支付 5005 / MySQL）实战。目标：业务端口公网完全不可见，全部流量经 443 单一入口（Caddy）按域名/Host 分流。

## 背景（为什么演进到这一版）

1. 初版加固：iptables 来源白名单（5002/5003 仅 B、5005 仅 B+E）+ DROP 兜底 → 验证时发现 **B→A:5002 SYN 无响应，tcpdump 25 秒一个 SYN 都没抓到** → 云安全组在 hypervisor 层拦截（iptables 规则正确也没用）。
2. 中间方案：5005 先绑 127.0.0.1，B/E/D 的 /pay 反代改走 Caddy 443 → 引发 nginx 反代解析坑（见 SKILL.md「Nginx 反代域名解析坑」）。
3. 终版：**所有业务端口绑 127.0.0.1 + 双入口域名 Host 分流**，安全组问题彻底绕开。

## 最终架构

```
                    ┌─────────────────────────┐
 B/E/D ──443──→ A  │  api.openai2000.cn      │
  (SNI+Host)       │   Host=dazi → 5002       │  主站 API（/api /socket.io /uploads）
                   │   Host=aiweb → 5003      │  aiweb API
                   │  兜底 → 5002             │
                   │  pay.openai2000.cn       │
                   │   /pay* → 5005           │  支付页面
                   │   回调(兜底) → 5005       │  微信支付回调
                   └─────────────────────────┘
```

- A 公网只开 22/80/443（iptables + 安全组双保险）
- 5002/5003/5005 全部 bind 127.0.0.1
- B/E/D 的 nginx 反代全部 `proxy_pass https://42.193.113.230:443` + `proxy_ssl_server_name on` + `proxy_ssl_name <域名>`（IP 直写，零 DNS 依赖）

## A 机 Caddyfile（/etc/caddy/Caddyfile）

⚠️ **站点必须声明多 Host**（api/dazi/aiweb/www.ttdazi.xyz 全列）：Caddy 的 site block 按请求 **Host 头精确匹配**，B/E 反代带 `Host: dazi.openai2000.cn` 时若站点只写 `api.openai2000.cn` → 不匹配任何站点 → **返回 HTTP 200 但空 body（content-length: 0），前端数据全丢**。匹配器用 `host`（勿用 `header Host`）。声明多 Host 的副作用是 Caddy 会为 dazi/aiweb 尝试 ACME 证书（解析在别的服务器→获取失败重试），仅日志噪音，不影响服务（反代 SNI 仍走 api/pay 真证书）。

```caddyfile
api.openai2000.cn dazi.openai2000.cn aiweb.openai2000.cn www.ttdazi.xyz {
    @dazi host dazi.openai2000.cn www.ttdazi.xyz
    handle @dazi {
        reverse_proxy 127.0.0.1:5002
    }
    @aiweb host aiweb.openai2000.cn
    handle @aiweb {
        reverse_proxy 127.0.0.1:5003
    }
    handle {
        reverse_proxy 127.0.0.1:5002
    }
}

pay.openai2000.cn {
    handle /pay* {
        reverse_proxy 127.0.0.1:5005
    }
    handle {
        reverse_proxy 127.0.0.1:5005
    }
}

:80 {
    root * /usr/share/caddy
    file_server
}
```

⚠️ `handle_path /pay*` 会 strip 掉 /pay 前缀（支付服务收到 /xxx 缺前缀），必须用 `handle`。

⚠️ 反代链路测试**必须看 body 字节数**（`curl -s ... | wc -c`）而不只是 http_code——空 body 时状态码仍是 200，只看 code 测不出数据丢失（2026-08 用户报"B 站数据不显示"即此坑）。排查顺序：`curl -i` 看 `content-length: 0` → 最小配置（无 handle 直反代）正常、多 Host/handle 分流后空 = 站点 Host 匹配问题。

## 业务端口内网化操作

| 服务 | 启动方式 | 改法 |
|---|---|---|
| 5002 主站 | systemd ttdazi.service，ExecStart `-b 0.0.0.0:5002` | sed 改 `-b 127.0.0.1:5002` → daemon-reload → restart |
| 5003 aiweb | nohup `gunicorn -c gunicorn.conf.py main:app`（非 systemd） | 改 gunicorn.conf.py `bind = '127.0.0.1:5003'` → kill master PID → `sudo /venv/bin/gunicorn -c gunicorn.conf.py main:app -D`（-D 守护模式） |
| 5005 支付 | systemd ttdazi-pay.service，`-b 0.0.0.0:5005` | 同上 sed 改 127.0.0.1 → restart |

- 重启后验证：`ss -tlnp | grep 端口` 显示 `127.0.0.1:` 开头 + `curl http://127.0.0.1:端口/` 有响应（404 也算，说明服务在）+ 公网 `curl http://公网IP:端口` 000
- gunicorn 重启失败看日志：`Connection in use` = 旧进程没杀干净（`ps aux | grep gunicorn` 定位 PID 逐个 kill）

## B/E/D 反代改法（nginx）

B huizhiyunma（主站）：
```nginx
location /api/ {
    proxy_pass https://42.193.113.230:443;      # IP 直写，别写域名
    proxy_ssl_server_name on;
    proxy_ssl_name api.openai2000.cn;           # API 走 api 域名
    proxy_set_header Host $host;                 # Host 保持 dazi → Caddy @dazi → 5002
    ...
}
location ~ ^/pay(/.*)?$ {
    proxy_pass https://42.193.113.230:443/pay$1;  # 带 $1 变量 + IP 直写（无需 resolver）
    proxy_ssl_server_name on;
    proxy_ssl_name pay.openai2000.cn;            # 支付走 pay 域名
    ...
}
```
B aiweb、E 国际站同理（E 的 /api/ /socket.io/ /uploads/ SNI=api，/pay/ SNI=pay）。D 备用站只改 /pay。

## 验证清单（全部必须过）

```bash
# Caddy 分流（A 本机）
curl -sk --resolve api.openai2000.cn:443:127.0.0.1 -H 'Host: dazi.openai2000.cn' https://api.openai2000.cn/api/config
curl -sk --resolve api.openai2000.cn:443:127.0.0.1 -H 'Host: aiweb.openai2000.cn' https://api.openai2000.cn/api/config
curl -sk --resolve pay.openai2000.cn:443:127.0.0.1 https://pay.openai2000.cn/pay/
curl -sk --resolve pay.openai2000.cn:443:127.0.0.1 https://pay.openai2000.cn/wxpay/notify   # 回调入口

# 端到端（注意本机 DNS 缓存可能指向旧服务器，必须 --resolve 强制目标机）
curl -s -o /dev/null -w '%{http_code}' https://dazi.openai2000.cn/api/config        # 200 或 404(接口不存在=链路通)
curl -s -o /dev/null -w '%{http_code}' https://dazi.openai2000.cn/pay/              # 200
curl -s -o /dev/null -w '%{http_code}' --resolve www.ttdazi.xyz:443:185.239.224.191 https://www.ttdazi.xyz/api/config
curl -s -o /dev/null -w '%{http_code}' --resolve www.ttdazi.xyz:443:165.154.224.225 https://www.ttdazi.xyz/pay/   # D 备用

# 公网业务端口必须 000/拒（内网化成功）
for p in 5002 5003 5005; do timeout 5 bash -c "echo > /dev/tcp/42.193.113.230/$p" && echo "$p 仍通(异常)" || echo "$p 已不可达"; done

# WebSocket 升级链路
curl -s -o /dev/null -H 'Connection: Upgrade' -H 'Upgrade: websocket' https://dazi.openai2000.cn/socket.io/?EIO=4&transport=polling
```

## 关键经验

- **安全组拦截 vs iptables**：tcpdump 抓不到 SYN = 安全组层；抓到 = iptables 层。改 iptables 之前先用 tcpdump 定性，避免白折腾。
- **微信回调必须能进 443**：pay.openai2000.cn 公网解析 + Caddy 兜底 handle → 5005。5005 绑 127.0.0.1 不影响（Caddy 回环转发）。
- **改 bind 前想清楚调用方**：全部走 Caddy 后业务端口就只服务本机回环；若有遗漏的直连方（cron、外部服务）会挂，改前 grep 一下有哪些地方引用该端口。
- **iptables 与 Caddy 无冲突**：443 ACCEPT + 业务端口 DROP 并存，Caddy 回环流量走 lo 不受 INPUT 公网规则影响。
