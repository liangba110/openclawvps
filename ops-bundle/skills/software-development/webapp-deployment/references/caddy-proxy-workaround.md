# Caddy Reverse Proxy Workaround for Blocked Ports

## Problem

Tencent Cloud security group blocks a new backend port (e.g. `:5003`).
- `curl http://127.0.0.1:5003` works (local)
- `curl http://<public-ip>:5003` times out (cloud firewall)

## Fix: Caddy as Intermediary

Server A already runs Caddy on **port 80/443** (which the security group allows).

1. Add API path routing to Caddy config:
```caddyfile
:80 {
    @api_path { path /api/* }
    handle @api_path {
        reverse_proxy 127.0.0.1:<blocked-port>
    }
    root * /usr/share/caddy
    file_server
}
```

2. Update Nginx on Server B to proxy to Server A's **port 80** instead of blocked port:
```nginx
location /api/ {
    proxy_pass http://<server-a-ip>:80;
}
```

3. Reload both:
```bash
sudo caddy reload --config /etc/caddy/Caddyfile
# On Server B:
sudo systemctl reload nginx
```

## Revert When Security Group Is Fixed

Once the cloud security group rule is added for the direct port:
1. Revert Nginx proxy_pass back to direct port `:<port>`
2. Remove the `@api_path` handle block from Caddy config
3. Reload both

**Don't leave the workaround in place** — it adds an unnecessary hop.
