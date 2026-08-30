#!/bin/bash
# 通用服务器安全扫描脚本（2026-08 实测 4 台机）
# 用法：scp 到目标机 /tmp 后 sudo bash security-scan.sh
echo "===== $(hostname) $(hostname -I 2>/dev/null) ====="
echo "--- 1.fail2ban ---"
systemctl is-active fail2ban 2>/dev/null || echo "fail2ban 未运行!"
sudo fail2ban-client status 2>/dev/null | head -8
echo "--- 2.SSH配置 ---"
sudo sshd -T 2>/dev/null | grep -iE '^(passwordauthentication|pubkeyauthentication|permitrootlogin|port) '
echo "--- 3.监听端口(公网0.0.0.0需另行公网实测) ---"
sudo ss -tlnp 2>/dev/null | awk '{print $4, $6}' | sort -u | head -30
echo "--- 4.待更新包 ---"
apt list --upgradable 2>/dev/null | grep -c upgradable || echo 0
ls /var/run/reboot-required 2>/dev/null && echo "!!! REBOOT_REQUIRED(需用户手动重启)"
echo "--- 5.爆破统计(最近Failed) ---"
sudo grep 'Failed password' /var/log/auth.log 2>/dev/null | grep -oE 'from [0-9.]+' | sort | uniq -c | sort -rn | head -5
echo "--- 6.挖矿进程(注意[kdevtmpfs]带方括号=内核线程正常) ---"
ps aux | grep -iE 'xmrig|minerd|kdevtmpfs|kinsing|cryptonight' | grep -v grep | head -5 || echo "无"
echo "--- 7.UID=0用户 ---"
awk -F: '$3==0{print $1}' /etc/passwd
echo "--- 8.近期新增用户 ---"
sudo grep -E 'useradd|groupadd|new user' /var/log/auth.log 2>/dev/null | tail -3
echo "--- 9.authorized_keys(发现skey-前缀=工具密钥需向用户确认) ---"
cat ~/.ssh/authorized_keys 2>/dev/null | awk '{print $1, $3}'
echo "--- 10./tmp权限 ---"
ls -ld /tmp /var/tmp 2>/dev/null
echo "--- 11.cron异常 ---"
sudo cat /etc/crontab 2>/dev/null | grep -v '^#' | grep -v '^$' | head -5
sudo ls /etc/cron.d/ 2>/dev/null
echo "--- 12.nginx版本隐藏 ---"
sudo grep -r 'server_tokens' /etc/nginx/nginx.conf 2>/dev/null | head -2
echo "===== END ====="
