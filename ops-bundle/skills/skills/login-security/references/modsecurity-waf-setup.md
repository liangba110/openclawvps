# ModSecurity WAF Setup for Nginx

## Installation

```bash
sudo apt-get install -y libnginx-mod-http-modsecurity
```

## Enable in Server Block

```nginx
server {
    modsecurity on;
    modsecurity_rules_file /etc/nginx/modsecurity.conf;
}
```

## Main Rule Set

File: `/etc/nginx/modsecurity.conf`

```
SecRuleEngine On
SecRequestBodyAccess On
SecResponseBodyAccess Off
SecDataDir /tmp/modsecurity
```

### SQL Injection
Generic: `select|insert into|update set|delete from|drop table|alter table|truncate|exec(|execute(|load_file(|into outfile|information_schema|sleep(|benchmark(|0x[0-9a-f]{8,}`

High Precision: `OR digit =|AND digit =|union select|select ... from`

### XSS
`<script>|javascript:|onload=|onerror=|onclick=|alert(|prompt(|confirm(`

### Path Traversal
`../../../|../../|/etc/passwd|/etc/shadow|/proc/self|/boot.ini`

### Command Injection
`cmd=|command=|exec=|system=|passthru|shell_exec|eval(|assert(|base64_decode|phpinfo`

### Scanner User-Agent Blocking
`acunetix|netsparker|sqlmap|nmap|nikto|nessus|openvas|wpscan|burpsuite|appscan|zap|hydra|medusa|havij|pangolin|w3af|dirbuster|gobuster|masscan|aircrack`

## Logs
- Audit log: `/var/log/modsecurity_audit.log`
- Configure: `SecAuditEngine RelevantOnly`

## Load Module
If not auto-loaded, add to `/etc/nginx/nginx.conf`:
```
load_module modules/ngx_http_modsecurity_module.so;
```

## Verification
```bash
# Test SQL injection
curl -s -o /dev/null -w "%{http_code}" "http://yoursite.com/api/test?id=1%20OR%201=1"
# Expect: 403

# Test normal access
curl -s -o /dev/null -w "%{http_code}" "http://yoursite.com/"
# Expect: 200
```
