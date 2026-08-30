# 授权 openclaw 建站/建库/跑 PHP（不影响现有站点）

需求：openclaw 能创建自己的网站、数据库、PHP 站点；但不能碰现有 ttdazi 网站程序和数据库。
隔离模式（Server E 实测通过，2026-08-10）。

## 网站
- 专属站点根目录：`/var/www/openclaw-sites/`（chown openclaw:openclaw, 755）
- 专属 nginx 配置目录：`/etc/nginx/openclaw-conf/`（chown openclaw）+ nginx.conf 加 `include /etc/nginx/openclaw-conf/*.conf;` → `nginx -t` 验证
- ⚠️ **绝不把 /etc/nginx/conf.d/ 目录本身交给 openclaw**（目录写权限 = 能删里面的 ttdazi-guard.conf 等 root 文件）。独立子目录才是隔离。

## 数据库（MariaDB）
```sql
CREATE USER 'openclaw'@'localhost' IDENTIFIED BY '<密码>';
GRANT CREATE ON *.* TO 'openclaw'@'localhost';                       -- 可建库
GRANT ALL PRIVILEGES ON `openclaw\_%`.* TO 'openclaw'@'localhost';  -- 只能全权管理 openclaw_* 前缀库
FLUSH PRIVILEGES;
```
- ttdazi 库在 Server A（不同服务器），E 上 openclaw 天然物理隔离；前缀授权再兜一层
- ⚠️ 密码文件放 `/etc/openclaw-db-credentials`（644，www-data 与 openclaw 都可读）。**放 openclaw 家目录 700 会被 php-fpm(www-data) 拒读**（PHP 里 file_get_contents 返回空 → 连接报 using password: NO）

## PHP
- `apt install php-fpm php-mysql`（Ubuntu 24.04 → php8.3-fpm，socket `/run/php/php8.3-fpm.sock`）
- PHP 连库模板：
```php
$db = new mysqli("127.0.0.1", "openclaw", trim(file_get_contents("/etc/openclaw-db-credentials")), "你的库名");
```

## openclaw 发布站点流程（它自己完成，全部有权限）
1. 写站点文件到 `/var/www/openclaw-sites/<site>/`
2. 写 `/etc/nginx/openclaw-conf/<site>.conf`（`listen 8088+` 端口，php location 用 fastcgi_pass unix:/run/php/php8.3-fpm.sock + SCRIPT_FILENAME $document_root$fastcgi_script_name）
3. `sudo nginx -t && sudo systemctl reload nginx`（sudoers 白名单允许）
4. 建库：`mysql -uopenclaw -p$(cat /etc/openclaw-db-credentials) -e "CREATE DATABASE openclaw_xxx"`

## 边界验证清单（交付必测）
- [ ] openclaw 删 `/var/www/ttdazi/index.html` → Permission denied
- [ ] openclaw 删 `/etc/nginx/conf.d/ttdazi-*.conf` → Permission denied
- [ ] openclaw `sudo systemctl stop/restart nginx` → 白名单外被拒
- [ ] openclaw 的 PHP 测试站 `curl 127.0.0.1:8088/` → 输出 PHP 版本 + DB 连接成功
- [ ] 现有站点 www.ttdazi.xyz 200、openclaw gateway health 200
