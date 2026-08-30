# 备份下载页面中文日期格式

## 问题

Nginx `autoindex` 默认使用 UTC 时间（`18-Jul-2026 21:45`），比北京时间晚8小时，且日期为英文格式。

## 解决方案

放弃 Nginx autoindex，用自定义脚本生成 index.html。

## 脚本位置

**Server B:** `/usr/local/bin/gen_backup_index.sh`

## 脚本内容

```bash
#!/bin/bash
DIR="/data/backups"
INDEX="$DIR/index.html"

cat > "$INDEX" << 'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>备份文件下载</title>
<style>
body{font-family:"PingFang SC",sans-serif;max-width:700px;margin:40px auto;padding:0 20px}
h1{color:#333;font-size:20px}
table{width:100%;border-collapse:collapse;margin-top:16px}
th,td{text-align:left;padding:10px 8px;border-bottom:1px solid #eee}
th{color:#666;font-size:13px}
td{font-size:14px}
a{color:#667eea;text-decoration:none}
.size{color:#999;text-align:right;font-size:13px}
.date{color:#999;font-size:13px}
.footer{color:#ccc;font-size:12px;margin-top:30px;text-align:center}
</style></head>
<body>
<h1>📦 同途搭子备份文件</h1>
<table>
<tr><th>文件名</th><th>修改时间</th><th class="size">大小</th></tr>
HTML

for f in "$DIR"/ttdazi_full_backup_*.tar.gz; do
  [ ! -f "$f" ] && continue
  name=$(basename "$f")
  size=$(ls -lh "$f" | awk '{print $5}')
  mtime=$(date -r "$f" '+%Y-%m-%d %H:%M:%S')
  echo "<tr><td><a href=\"$name\">$name</a></td><td class=\"date\">$mtime</td><td class=\"size\">$size</td></tr>" >> "$INDEX"
done
echo "</table><p class=\"footer\">汇智云科技 · 同途搭子 &copy; 2026</p></body></html>" >> "$INDEX"
```

## Nginx 配置

不再需要 `autoindex on;`，改为 `index index.html;`：

```nginx
location /backup/ {
    alias /data/backups/;
    index index.html;         # 不再用 autoindex
    auth_basic "备份文件下载";
    auth_basic_user_file /etc/nginx/backup-auth/.htpasswd;
    expires off;
    add_header Cache-Control "no-store";
}
```

## 自动更新

`daily_backup.sh` 同步备份后自动执行：
```bash
ssh ubuntu@${SERVER_B} "sudo bash /usr/local/bin/gen_backup_index.sh"
```
