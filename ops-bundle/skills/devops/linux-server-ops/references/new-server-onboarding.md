# 新服务器上架运行手册（2026-08-04 实测 185.239.224.191）

目标：新购公网服务器从"密码可登录"到"纯密钥 + fail2ban"安全状态，全程防锁死。

## 1. 连通性 + 工具检查
```bash
bash -c 'echo > /dev/tcp/IP/22' && echo 22通 || echo 22不通
ping -c 2 -W 3 IP      # >150ms 多为海外节点
which sshpass          # 首次密码接入必需 sshpass
```

## 2. 密码接入 + 采集规格
```bash
sshpass -p 'PASS' ssh -o StrictHostKeyChecking=no -o NumberOfPasswordPrompts=1 -o ConnectTimeout=15 root@IP \
  "hostname; head -3 /etc/os-release; nproc; free -h | head -2; df -h / | tail -1; lsblk -o NAME,SIZE,MOUNTPOINT | grep -v loop; curl -s --max-time 5 ipinfo.io/IP/json"
```
- 记录：hostname / OS / 核数 / 内存 / 磁盘布局 / ipinfo 归属
- ⚠️ 归属与用户宣称地域不符时提醒确认（实测：用户称"香港"，ipinfo 显示 Tokyo/JP AS134835）

## 3. 部署本机公钥（密码会话内）
```bash
sshpass -p 'PASS' ssh ... root@IP "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '$(cat ~/.ssh/id_ed25519.pub)' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

## 4. 验证密钥登录 —— ⚠️ 可能因 PubkeyAuthentication no 失败
```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 root@IP "echo ok"
# 失败且报 Permission denied (password) 时，先查服务端生效配置：
sshpass -p 'PASS' ssh ... root@IP "sudo sshd -T | grep -iE 'pubkeyauthentication|passwordauthentication|permitrootlogin'"
# pubkeyauthentication no = 服务端显式关闭公钥认证（厂商默认），不是密钥部署错误
```

## 5. 锁定（一条会话内完成，先语法检查再重启）
```bash
sudo sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sudo sshd -t && sudo systemctl restart ssh && sleep 1
sudo sshd -T | grep -Ei 'pubkey|password|permitrootlogin'   # 复核生效值
```

## 6. 双向验证（两条必须都过）
```bash
# 密钥登录必须成功
ssh -o BatchMode=yes root@IP "echo OK"
# 密码登录必须被拒 —— 必须 -o PubkeyAuthentication=no 强制排除本地密钥，
# 否则 sshpass 会"偷用"本地密钥误报成功
sshpass -p 'PASS' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no root@IP "echo 不应输出"
# 期望输出：Permission denied (publickey)
```

## 7. fail2ban（新机日志常已有大量 Failed password 爆破）
```bash
sudo apt-get update && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y fail2ban
# /etc/fail2ban/jail.local:
#   [DEFAULT] ignoreip = 127.0.0.1/8 ::1 <全部自有服务器IP（各台白名单互加）>
#   bantime = 3600  findtime = 600  maxretry = 5
#   [sshd] enabled = true
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```

## 8. 收尾核查
- 公网端口：`ss -tlnp | awk 'NR>1{print $4}' | grep -v 127.0.0.1 | sort -u`（应只剩 22 等必要端口）
- 重启标记：`ls /var/run/reboot-required`
- 更新记忆：服务器清单（IP/地域/规格/登录方式/加固状态）
