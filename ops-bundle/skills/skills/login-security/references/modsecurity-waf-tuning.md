# ModSecurity WAF Tuning Reference

Captured from the 2026-07-06 incident where enabling OWASP-style SQL injection rules broke the `/api/captcha/get` endpoint and other binary-data endpoints.

## The Symptom

After deploying ModSecurity WAF on the public-facing Nginx server:

```
GET http://82.157.202.24/api/captcha/get → HTTP 502 (Bad Gateway)
```

Sometimes the response was empty / truncated. The Nginx error log showed nothing. The backend Flask service was healthy (`/api/health` returned 200). Only `/api/captcha/get` and other endpoints that returned base64-encoded images failed.

## Root Cause

The default ModSecurity OWASP SQL injection rule set contains patterns like:

```regex
(?i:\b(select|union|insert|update|delete|drop|alter|truncate|exec|execute|load_file|into\s+outfile|information_schema)\b)
```

The `.*` between keywords makes the rule match **any string containing those keywords**. The captcha image base64 string contains random pixel data that, by sheer probability, eventually matches one of these keywords — ModSecurity blocks the response as a false positive.

Same problem hit `/uploads/` static file serving because binary image data triggered rules.

## The Fix

### Option A — Disable ModSecurity for specific paths (recommended for binary endpoints)

Add to Nginx config (inside the affected `location` blocks):

```nginx
location /api/captcha/ {
    modsecurity off;  # Captcha base64 contains random data
    proxy_pass http://backend;
}
```

### Option B — Tune the rules per endpoint

Keep ModSecurity ON everywhere but add `SecRuleRemoveById` exemptions:

```nginx
SecRule REQUEST_URI "@beginsWith /api/captcha/" \
    "id:10099,phase:1,nolog,pass,ctl:ruleRemoveById=10001"
```

### Option C — Use precision over coverage in rule patterns

The original rules from session 2026-07-06 had overly broad patterns. Replace them with **precision patterns** that require SQL syntax (so they don't false-positive on binary data):

```regex
# BAD — too broad, matches random data
(?i:\b(select|union\s+select|insert\s+into|...)\b)

# BETTER — requires SQL context: keyword followed by SQL syntax
SecRule ARGS "(?i:(\bor\b\s*\d+\s*[=<>]|and\s*\d+\s*[=<>]|union\s+(all\s+)?select|select\s+.*\bfrom\b))" \
    "id:10011,phase:2,deny,status:403,msg:'SQL Injection blocked'"
```

## Recommended Production WAF Rule Set

Tuned rules that protect against real attacks without false positives:

```nginx
SecRuleEngine On
SecRequestBodyAccess On
SecResponseBodyAccess Off
SecDataDir /tmp/modsecurity

# 1. SQL injection — high precision (requires SQL syntax)
SecRule ARGS "(?i:(\bor\b\s*\d+\s*[=<>]|and\s*\d+\s*[=<>]|union\s+(all\s+)?select|select\s+.*\bfrom\b|insert\s+into|delete\s+from|drop\s+(table|database)|update\s+\w+\s+set))" \
    "id:10001,phase:2,deny,status:403,msg:SQL Injection blocked"

# 2. SQL injection — keywords with strict context
SecRule ARGS "(?i:(\binformation_schema|sleep\s*\(|benchmark\s*\(|load_file\s*\(|into\s+outfile))" \
    "id:10002,phase:2,deny,status:403,msg:SQL Keyword blocked"

# 3. XSS — common vectors
SecRule ARGS "(?i:(<script[^>]*>|javascript:|onload\s*=|onerror\s*=|alert\s*\(|prompt\s*\(|confirm\s*\())" \
    "id:10003,phase:2,deny,status:403,msg:XSS blocked"

# 4. Path traversal
SecRule REQUEST_URI|ARGS "(?i:(\.\./|\.\.\\\\|/etc/passwd|/etc/shadow|/proc/self|/boot\.ini))" \
    "id:10004,phase:1,deny,status:403,msg:Path traversal blocked"

# 5. Command injection
SecRule ARGS "(?i:(\bcmd\s*=|command\s*=|system\s*=|exec\s*=|passthru|shell_exec|popen|proc_open|base64_decode|phpinfo))" \
    "id:10005,phase:2,deny,status:403,msg:Command injection blocked"

# 6. Scanner UA strings (12+ known tools)
SecRule REQUEST_HEADERS:User-Agent "(?i:(acunetix|netsparker|sqlmap|nmap|nikto|nessus|openvas|wpscan|burpsuite|appscan|zap|hydra|havij|w3af|dirbuster|gobuster|masscan))" \
    "id:10006,phase:1,deny,status:403,msg:Scanner blocked"

# 7. Body size limit (5MB)
SecRule REQUEST_BODY "@gt 5242880" \
    "id:10007,phase:2,deny,status:413,msg:Request body too large"
```

## Verification Test Suite

After deploying any WAF rules, run these tests:

```bash
# 1. Normal pages still work
curl -s -o /dev/null -w "%{http_code}" http://host/                    # 200
curl -s -o /dev/null -w "%{http_code}" http://host/login             # 200

# 2. API endpoints still respond
curl -s -o /dev/null -w "%{http_code}" http://host/api/health         # 200
curl -s -o /dev/null -w "%{http_code}" http://host/api/captcha/get    # 200
curl -s -o /dev/null -w "%{http_code}" http://host/api/agreement/get?type=user  # 200

# 3. Image content loads (binary data shouldn't trigger rules)
curl -s -o /dev/null -w "%{http_code}" http://host/uploads/avatars/test.png  # 200
curl -s -o /dev/null -w "%{http_code}" http://host/uploads/id_cards/test.jpg  # 200

# 4. Attacks still blocked
curl -s -o /dev/null -w "%{http_code}" "http://host/api/x?id=1%20OR%201=1"  # 403
curl -s -o /dev/null -w "%{http_code}" "http://host/?q=<script>alert(1)</script>"  # 403
curl -s -o /dev/null -w "%{http_code}" -A "sqlmap/1.7" http://host/  # 403
```

If any normal request returns non-200, the rules are too aggressive.

## Nginx + ModSecurity Deployment

```bash
# Install
sudo apt-get install -y libnginx-mod-http-modsecurity

# Enable module (only once per nginx.conf)
echo "load_module modules/ngx_http_modsecurity_module.so;" | sudo tee -a /etc/nginx/nginx.conf

# Configure (one-time)
# /etc/nginx/modsecurity.conf → your rules
# /etc/nginx/conf.d/ttdazi.conf → modsecurity on;

# Test and reload
sudo nginx -t && sudo nginx -s reload

# Verify rules loaded (should print ModSecurity-nginx v...)
sudo tail -f /var/log/nginx/error.log | grep ModSecurity
```

## Audit Logging

```bash
# View ModSecurity audit log
sudo tail -100 /var/log/modsecurity_audit.log

# Find false positives
sudo grep "id:10001\|id:10002\|id:10003" /var/log/modsecurity_audit.log | tail -20

# Each entry shows: rule_id, matched data, request URI
# If you see /api/captcha/ or /uploads/ — false positive, add exemption
```

## Pitfalls

- **Don't put `*` in OWASP patterns without context.** A rule matching `\bSELECT\b` anywhere in request body will fire on every base64 image.
- **ModSecurity is binary-blind.** It can't tell "this base64 string contains an attack" from "this base64 string is a legit captcha image with random pixel data that happens to spell SELECT".
- **Audit `/var/log/modsecurity_audit.log` after enabling WAF.** False positives show up as 403 responses in user testing.
- **Don't enable `SecResponseBodyAccess On` unless you need to scan output.** It doubles memory and latency for no benefit when you only scan input.
- **Tune rules in a staging environment first.** Test against legitimate traffic (especially binary endpoints: captcha, file uploads, image APIs) before deploying to production.