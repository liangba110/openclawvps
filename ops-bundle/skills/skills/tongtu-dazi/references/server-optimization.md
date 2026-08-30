# Server Optimization Notes

## iptables Firewall (Server B)

```bash
# 并发限制：单IP连接>100拒绝
sudo iptables -A INPUT -p tcp --dport 80 -m connlimit --connlimit-above 100 -j REJECT

# 频率限制：60秒内60次请求封IP
sudo iptables -A INPUT -p tcp --dport 80 -m recent --name badip --set
sudo iptables -A INPUT -p tcp --dport 80 -m recent --name badip --update --seconds 60 --hitcount 60 -j DROP
```

> ⚠️ 重启后 iptables 规则丢失。持久化需安装 `iptables-persistent` 或写入 rc.local。

## Nginx 限流（全局 nginx.conf）

```nginx
limit_req_zone $binary_remote_addr zone=waf:10m rate=30r/s;
limit_conn_zone $binary_remote_addr zone=addr:10m;
```
Server block 内：
```nginx
limit_req zone=waf burst=50 nodelay;
limit_conn addr 50;
if ($http_user_agent ~* (curl|wget|python-requests|scrapy|sqlmap)) { return 444; }
```

## Gzip (Nginx)
```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;
gzip_min_length 256;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 4;
```
Must be at **server level** (not inside `location /`) to cover `/api/` responses.

## Nginx Cache Prevention for SPA
```nginx
location / {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    expires 0;
    try_files $uri $uri/ /index.html;
}
```
Prevents stale index.html from loading old chunk files after rebuild.

## Gunicorn Log Level
```systemd
ExecStart=... gunicorn ... --log-level warning --timeout 120
```
Reduces disk I/O in production.

## Monitoring Cron
```bash
# /opt/ttdazi/monitor.sh — runs every minute via crontab
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
MEM=$(free | grep Mem | awk '{printf "%.0f", $3/$2*100}')
CONNS=$(ss -tn state established | wc -l)
echo "$(date) CPU:${CPU}% MEM:${MEM}% CONNS:$CONNS" >> /var/log/ttdazi_monitor.log
```

## Deploy Command
```bash
cd /opt/ttdazi/frontend && npm run build && bash /opt/ttdazi/deploy.sh
```
Backend-only: `sudo systemctl restart ttdazi`
