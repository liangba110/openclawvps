---
name: linux-server-ops
description: 多服务器(腾讯云/阿里云国际)SSH接入与运维：连接诊断、磁盘/挂载点核查、备份落盘校验、新服务器上架。当需要ssh连服务器、排查连不上、查磁盘空间、核对备份是否写到数据盘时触发。
---

# Linux 服务器接入与运维

## 适用场景
- 新服务器上架（腾讯云 / 阿里云国际站 / 轻量）
- SSH 连接失败排查（密码被拒、超时、refused）
- 磁盘空间 / 数据盘挂载点核查
- 备份脚本落盘路径校验（防备份写进系统盘）

## 连接模式
- 免密钥：`ssh -o BatchMode=yes root@IP`（known_hosts 已配置）
- 密码：`sshpass -p 'PASS' ssh -o StrictHostKeyChecking=no -o NumberOfPasswordPrompts=1 root@IP`
- 端口探测：`bash -c 'echo > /dev/tcp/IP/22'`
- 海外节点判断：`ping -c 2 -W 3 IP`（>150ms 多为海外，延迟正常不表示配置问题）

## 脚本化 SSH 访问的重试模式 ⚠️（2026-08 实测 B 机）

**症状**：连续多次 `kex_exchange_identification: read: Connection reset by peer` / `Connection closed by IP port 22`（无密码错误、非超时）——B（82.157.202.24）对高频/多连接触发限流（fail2ban/sshd MaxStartups），**随机 reset**。不是网络故障也不是被永久封禁。

**正确做法**：脚本化访问用 for 循环 + sleep 重试（3-4 次），中间穿插 `sleep 15-20`，成功率接近 100%：
```bash
for i in 1 2 3 4; do
  R=$(ssh -o BatchMode=yes -o ConnectTimeout=25 ubuntu@82.157.202.24 "命令" 2>/dev/null) \
    && { echo "$R"; break; } || { echo "attempt $i failed, retry..."; sleep 15; }
done
```
- 单次命令尽量合并多个操作（一次连接做完），减少连接次数
- 长任务（build/部署）用 `nohup ... &` 后台 + 轮询日志，别用长连接挂着
- 复杂命令避免嵌套引号（见下文引号陷阱节），SSH 参数用单引号包外层、内部双引号，或本地写文件 scp 上去

## 服务器数据布局速查（2026-08 实测）

| 服务器 | 业务数据位置 | 备注 |
|---|---|---|
| B 82.157.202.24（腾讯云） | dazi 前端 /home/ubuntu/ttdazi-frontend/；官网后端 /data/web/huizhiyunma/backend/（8081 绑 127.0.0.1）；AI电商站 /opt/ai-ecom-site（Next.js :3000，PM2 用户 aiecom，SQLite data/site.db）；OpenClaw（pnpm 旧布局 global/5/.pnpm，gateway :38598） | 用户自建 AI 应用 aiecom 勿动 |
| E 185.239.224.191（东京） | **无 MySQL/无后端进程**：仅 /var/www/ttdazi 静态站文件 + nginx `ttdazi-xyz` 站点（www.ttdazi.xyz 反代到 api_upstream=Server A:443）；/tmp/ttdazi* 备份副本 | 别按\"国际站跑于此\"误以为 E 上有库；装软件/查数据先看这里 |
| A 42.193.113.230（腾讯云，本机） | ttdazi 代码 /opt/ttdazi/；支付网关 /opt/ttdazi/payment_service（5005）；aiweb /opt/aiweb/（5003）；数据盘 /data/disk | 核心数据机 |

OpenClaw 实例（B/E）的安装/运维细节见 📖 `openclaw-server-deploy` skill。

## SSH 连接失败诊断流程（按序执行）
1. **端口探测** — 22 不通 → 安全组/防火墙未放行；通 → 继续
2. **抓 banner**：`exec 3<>/dev/tcp/IP/22; head -c 100 <&3` — 有 banner 说明 sshd 运行中，问题在认证层
3. `Permission denied (publickey,password)` = sshd 正常响应但**密码错误**（不是网络问题）
4. `Connection refused` / `timed out` 波动 = ①连续密码失败触发 **fail2ban 临时封禁**（等 2 分钟再试）②实例重启中
5. ⚠️ **host key changed 警告 = 实例被重装过系统** → 旧密码全部失效，必须控制台重置
   - 清除旧指纹：`ssh-keygen -f ~/.ssh/known_hosts -R 'IP'`
6. 阿里云国际站新购实例**默认密钥对登录**；控制台重置密码后**必须重启实例才生效**
7. 连续 3+ 次失败且原因不明 → 停下，让用户在控制台重置密码并重启，**不要反复盲试**（会持续触发 fail2ban 封禁，把诊断窗口堵死）

## 磁盘 / 备份核查
- **别信脚本注释和记忆里的路径**，以实际为准：`df -h` / `lsblk` / `cat /etc/fstab`
- fstab 形如 `UUID=xxx data/disk ext4` → 数据盘挂载点就是 `/data/disk`
- 常见事故：备份脚本 `BACKUP_BASE` 写死旧路径，备份悄悄落进系统盘（实例如 ttdazi/aiweb 脚本写 `/root/data/disk`，数据盘实际在 `/data/disk`，7 天吃掉系统盘 1.4G）
- 修正流程：`sed -i` 改脚本路径 → `mv` 迁移已有备份到正确盘 → **手动跑一次脚本验证落盘位置** → 清理系统盘残留目录 → `df -h` 复查双盘
- 系统盘只剩 30G 级别时，备份误写系统盘会快速撑爆，核查优先级高
- **备份保留策略（2026-08 起 15 天）**：daily 备份约 410MB/个，90 天 ≈ 37G 会撑爆 20G 数据盘（实测 88% 满、剩 2.4G 只够 6 天），改 15 天 ≈ 6G 合理。清理：`ls -d /data/disk/daily_* | sort | head -N` 取最旧 N 个删除，保留最近 15 个
- **Hermes 记忆已纳入备份（2026-08-28）**：`daily_backup.sh` 步骤 6.5 + `backup_hermes.sh` 均打包 `~/.hermes/memories/` 与 `~/.hermes/workspace/`（hermes_memory.tar.gz）——Hermes 每天凌晨 4 点自动重置会话（session_reset.at_hour=4），记忆文件是唯一跨会话连续性来源，漏备=记忆全丢；备份脚本里的 RETENTION_DAYS 需与数据盘保留策略同步改（90→15）
- ⚠️ **删 daily_* 报 Permission denied 但目录属主是 ubuntu？看父目录**：删除目录条目需要**父目录**写权限，不是目录自身。`/data/disk` 属 root:root 755 → ubuntu 直接 `rm -rf` 全部 Permission denied，必须 `sudo rm -rf`
- 清理前先看内容再删：`ls -la /data/disk/fullbackup_*/ /data/disk/backup_download/`（旧全量备份如 ttdazi_full_backup_*.tar.gz，确认日期超期再一并删）；删完 `df -h` 复查双盘

## Chrome 杀不死？browser-vnc 三层保活拉锯（2026-08 Server B 实测）⚠️

**症状**：B 机负载长期 2.5+（2核机），`ps aux` 看到 `/opt/google/chrome` renderer/gpu-process 各占 60%+ CPU，`pkill -9 -x chrome` 杀掉后 **30 秒内复活**。

**根因（三层保活，缺一不可地全停）**：
1. `browser-vnc-chromium.service`（systemd `Restart=on-failure` + `RestartSec=3`）跑 `/opt/browser-vnc/start-chromium.sh` 启动 VNC Chrome（root，CDP 9222，页面 cloud.tencent.com）
2. **`browser-vnc-healthcheck.timer` 每 30 秒跑 `healthcheck.sh` auto-repair**——检测到 chromium 没跑就重新 enable+start 服务。这就是"disable --now 后 30 秒又 active running"的真凶
3. ubuntu crontab `chrome_clean_notify.sh` 每 30 分钟杀 renderer/gpu（防 OOM）→ Chrome 页面强杀重载 → CPU 空转，形成"清理→重载"拉锯

**根治命令（一次连做完）**：
```bash
sudo systemctl disable --now browser-vnc-healthcheck.timer browser-vnc-healthcheck.service \
  browser-vnc-update-devtools-port.service browser-vnc-chromium.service
crontab -l | grep -v chrome_clean_notify.sh | crontab -
sudo pkill -9 -x chrome
```
⚠️ 别用 `pkill -9 -f '/opt/google/chrome'`：`-f` 会匹配远程 bash 会话自身命令行（含该字符串）→ SSH 会话被 SIGKILL 掐断、命令看起来全失败。用 `pkill -x chrome`（精确匹配进程名，安全）。

**验证**：`systemctl is-active` 全 inactive + `is-enabled` 全 disabled + `pgrep -x chrome` 只剩 openclaw 的 playwright 实例（ubuntu 用户，`--user-data-dir=/home/ubuntu/.openclaw/browser-existing-session`，CPU <1%，属 openclaw 正常浏览器后端，勿杀）。负载 2.6→1.0，Xvnc/openbox/websockify 轻量组件保留不影响。

## 网站打不开排查：DNS vs 服务器（域名过期是高发原因）

"网站打不开"先分清是 DNS 层问题还是服务器层问题，别一头扎进服务器：

1. **查解析**：`dig +short www.域名 A` — 无结果/NXDOMAIN = DNS 层问题，先别查服务器
2. **查权威 NS 判断域名是否过期**：`dig +trace 域名 @8.8.8.8 | grep "域名.*NS"`（本机 resolv 经常超时，用 @8.8.8.8 / @1.1.1.1 / @114.114.114.114 更稳）
   - ⚠️ **NS 为 dnsowl.com 不能直接断定过期**：dnsowl.com 是 **NameSilo 的默认免费 DNS**（ns1/2/3.dnsowl.com），NameSilo 注册的域名默认用它；同时 Namecheap 过期域名也可能转 dnsowl 停放。**必须查 whois 的 Expiry/Status 确认**（`python3 socket 连 whois.nic.<tld>:43` 或 RDAP），Creation Date 很新 + addPeriod = 新注册（正常），Expired/Redemption = 真过期
3. **验证服务器本身（绕过 DNS 直连）**：
   ```bash
   curl -sS -o /dev/null -w "HTTP:%{http_code}\n" -m 10 --resolve www.域名:443:服务器IP https://www.域名/
   ```
   HTTP 200 = 服务器健康（Nginx、证书、前端全正常），问题在域名/DNS 层
4. **域名恢复后必查残留停放记录**：过期期间 Namecheap 自动生成的停放 A 记录（常指向 Vultr 等第三方 IP，页面显示 "Welcome to <域名>" 停放页）续费后**不会自动删除**。多 A 记录轮询造成**时好时坏**：抽中真 IP 正常、抽中停放 IP 打不开。处理：
   - 多 DNS 轮询暴露全部记录：`for dns in 8.8.8.8 1.1.1.1 223.5.5.5 119.29.29.29; do dig +time=3 +tries=1 +short www.域名 A @$dns; done`
   - 逐 IP 测真伪：`curl -sk --resolve www.域名:443:IP https://www.域名/` — 停放 IP 返回 "Welcome to" 停放页或 000，真 IP 返回 200
   - 到注册商（Namecheap → Advanced DNS）删掉停放 A 记录只留真实 IP 一条；Nameservers 改回注册商默认（或原 CF CDN NS，勿留在 dnsowl 停放）
   - ⚠️ 域名操作不可逆，让用户先在控制台看状态（Active / Expired / Redemption）再动手，别让用户乱点
5. **验证删除已生效**：直查权威 NS（带 TTL，不受递归缓存影响）：`dig +noall +answer www.域名 A @ns1.dnsowl.com` — 只剩真实 IP 一条即生效
6. **缓存滞后别误判**：删除后 8.8.8.8 可能已干净，但国内 DNS（223.5.5.5 / 119.29.29.29）缓存旧记录需 **1-2h TTL 自然过期**，期间用户仍时好时坏属正常。本机 systemd-resolved 缓存用 `sudo resolvectl flush-caches` 刷新后 `getent hosts` 确认。模拟国内用户视角：SSH 到腾讯云服务器上 `dig @223.5.5.5` + curl 实测

详见 📖 `references/domain-expired-dns-triage.md`

## SSH 会话内重启服务（pkill -f 误杀自己）⚠️
通过 `sshpass ssh root@IP "sudo pkill -f 'gunicorn main:app' && ..."` 远程重启服务时，
**pkill -f 会匹配到当前 SSH 会话自身的命令行**（因为远程 shell 命令行里包含
'gunicorn main:app' 这个字符串），导致 SSH 会话被 SIGTERM 杀掉，返回
`exit_code: -15`，后续 `&&` 命令全部不执行，看起来像"命令失败/中断"。

正确做法（三步分开，避免在同一条 ssh 命令里 pkill 自己）：
```bash
# 1. 单独一条 ssh 只杀进程（接受 -15 退出，属正常）
sshpass -p 'PASS' ssh root@IP "sudo pkill -f 'gunicorn main:app'; sleep 2"
# 2. 单独一条 ssh 重启并检查（新会话不受影响）
sshpass -p 'PASS' ssh root@IP "cd /opt/xx/backend && sudo -u ubuntu nohup /usr/bin/python3.12 -m gunicorn main:app -b 0.0.0.0:5002 -w 2 --log-level info --timeout 120 > /tmp/xx.log 2>&1 &"
# 3. 单独一条验证
sshpass -p 'PASS' ssh root@IP "ps aux | grep 'gunicorn main:app' | grep -v grep | wc -l; curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5002/api/health"
```
或者单条命令里用 `pkill -f ... || true` + 明确不依赖后续执行；最稳是分 2-3 条 ssh。
重启后必须验证：进程数 + 健康检查 HTTP 200 + 新 PID（确认不是旧进程残留）。

## 跨地域/跨服务器大文件传输（单连接被掐断）⚠️

**症状**：从海外服务器（阿里云国际等）往国内本机传大文件，scp/rsync/curl 都**规律性断在同一字节数**（实测每次卡在 2,612,100 字节 ≈ 2.5MB），而小命令（ssh、15K 文件 scp）秒回 → 链路对单连接累计流量有限制，不是随机网络抖动。别反复试同一种方式。

1. **分块传输（抗断流）**：源机 `split -b 512k file part_`，循环逐块 scp（每块独立连接，断哪块重传哪块），`cat part_* > file` 合并后 `md5sum` 对照源机校验。
   - ⚠️ split 默认后缀是 `aa/ab/ac…`，循环用 `ls part_*` 取真实文件名，别按 `aa1/aa2` 写（会全部文件不存在、白耗超时）
2. **海外服务器间直连更快**：国内↔海外链路不稳时，让两台海外节点直连（如日本机直接拉阿里云国际的 HTTP/scp），海外链路通常稳且快，绕开国内中转
3. **一次性跨机密钥对**（两台机器无互信密钥时）：
   ```bash
   ssh-keygen -t ed25519 -N '' -f /tmp/sync_key
   ssh root@目标机 "echo '$(cat /tmp/sync_key.pub)' >> ~/.ssh/authorized_keys"   # 本机ssh加公钥
   scp /tmp/sync_key 源机:/tmp/                                                  # 私钥传到源机(小文件能传)
   ssh 源机 "for f in /tmp/part_*; do scp -i /tmp/sync_key -o StrictHostKeyChecking=no \$f root@目标机:/tmp/; done"
   ```
   **用完必须清理**：删目标机 authorized_keys 里的对应行 + 删源/目标机上私钥（本次 E 机就是靠这个 D→E 直传 9 块全过）
4. **超时杀本地 ssh 客户端 ≠ 杀远端进程**：本地 `timeout` 只杀本地进程，远端命令变孤儿继续跑（实测 certbot 卡 2 小时，重跑报 `Another instance of Certbot is already running`）。处理：远端 `ps aux | grep` 定位 + `kill -9`。后台跑长命令前确认命令本身要在正确的机器上执行（本机没装的工具别在本机跑）
5. **长任务用户催进度**：跨服大文件传输动辄十几分钟，用户会反复问\"可以了吗/继续\"。别闷头重试：写成脚本 `background=true + notify_on_complete=true` 跑，回一句\"正在传 X 块/Y 块，完成自动汇报\"即可；中途被问就 poll 一下报进度

## SSH 密码认证禁用（改纯密钥）— 防锁死顺序

改之前先确保密钥登录可用，顺序错了会把自己锁在门外：

1. 部署公钥：`sshpass ... "mkdir -p ~/.ssh && echo '$PUB' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"`
2. **先验证**：`ssh -o BatchMode=yes ubuntu@IP "echo ok"` 成功才继续
   - ⚠️ **新服务器 PubkeyAuthentication no 陷阱**（实测 185.239.224.191）：部分厂商默认在 sshd_config 显式写 `PubkeyAuthentication no`，密钥已正确部署但密钥登录仍报 `Permission denied (password)`。此时**不是密钥问题**，先查生效配置 `sudo sshd -T | grep -iE 'pubkeyauthentication|passwordauthentication'`；若为 `pubkeyauthentication no`，先 sed 改成 `PubkeyAuthentication yes` 并 `systemctl restart ssh` 再回来验证
3. 改配置：`PasswordAuthentication no` + `PermitRootLogin prohibit-password`
4. **Ubuntu 24.04 陷阱**：`/etc/ssh/sshd_config.d/50-cloud-init.conf` 里 `PasswordAuthentication yes` 会**覆盖主配置**，必须一并改；用 `sudo sshd -T | grep passwordauthentication` 确认生效值
5. `sudo sshd -t` 语法检查 → `systemctl restart ssh`
6. **验证禁用**：必须加 `-o PreferredAuthentications=password -o PubkeyAuthentication=no` 强制排除密钥再测，应返回 `Permission denied (publickey)`
   - ⚠️ sshpass 误报陷阱：禁用密码后 `sshpass -p ...` 仍"成功登录"= 客户端自动用了刚部署的本地密钥，不是密码生效。不带 `-o PubkeyAuthentication=no` 的测试结果不可信
7. 配套 fail2ban（防 SSH 爆破）：`jail.local` 里 `[sshd] maxretry=5 bantime=3600 findtime=600 ignoreip=127.0.0.1/8 <自有服务器IP>`；`fail2ban-client status sshd` 查看 Banned IP。服务器日志里 `Failed password` 上万条是常态，靠 fail2ban 兜底

完整新服务器上架运行手册（探测→规格采集→部署密钥→PubkeyAuthentication 修复→锁定→双向验证→fail2ban→收尾）见 📖 `references/new-server-onboarding.md`

## 私钥交付 — 内容会被安全机制脱敏，必须打包附件

用户要私钥时，`read_file` / `cat ~/.ssh/id_ed25519` 输出会被 Hermes 安全机制脱敏为 `[REDACTED PRIVATE KEY]`（防密钥泄露进对话记录），**直接读文本行不通**。正确做法：打包 zip 用 MEDIA 附件发送：

```bash
mkdir -p /home/ubuntu/key_export && cp ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub /home/ubuntu/key_export/
# 写 README.txt：服务器列表(IP/用户) + Linux/Mac/Windows 使用方法 + 私钥保管警告
cd /home/ubuntu/key_export && zip -j ttdazi_ssh_key.zip id_ed25519 id_ed25519.pub README.txt
# 回复中发：MEDIA:/home/ubuntu/key_export/ttdazi_ssh_key.zip
```

注意事项：① 私钥=服务器钥匙，回复中必须附保管警告（泄露=失守）；② 若用户要"只留我的密钥"，把 Hermes 本机公钥从各服务器 `authorized_keys` 删掉即可；③ 密钥丢失可通过云控制台重置密码后重新部署，需告知。

**非技术用户（用户自己电脑）配 SSH/Trae/SFTP 访问**：用户不会命令行，必须给傻瓜式 Win→PowerShell 步骤（见 📖 `references/user-access-onboarding.md`）；先查 `PasswordAuthentication` 是否 no（纯密钥），再走"用户生成→公钥发我→我加 authorized_keys→Trae config 别名"流程。用户说"连不上"先做服务器侧诊断（journalctl 有无 Accepted/Failed、fail2ban 是否误封）再改配置；GitHub SSH 公钥≠服务器密钥，服务器 push 用户 GitHub 仓库需要的是**私钥**。

**服务器操作用户 GitHub 仓库（2026-08-28 实测）**：用户想把仓库部署/推送到服务器上时，服务器需要**用户 GitHub 账号的私钥**（不是公钥）：
```bash
# 1. 用户私钥装到服务器（权限 600），独立文件名避免与服务器自身密钥混淆
install -m 600 /path/to/user_private_key ~/.ssh/github_id_ed25519
# 2. 校验私钥与用户之前给的公钥是否匹配（防用户发错/发的是另一个账号的密钥）
ssh-keygen -y -f ~/.ssh/github_id_ed25519 | grep -q '<公钥指纹>' && echo MATCH
# 3. ~/.ssh/config 加 github.com 条目（IdentitiesOnly 防止误用服务器其他密钥导致认证混乱）
cat >> ~/.ssh/config << 'EOF'

Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_id_ed25519
    IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
# 4. 验证（成功返回 "Hi <用户名>! You've successfully authenticated"）
ssh -o BatchMode=yes -T git@github.com
# 5. 之后即可 git clone git@github.com:<user>/<repo>.git
```
坑：①用户可能发 GitHub 公钥以为能用于服务器——公钥只能让别人连进来，服务器去 push 需要**私钥**；②私钥文件从 QQ/chat 附件接收后存在 cache 目录，`install -m 600` 到位后无需保留副本；③验证 git 连通性用 `ssh -T git@github.com` 返回的用户名确认是预期账号。

**Hermes 记忆体系运维（A 机自维护系统）**：双轨记忆 + git 异地 + AES 加密备份 + 每周整理/每日巡检 cron，维护要点与教训见 📖 `references/hermes-memory-system.md`。

## Nginx 隐藏版本号 — server_tokens 位置陷阱 ⚠️
`server_tokens off;` 必须写在 **nginx.conf 的 `http{}` 块内**（Ubuntu 默认第 21 行附近），**不要**再单独建 `/etc/nginx/conf.d/xxx.conf` 重复定义——conf.d 文件也被 include，与 nginx.conf 重复声明会直接 `nginx -t` 失败（`server_tokens` directive is duplicate）导致 reload 失败。改法：
```bash
# 确认 http{} 块内已有（或加一行）
grep -n 'server_tokens' /etc/nginx/nginx.conf   # 应为 server_tokens off; 无 # 注释
# 如无：在 http { 后加
sudo sed -i '/^http {/a\\\\    server_tokens off;' /etc/nginx/nginx.conf
sudo nginx -t && sudo systemctl reload nginx
curl -skI https://域名/ | grep -i '^server'     # 应显示 server: nginx（无版本号）
```
验证版本隐藏：`curl -skI` 看 Server 头从 `nginx/1.24.0 (Ubuntu)` 变为 `nginx`。

## 服务器安全加固清单（2026-08-03 实测流程）

对公网服务器做基础安全加固，按序执行（每步验证再进下一步）：

1. **fail2ban 防 SSH 爆破**（最高优先，日志常上万条 Failed password）：
   ```bash
   sudo apt-get install -y fail2ban
   # /etc/fail2ban/jail.local: [sshd] enabled=true maxretry=5 bantime=3600 findtime=600 ignoreip=127.0.0.1/8 <自有服务器IP>
   sudo systemctl enable --now fail2ban
   sudo fail2ban-client status sshd   # Currently banned / Banned IP list
   ```
2. **隐藏 Nginx 版本**：见上节 server_tokens
3. **Nginx 限流**：`limit_req_zone` 在 http{} 定义后，**必须在目标 server 块里实际应用** `limit_req zone=xxx burst=50 nodelay;` 才生效——只定义 zone 不应用等于没有（Server B dazi 块曾只定义未应用）。burst 别太小（login 用 10+，API 用 20-50）防误伤正常用户
4. **公网端口核查**：`for p in 21 22 443 3306 5002 5003 5005; do timeout 5 bash -c "echo > /dev/tcp/IP/$p" && echo "$p 通" || echo "$p 不通"; done` — 只暴露必要端口；云服务器**用安全组而非本机 iptables/UFW**（本机规则有锁死 SSH 风险，云安全组在 hypervisor 层随时可恢复）
5. **IP 归属/暴露服务评估**：公网可达的支付/管理服务确认有鉴权（如支付 5005 只暴露带微信签名的路由算可接受）；`ipinfo.io/IP/json` 查归属
6. **攻击扫描识别**：`grep 'Failed password' /var/log/auth.log | grep -oE 'from [0-9.]+' | sort|uniq -c|sort -rn|head` 找爆破源；Nginx access.log 里 `kitty.*|titanjr.*|bins/bin` = Mirai 僵尸网络探测，无成功即无视
7. **系统更新**：`apt update && apt upgrade -y`，`/var/run/reboot-required` 存在则需重启（重启前确认 nginx/systemd 服务 enabled）
8. **业务端口白名单化（iptables，先 ACCEPT 后 DROP 防业务中断）**（2026-08-04 Server A 实测，核心数据服务器适用）：
   - **动手前先梳理端口调用方**：每个业务端口谁在访问（反代服务器 IP、支付回调路径、国际站直连等）。例：A 的 5002/5003 只被 Server B 反代、5005 被 B+国际站 E 直连且微信回调走 Caddy 443→127.0.0.1:5005 回环（回环不受 INPUT 影响，无需对公网开 5005）→ 白名单 = B/E 两个来源
   - **分两步防断网**：①先加 `-A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT` + `-i lo` + 22/80/443 + 各业务端口对调用方 IP 的 ACCEPT；②**从可信服务器实测各通道全通、本机回环正常后**，再加对应端口的 `-j DROP` 兜底。别第一步就改 policy DROP（锁死 SSH 风险）；黑名单模式（只 REJECT 已知攻击 IP）不够，业务端口必须按来源白名单
   - **持久化**：`apt install iptables-persistent && sudo netfilter-persistent save`（否则重启规则全丢）；确认 `/etc/iptables/rules.v4` 有对应规则
   - **明文协议/管理面板一并处理**：FTP（vsftpd）公网明文暴露=送密码，直接 `systemctl disable --now vsftpd`（文件传输用 SFTP）；管理面板（1Panel 等）按用户选择关闭或限 IP
   - **云安全组双保险**：提醒用户在云控制台安全组同步只放行 22/80/443（安全组在 hypervisor 层，重装系统后仍兜底）
   - 加固完成必须全站回归：主站/支付/国际站逐一点 200 + 可信服务器白名单通道复测

## Nginx 反代域名解析坑（IP 直写 + SNI 是王道）⚠️

nginx 反代到上游域名有两类解析坑（2026-08 B/E 实测）：
- `proxy_pass https://域名/pay$1;` **带变量** → nginx 运行时解析域名，未配 resolver 报 `no resolver defined to resolve xxx` → 502（B 主站 /pay/ 502 根因）
- `proxy_pass https://域名;` **不带变量** → 启动时解析，DNS 抖动即 `host not found in upstream "域名"` → `nginx -t` 失败 / 服务反复崩溃（E 日本机 DNS 不稳，nginx 一天崩 3 次的根因）

**正解：proxy_pass 一律 IP 直写 + SNI 指定**，启动/运行零 DNS 依赖：
```nginx
proxy_pass https://1.2.3.4:443;
proxy_ssl_server_name on;
proxy_ssl_name 真实域名;   # SNI，证书匹配 + 上游按域名路由
```
IP 字面量 + 变量（`$1`/`$request_uri`）不需要 resolver；域名才需要。

## Caddy 按 Host 头路由 — 反代 Host 必须匹配上游站点 ⚠️（2026-08-05 实测）

**症状**：dazi 主站点支付 → 跳 /pay → **返回主站首页**（看起来像"支付被吞了/跳回首页"）。A 的 Caddy 一切正常（`curl --resolve pay.openai2000.cn:443:AIP https://pay.openai2000.cn/pay` 返回支付页），但 B 反代后 `curl https://dazi.openai2000.cn/pay` 返回 200 + 主站 index.html（大小恰好=主站首页）。

**根因**：Caddy 路由按 **Host 头**（不是 SNI）匹配站点块。B 反代 `/pay` 时 `proxy_set_header Host $host`（透传 dazi.openai2000.cn）→ A 的 Caddy 按 Host=dazi 命中**多 Host 业务站点**（api/dazi/aiweb/www.ttdazi.xyz → @dazi → 5002）→ 5002 Flask 对未知路径 serve 静态 fallback 返回 index.html。SNI=pay.openai2000.cn 只影响证书选择，**不影响站点路由**。

**修复**：反代到专用上游时 Host 头必须固定为上游站点名：
```nginx
location /pay {
    proxy_pass https://42.193.113.230:443;      # IP 直写
    proxy_ssl_server_name on;
    proxy_ssl_name pay.openai2000.cn;            # SNI=证书
    proxy_set_header Host pay.openai2000.cn;     # Host=路由（关键！不能 $host）
}
```
**排查经验**：①`curl -sI https://域名/pay` 看 content-length（=主站首页大小说明被路由错）②抓包 `tcpdump -i any host AIP and port 443` 确认 proxy 出站正常（排除 nginx location 问题）③**Caddy 按 Host 路由，反代必须显式设置 Host 匹配上游站点**；同架构里 `/api/ /socket.io/ /uploads/` 透传 Host=$host 反而正确（因为业务站点就是按 dazi 分流到 5002），**只有跨站点（pay）必须改 Host**。

## Nginx 反代上游 TLS 证书验证（proxy_ssl_verify on）⚠️

"全程加密"要求给反代开启上游证书验证 `proxy_ssl_verify on; proxy_ssl_trusted_certificate ...;` 时的全套坑（2026-08 E→A/D 实测，openssl 验证全过但 nginx 三连报错）：

1. **openssl 能过、nginx 报 `unable to get local issuer certificate` → 先查 `proxy_ssl_verify_depth`**：nginx 默认 **depth=1**，Let's Encrypt 2024 新链深度 4（叶子→YE1→Root YE→X2→X1），必须 `proxy_ssl_verify_depth 6;`。判定：`openssl s_client -connect IP:443 -servername 域名 -CAfile 信任文件 | grep 'Verify return'` 返回 0，但 nginx 握手报 error 2 —— 加 depth 即好
2. **信任文件必须含中间证书，不只是根**：系统 `/etc/ssl/certs/ca-certificates.crt` 只有根证书；LE 2024 链实际是 叶子→中间(YE1/YR2)→新根(Root YE/Root YR)→旧根，且**系统 ISRG_Root_X2.pem 是 X1 交叉签名版**（issuer=X1），链终点是 X1 → 信任文件 = 各服务器链的非叶子证书 + ISRG X1/X2
3. **信任文件构建（防 bad end line）**：`openssl s_client -showcerts` 抓链 → 取非叶子证书 + 系统根 → **逐个 `openssl x509 -outform PEM` 重编码再拼接**（直接用 re.findall 拼原始抓取文本会 `PEM routines::bad end line`，`nginx -t` 报 `SSL_CTX_load_verify_locations failed`）
4. **keepalive 连接池 SNI 混淆 → 偶发 502**：多个 location 用相同 `proxy_pass https://同IP:443` 但不同 `proxy_ssl_name`（如 api 与 pay 两个 SNI）→ nginx 复用上游连接时 SNI 与证书不匹配，报 `upstream SSL certificate does not match "xxx"`，症状是时好时坏（连接复用竞态）。修复：http 级按 SNI 拆 upstream 块，各 location 用各自 upstream：
   ```nginx
   upstream api_upstream { server 42.193.113.230:443; keepalive 16; }
   upstream pay_upstream { server 42.193.113.230:443; keepalive 16; }
   ```
5. **验证链**：`curl --resolve` 全链路 200 + `tail error.log` 无 verify error + **高并发混合请求**（API/pay 交替 8 轮以上）无 certificate mismatch——单发 200 测不出连接池问题

## 新站点上线：certbot --nginx 配置陷阱 + 静态目录权限 ⚠️

2026-08 实测（Server B info.openai2000.cn 纯静态站上线）：

1. **certbot --nginx 会把 80 块的 `return 301` 原样留在 443 块里 → 443 自己重定向自己**：预先写好 80 端口 server 块（`location / { return 301 https://$host$request_uri; }`）再跑 `certbot --nginx -d 域名 --redirect`，certbot 只把 `listen 80` 改成 `listen 443 ssl`，**location 里的 return 301 原样保留** → 443 上 GET / 返回 301（Content-Length: 162，跳转目标还是自己）。症状：80→443 正常、443→301 循环。修复：签完证书**重写 conf**——443 块用 `root + try_files`，80 块单独 return 301，再 `nginx -t && reload`
2. **scp 部署的静态文件是 600 权限，nginx(www-data) 读不了 → 403**：本地 write_file 生成的文件默认 600，传上服务器后必须 `sudo chown -R www-data:www-data 站点目录 && sudo chmod -R 755`，否则页面 403/空
3. **⚠️ scp 多源文件丢目录路径（basename 展平）**：`scp /a/js/app.js /a/js/data.js user@host:/var/www/site/` 多源文件时目标取**每个文件的 basename**，`js/app.js` 会被放到站点**根目录** `/var/www/site/app.js` 而不是 `js/` 子目录 → **index.html 更新了但 js/ 下还是旧版**（页面仍加载旧 js，grep 新关键字查不到、肉眼难发现）。修复：删除根目录误传文件 + **逐文件 scp 到完整目标路径**（`scp a.js user@host:/var/www/site/js/a.js`）；更新验证用 **md5sum 两端逐文件对比**（Server B 与本地源必须一致）
4. **scp 覆盖已存在文件报 `Permission denied`（www-data 属主）**：站点目录归 `www-data` 后，部署用户 scp 覆盖旧文件失败。部署顺序固化：`sudo chown -R ubuntu:ubuntu`（部署用户）→ scp → `sudo chown -R www-data:www-data && sudo chmod -R 755`（nginx 可读）→ md5 对比
5. **验证纪律**：HEAD 与 GET 分开测——`curl -skI` 返回 200 不代表 GET 正常（本会话 HEAD 200 但 GET 301 循环）；用 `curl -sk -o /dev/null -w '%{http_code} 大小:%{size_download}'`，大小应等于 index.html 真实字节数；更新后必须确认 Server B 文件 md5 = 本地源 md5
6. **改 dist 构建产物文案，必须同时处理 immutable 缓存**（无源码/不想重 build 时）：`sed -i 's/旧文案/新文案/g' assets/*.js` 直接改 dist 可行——中文字符串不会出现在代码逻辑里，替换安全；动手前先 `grep -o '.\{12\}关键词.\{12\}'` 抽查上下文确认都是文案，改前 `cp -r assets /tmp/bak_$(date +%Y%m%d)` 备份。⚠️ 带 hash 文件名的 assets 若配置 `expires 1y; immutable`，改内容后文件名没变 → 浏览器缓存旧版永不更新（症状：`grep` 线上 js 已有新文案、浏览器页面还是旧的）。处理：assets location 改 `expires 0; add_header Cache-Control "no-cache, max-age=0";`（或重新构建生成新 hash）。**纯静态站（非 hash 文件名）改版"用户看不到新版"同理**：index.html 引用加 `?v=日期` 版本号（强制重拉 css/js）+ nginx 对 index.html 配 `Cache-Control "no-cache, max-age=0"`（防 index.html 本身被浏览器启发式缓存导致版本号不生效）——**两者缺一不可**，只加版本号或只改 no-cache 都可能在微信 WebView（缓存最顽固）里继续显示旧版。页面标题/logo alt 等文本在 index.html 和 manifest.json 里，一并 sed
7. **服务器迁移后 /etc/hosts 残留旧 IP → "改了没生效"假象**：`/etc/hosts` 硬编码旧服务器 IP（迁移前加的），本机浏览器/curl 全部打到旧机，线上明明已改却"看不到变化"（浏览器加载的还是旧站 index-*.js）。排查：`grep 域名 /etc/hosts` + 多 DNS 对比（`dig +short 域名 A @8.8.8.8` 与 `getent hosts 域名` 不一致 = hosts 或本地 resolver 问题）；修正：`sudo sed -i 's/旧IP/新IP/' /etc/hosts` 后 `sudo resolvectl flush-caches`。结合 E 站恶意 UA 分流：测试必须带浏览器 UA（详见恶意流量分流节）
8. **sed 多行插入 nginx 配置会合并成一行**：`sed -i '/pattern/i\\ line1\\ line2'` 插入多行时实际合并为一行（如 `location = /en { ... }    location /en/ { ... }`），nginx -t 能过但难维护。多行插入改用 python 脚本，或写成独立 conf 文件在 server 块内 include。给 SPA 加静态子路径（如 `/en/`）用 `location = /en { return 301 /en/; }` + `location /en/ { alias 目录; index index.html; }`，验证无斜杠 301 与主站 SPA 不受影响
9. **复刻现有站点结构（多语言/海外版）**：浏览器 console 提取原站 DOM 拿完整结构——`document.querySelectorAll('body *')` 遍历找含关键词的最小容器（如 section 标题文本）→ `el.parentElement.outerHTML` 逐层拿 section 结构（hero-area/top-bar/banner-carousel/game-grid/rec-card/bottom-nav 等类名与嵌套）→ 1:1 重建 HTML+CSS（同款渐变/圆角/卡片，**结构类名保持一致**）；数据从 API 拉快照生成 data.js（字段过滤规则见 game-platform-compliance 三.6）。原站 logo/头像等静态资源同域路径可直接复用（如 /brand/logo-horizontal.png、/avatars/）；SPA index.html 注入浮动元素（EN 切换/浮层）用 `</body>` 前 sed 插入 `<a>`+`<style>`（fixed+高 z-index+避开顶部导航/底部 tab 的位置），零风险

## Vite 项目重建 dist 的坑（SEO 静态页丢失 + 属主权限）⚠️

- **`vite build` 默认清空 dist**：若构建脚本是 `vite build && node seo/generate.js`（生成 *.seo.html、案例/文章静态页、sitemap.xml），**单独跑 `vite build` 会把已生成的 SEO 页全删**（百度收录断崖，且不易察觉——页面仍 200）。必须跑完整构建脚本或补跑 generate.js（纯读库生成，无需外部 API；⚠️ SEO 生成器连的库可能用独立账号，如模板订单在 pay_system 用户下，主库用户无权访问会报 Access denied）
- **dist 属主 www-data 时 ubuntu 用户构建报 emptyDir 权限错**（`emptyDir ... sitemap.xml`）：上一轮部署把 dist chown 给了 www-data，下次重建直接 `vite build` 失败。部署循环固定为：`sudo chown -R ubuntu:ubuntu dist` → 构建 + SEO 生成 → `sudo chown -R www-data:www-data dist && sudo chmod -R 755`（nginx 可读）→ 全站回归（含百度 UA 的 SEO 版页面 200）
- **本地改文件后部署必须确认 scp 真执行（漏传 = 线上旧版 = 用户报"还是不行"）**：标准流程是 本地改 → `scp` 到远端 /tmp → 远端 `sudo cp /tmp/x src/`。若只改了本地、远端 /tmp 还是旧文件，`sudo cp` 覆盖的是**旧版** → 构建产物不含新逻辑，用户端表现不变。部署后必须验证：`grep 新关键字（如 'payment/native'）dist/assets/*.js` 有结果，或 md5 对比。用户重复报同一问题时，第一排查项就是线上产物是否真含新代码

## 微信内置浏览器(X5)提示"不安全" — 证书必须是 RSA 链 ⚠️（2026-08 实测 www.openai2000.cn）

**症状**：电脑浏览器访问正常（Chrome/Edge 自动兼容），微信内打开网页提示"不安全/非私密连接"。

**根因**：证书是 **ECDSA 算法签发**（Let's Encrypt 历史签发可能带 `key_type = ecdsa`，证书 Signature Algorithm 为 `ecdsa-with-SHA384`、Public Key 为 `id-ecPublicKey (P-256)`）。微信 X5 内核**只信任 RSA 证书链**（链终点须为 ISRG Root X1 的 RSA 链），ECDSA 链在 X5 里信任验证失败 → 报不安全。电脑浏览器会自动补链/兼容，所以网页端看不出问题。

**诊断三步（判别证书算法是第一步，别先去查链）**：
```bash
# 1. 证书算法（关键判别）——ecdsa-with-SHA384 = 微信必报不安全
echo | openssl s_client -connect 域名:443 -servername 域名 2>/dev/null | openssl x509 -noout -text | grep -E 'Signature Algorithm|Public Key Algorithm'
# 2. 链完整性 ⚠️ 必须用 -showcerts 数 BEGIN CERTIFICATE（crl2pkcs7|pkcs7 -print_certs 方法会误报成 1 张）
echo | openssl s_client -connect 域名:443 -servername 域名 -showcerts 2>/dev/null | grep -c 'BEGIN CERTIFICATE'
# 3. 信任链验证：应为 Verify return code: 0 (ok)
echo | openssl s_client -connect 域名:443 -servername 域名 2>/dev/null | grep 'Verify return'
```
- **ECDSA 链** = 4 张：叶→YE2→Root YE→ISRG X2→X1；**RSA 链** = 3 张：叶→YR2→Root YR→ISRG Root X1 —— 终点 X1 才是 X5 信任的 RSA 根
- 服务器侧一眼确认：`cat /etc/letsencrypt/renewal/域名.conf | grep key_type`（ecdsa = 问题确认）

**修复：重新签发 RSA 证书（webroot 验证）**：
```bash
# ⚠️ 从 ECDSA 换 RSA 必须同时传 --cert-name 和 --key-type，否则报
# "Please provide both --cert-name and --key-type on the command line to confirm the change"
sudo certbot certonly --cert-name 域名 --webroot -w /var/www/html \
  -d 域名 -d www.域名 --key-type rsa --rsa-key-size 2048 --force-renewal --non-interactive
sudo nginx -t && sudo systemctl reload nginx   # 必须 reload，否则 nginx 内存还是旧证书
```

**多域名批量修复（2026-08 实测 openai2000.cn 系列 4 域名一次换完）**：

1. **重签前先读 renewal conf**：`cat /etc/letsencrypt/renewal/<名>.conf` 确认 `authenticator`（webroot / standalone / nginx）与 `webroot_path`——**每域名可能不同**（实测 aiweb=standalone、dazi=webroot、info=nginx 插件），直接照抄同一条命令会失败
2. ⚠️ **没有专属 80 server 块的域名 http-01 必失败**：请求落 default_server（如 deny-ip.conf 的 `return 444`）或他块 301，验证文件读不到。判定：`curl -s http://域名/.well-known/acme-challenge/探测文件` 拿不到内容 = 缺 80 块。修复：建独立 80 块（精确 server_name + `location /.well-known/acme-challenge/ { root <webroot>; }` + 其余 `return 301 https://$host$request_uri;`）→ `nginx -t && reload` → 公网重测可达再重签。**该 80 块保留**（后续自动续期还要用）
3. 各 authenticator 处理：有 80 块 acme location 的走 `--webroot -w <webroot_path>`；**缺 80 块的补块后同样走 webroot**；443+80 齐全的标准配置可直接 `certbot certonly --nginx -d 域名`（自动临时插 acme location 并 reload，之后恢复原配置）
4. **公网验证用 `--resolve` 排除本机 DNS 缓存**：刚加完 80 块公网仍 301 时，`curl -s --resolve 域名:80:服务器IP http://域名/.well-known/acme-challenge/probe` 直连正常 = 服务器配置没问题，是本机解析缓存旧值，别误判去改配置
5. 批量顺序：先给所有缺 80 块的域名补块 → 统一 reload → 逐个 `--cert-name <名> --key-type rsa --force-renewal` 重签 → 统一 `nginx -t && reload` → 全站回归（微信 UA 200 + 公众号回调 `403`=签名校验正常拒绝 + `/pay` 200）
6. 收尾：`rm -f <webroot>/.well-known/acme-challenge/probe` 测试文件；`grep key_type` 确认全部 `rsa`；`--force-renewal` 重签到期日顺延 90 天（实测 10-10 → 11-05）

**验证**：①叶子 `Signature Algorithm: sha256WithRSAEncryption` ②showcerts 3 张全 RSA ③`Verify return code: 0 (ok)` ④微信 UA curl 200：
```bash
curl -sk -o /dev/null -w 'HTTP:%{http_code}\n' -A 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 ... MicroMessenger/8.0.49' https://域名/
```

**注意事项**：①renewal conf 的 key_type 会随重签更新为 rsa，自动续期（certbot.timer）沿用 RSA 不会退回 ②同一 live 符号链接被多个 nginx server 块共用（如 bt-panel/deny-ip 共用主站证书）自动生效，但 nginx 不 reload 内存还是旧证书 ③**同服一键体检所有站点**是否同为 ECDSA 隐患：`for d in 域名1 域名2; do openssl x509 -in /etc/letsencrypt/live/$d/cert.pem -noout -text | grep -m1 'Signature Algorithm'; done`（全 ecdsa → 建议批量换 RSA；dazi 公众号回调走 HTTPS 换证书无影响）④换证书只改加密算法不动业务，属低风险操作，但改主站/支付域前仍按惯例先问用户

### ⚠️ Caddy 域名无法用 RSA 证书（key_type rsa 不支持）
Caddy 全局 `key_type rsa` 直接报 `unrecognized key type: rsa`（只支持 ed25519/ecdsa）。要让 Caddy 服务的域名用 RSA（微信 X5/支付服务器要求）：certbot 单独签 RSA（`--key-type rsa`）+ Caddy 站点加 `tls /etc/letsencrypt/live/域名/fullchain.pem /etc/letsencrypt/live/域名/privkey.pem` 手动指定，该域名 Caddy 不再自动续签（certbot renew 兜底）。**支付回调域名 pay.openai2000.cn 若仍 ECDSA = 微信支付服务器回调 TLS 握手失败 = 用户付钱但订单不开通**（微信支付服务器与 X5 同不认 ECDSA，tcpdump 见 220.196.160.x 连 443 只有 ack 无数据）。详见 wechat-pay-gateway skill。

### 腾讯云云镜防火墙（YJ-FIREWALL-INPUT）⚠️
腾讯云主机安全（云镜）在 iptables INPUT 首条插入 `YJ-FIREWALL-INPUT` 链（~149 条 REJECT IP，**先于所有 ACCEPT 匹配**，`sudo iptables -L YJ-FIREWALL-INPUT -n` 查看）。影响：①**certbot webroot 验证报 `During secondary validation ... Timeout during connect (likely firewall problem)`**——本机/B/E/D 服务器 curl 全通但 Let's Encrypt 验证节点被 REJECT；②理论上也可拦微信支付回调服务器 IP。备选：DNS-01（需 DNSPod API 密钥）/ TLS-ALPN-01（443，需临时让出端口）；或向用户确认后放行验证 IP。

**临时摘除云镜链重试 certbot（2026-08-28 实测，规则保留在链内不删）**：
```bash
sudo iptables-save > /tmp/iptables_before_rsa.txt    # ①备份全量规则
sudo iptables -D INPUT 1                             # ②从 INPUT 摘除首条（即 YJ 链引用），规则本身不删
# ③重试 certbot → 成功后恢复：
sudo iptables-restore < /tmp/iptables_before_rsa.txt
# 或恢复引用：sudo iptables -I INPUT 1 -j YJ-FIREWALL-INPUT
```
注意：云镜 agent 可能周期性重新插入该链（若恢复后仍见到链，属正常）；`iptables -L YJ-FIREWALL-INPUT -n | head` 确认链还在（规则未丢）再恢复。

**Let's Encrypt 速率限制（certbot 连续失败必踩）**：同一域名 1h 内 **5 次验证失败**即触发 `too many failed authorizations for "<域名>" in the last 1h`，报错里会给 `retry after <UTC时间>`——**别在窗口内反复重试**（每次失败都刷新计数），等窗口过了再试；调试验证配置时用 `--dry-run`（不计数）或先本地 curl 确认 challenge 文件可达再正式跑。

**Caddy 下 certbot webroot 挑战的 308 陷阱**：Caddy 默认把 80 端口请求 301/308 重定向到 HTTPS → challenge 请求被重定向、验证失败（`Invalid response from http://域名/.well-known/acme-challenge/...`）。修复：Caddyfile 加**独立明文 80 块**（`http://域名 { root * <webroot>; file_server }`），仅 80 端口、不重定向，challenge 文件直接可达；验证 `curl -s http://域名/.well-known/acme-challenge/probe -H 'Host: 域名'` 返回 404（文件不存在但到达 webroot）而非 308 即成功。Caddy 自动签发的证书默认 ECDSA（`key_type rsa` 不支持），微信 X5/支付服务器要求 RSA 时必须 certbot 单独签 + Caddy `tls 证书路径` 手动指定（见上节）。

## SSH 远程命令嵌套引号被本地 shell 吃掉 ⚠️

`ssh host "cmd && python3 - <<'EOF' ... \"双引号\" ... EOF"` 这类命令里，**内嵌双引号会终止本地外层双引号字符串** → 远程收到时引号已丢（实测：nginx `add_header Cache-Control "no-cache, max-age=0"` 变无引号 → `invalid parameter "max-age=0"`；python heredoc 报 `SyntaxError: unterminated triple-quoted string`）。**涉及引号的远程文件修改一律本地编辑 → `scp` 回传 → 远程 `nginx -t && reload` 验证**，别用嵌套 heredoc/双引号包裹。

## nginx add_header 继承陷阱：location 级覆盖 server 级 ⚠️

location 块内一旦出现 `add_header`，**server 级的全部 add_header 不再继承**——HSTS / X-Frame-Options / X-Content-Type-Options / Referrer-Policy 全丢（实测给 `location = /index.html` 加 `Cache-Control` 后安全头消失）。给任何 location 加缓存/自定义头时，必须把 server 级安全头一并复制进该 location：

```nginx
location = /index.html {
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Cache-Control "no-cache, max-age=0";
    expires 0;
}
```
（该块同时解决微信 WebView 缓存旧 index.html → 加载旧 JS 的问题——部署新版后微信里看不到新逻辑的隐形元凶）
验证：`curl -skI https://域名/ | grep -iE 'strict-transport|x-frame|x-content|referrer|cache-control'` 必须全在。

## 业务端口内网化统一入口架构（Caddy/nginx Host 分流）⚠️

**演进结论（2026-08 Server A 实测）**：iptables 来源白名单加固（见上节第 8 条）仍可能被**云安全组**拦截业务端口——判定方法：A 上 `sudo tcpdump -i any -nn 'tcp port 5002 and tcp[tcpflags] & tcp-syn != 0'`，同时外部发起连接；**抓到 SYN = iptables 层问题，一个都抓不到 = 安全组在 hypervisor 层拦截**（本机 iptables 再对也没用）。腾讯云同地域实例互访公网 IP 可能走内网链路绕过公网安全组，造成"时通时不通"假象。

**根治架构**：业务端口全部绑 127.0.0.1（socket 层不可达公网）+ 公网只留 22/80/443 + 统一入口域名按 Host/路径分流，B/E/D 反代全部 IP 直写 443 + SNI。安全组只管 443，业务端口对它透明。实测链路：
```
B/E/D → https://42.193.113.230:443 (SNI: api/pay 域名)
      → Caddy: api.openai2000.cn 按 Host 分流 → dazi→5002, aiweb→5003
               pay.openai2000.cn 的 /pay* 及回调 → 5005
```
要点：
- 5002/5003/5005 改 bind 127.0.0.1 后重启，回环 200 + 公网连不通即成功；微信回调走 Caddy 443→127.0.0.1 回环不受影响
- gunicorn 用 `-c gunicorn.conf.py`（非 systemd）时改 bind 后 kill master PID 再守护模式重启；重启失败先看 `Connection in use` = 旧进程没杀干净
- Caddy `handle_path` 会 strip 前缀、`handle` 保留——支付路径要用 handle 保留 `/pay`
- 加固后必须全站回归：B/E/D 首页、/api/、/pay/ 逐点 200（DNS 缓存未过时用 `--resolve` 强制目标机）

### ⚠️ Caddy 站点按 Host 头精确匹配 — 多 Host 必须列全（数据不显示的隐形元凶）
Caddy 的 site block 按请求 **Host 头精确匹配**：反代请求带 `Host: dazi.openai2000.cn`，若站点只声明 `api.openai2000.cn` → **不匹配任何站点 → 返回 HTTP 200 但 content-length: 0 空 body**，前端数据全丢（用户症状\\"网站能打开但数据不显示\\"）。排查顺序：`curl -i` 看响应头 `content-length: 0`；最小配置（无 handle 直反代）正常、加 matcher 分流后空 = 站点 Host 匹配问题，不是 handle 语法问题。
**修复**：站点声明列全所有可能到达的 Host，handle 内用 `@dazi host dazi.openai2000.cn`（host 匹配器，勿用 header Host）按 Host 分流：
```caddy
api.openai2000.cn dazi.openai2000.cn aiweb.openai2000.cn www.ttdazi.xyz {
    @dazi host dazi.openai2000.cn www.ttdazi.xyz
    handle @dazi { reverse_proxy 127.0.0.1:5002 }
    @aiweb host aiweb.openai2000.cn
    handle @aiweb { reverse_proxy 127.0.0.1:5003 }
    handle { reverse_proxy 127.0.0.1:5002 }   # 兜底
}
```
副作用：Caddy 会为列出的每个 Host 尝试 ACME 证书（dazi/aiweb 解析到别的服务器 → 证书获取失败重试，日志噪音），**不影响服务**（反代 SNI 仍用 api/pay 证书）。
**验证纪律**：反代链路测试**必须看 body 字节数**（`curl -s ... | wc -c`）而不只是 http_code——空 body 时状态码仍是 200，只看 code 测不出数据丢失。

完整 Caddyfile / 反代改法 / 验证清单见 📖 `references/nginx-unified-entry-architecture.md`

## 网站系统跨服务器迁移（静态站 + 反代）— 完整流程

源机侦察 → 打包 → 传输 → 部署 → 验证 → 证书续期 → DNS 切换，每步验证再进下一步（2026-08 实测 ttdazi.xyz 国际站 D→E 迁移）：

1. **侦察源机**：`ls /etc/nginx/sites-enabled/` 看配置名；`cat` 配置确认 server_name / SSL 证书路径 / 反代目标 / 是否有后端进程（`ss -tlnp`）；`du -sh` 前端目录
2. **打包**：
   - 前端：`tar czf f.tar.gz --exclude='.bak' -C /var/www 站点目录`（排除历史备份目录省流量）
   - 证书：**必须 `cp -a /etc/letsencrypt /tmp/le_copy` 再 tar**（live/ 是符号链接指向 archive/，cp -a 保留结构，nginx 和 certbot renewal 都依赖这套结构；直接 `tar -h` 会把符号链接打成普通文件也能用但丢结构）
   - nginx 配置：单独 `cp sites-available/xxx /tmp/` 一份
3. **传输**：小文件（<100K）直接 scp；大文件见上节"跨地域大文件传输"（分块 / 海外直连 / 一次性密钥）
4. **目标机部署**：
   ```bash
   tar xzf f.tar.gz -C /var/www && chown -R www-data:www-data /var/www/站点
   mkdir -p /etc/letsencrypt && cp -a /tmp/le_extract/le_copy/. /etc/letsencrypt/
   chmod 600 /etc/letsencrypt/archive/*/privkey*.pem
   cp conf /etc/nginx/sites-available/xxx && ln -sf ... sites-enabled/ && rm -f sites-enabled/default
   nginx -t && systemctl reload nginx
   ```
5. **验证（绕 DNS 直连）**：目标机上 `curl -sk --resolve 域名:443:127.0.0.1 https://域名/` 看 200；外部 `curl -sk --resolve 域名:443:新IP https://域名/`；逐项测：页面标题、`/api/` 反代返回 JSON、静态资源 200、根域名 301（记得补根域名 443 server 块做 301，很多配置只写了 www）
6. **证书续期（必做，防 90 天到期网站挂）**：目标机 `apt install certbot python3-certbot-nginx`（Ubuntu 自动装 certbot.timer 每天跑）；`certbot renew --dry-run` 必须成功——**DNS 指向新机后 nginx 插件才能完成验证**，若报 "Another instance of Certbot is already running" 先 `ps aux | grep certbot` + `kill -9` 清孤儿；确认 `systemctl is-enabled certbot.timer`
7. **DNS 切换**：用户在注册商面板改 A 记录后按三层验证——①权威 NS 直查（`dig +noall +answer 域名 A @ns1.dnsowl.com`，立即生效值）②递归缓存（`dig +short 域名 A @8.8.8.8`）③实际访问（`curl -w '%{remote_ip}'`）；本机缓存 `sudo resolvectl flush-caches` 刷新；**全球 TTL 内 8.8.8.8 已新、本机仍旧 = 上游缓存未过期，正常收敛过程，别误判失败**
8. **回滚保障**：源机旧站不删，作为回滚点

## Nginx 恶意流量分流（蜜罐/惩罚节点）⚠️

需求：正常流量留主服务器，恶意流量（爬虫/扫描器/高频攻击）转发到备用服务器承担负载，攻击者无感知（客户端始终 200）。2026-08 实测部署于 www.ttdazi.xyz（E 主 D 罚）：

1. **规则文件放 http 上下文**（`/etc/nginx/conf.d/guard.conf`）：`map $http_user_agent $bad_ua`（curl/wget/python-requests/sqlmap/nikto/zgrab/scrapy/ahrefs 等 20+ 黑名单）+ `map $request_uri $bad_path`（`/.env` `/.git` `*.php` `/wp-*` `/admin` `*.sql` 等）+ `limit_req_zone $binary_remote_addr zone=guard:10m rate=30r/s`
2. **server 块**：`limit_req zone=guard burst=60 nodelay;` + `error_page 503 = @bad_guard;` + `if ($bad_ua = "1") { rewrite ^ /__guard__ last; }`（$bad_path 同理）
3. **转发点**：`location = /__guard__ { internal; proxy_pass https://备用机IP$request_uri; proxy_ssl_verify off; proxy_ssl_server_name on; proxy_ssl_name 域名; proxy_set_header Host 域名; }` + `location @bad_guard { 同样反代 }`
4. ⚠️ **核心坑**：rewrite 目标**不能拼接 `$request_uri`**（`rewrite ^ /__guard__$request_uri last;` 会让 URI 变成 `/__guard__/.env`，**精确匹配 `location = /__guard__` 失败**→落入 SPA 的 `location /` try_files → 报 `rewrite or internal redirection cycle while internally redirecting to /index.html` 500 循环）。正确：`rewrite ^ /__guard__ last;` 固定 URI，`$request_uri` 是只读变量在 proxy_pass 里仍保留原始 URI
5. **验证必须绕过本机 DNS 缓存**（解析切换后本机仍可能指向旧机，测试会全打到旧机造成\"分流没生效\"误判）：`curl --resolve 域名:443:主服务器IP -A 'python-requests/2.31' https://域名/`；确认 D 侧日志出现来自主服务器 IP 的请求（`grep '主IP' 备用机/var/log/nginx/access.log`）= 分流成功；正常 UA 只出现在主服务器日志
6. 限流触发测试：burst=60 时 40 并发不会触发（burst 内全容），用 `seq 1 300 | xargs -P 100 -I {} curl ...` 高并发，error.log 出现 `limiting requests, excess: xx by zone` 且客户端仍全 200（被转发的请求返回 200）
7. ⚠️ **测试请求本身会污染限流 zone → 后续测试被 503 转 D 误判**：limit_req 按 `$binary_remote_addr` 计数，本机/测试机 IP 频繁发测试请求后 zone 计数超标，之后所有请求（含首页静态）503 → error_page 转 D → 若 D 侧异常就全 502。**症状：同一 curl 一会 200 一会 502，error.log 是 `limiting requests` 而非证书错误**。处理：等 zone 恢复（rate=30r/s 的恢复速度，几十秒到几分钟）再测；或 `sudo systemctl reload nginx` 不重置 zone（zone 是共享内存，reload 保留）——真急就用不同源 IP 测。**别把限流 503 误判成证书/网络问题去改配置**（本会话为此白排查了 verify_depth/信任链一轮）
8. **互加 fail2ban 白名单**：主备两机 jail.local 的 ignoreip 互相包含对方 IP，防 E→D 高频转发触发误封
9. ⚠️ **curl 默认 UA 会被恶意 UA 规则转走——测试结果全是"目标服务器旧内容"**：`curl` 默认 UA 是 `curl/x.x`，命中 `$bad_ua` → rewrite /__guard__ → 反代到备用机。症状极具迷惑性：磁盘文件明明是新版（python http.server 起临时端口读同一目录能验证），但 nginx 返回的始终是备用机的旧版；**排查\"nginx 不读磁盘\"类问题时，第一步先确认 curl 带了浏览器 UA**（`-A 'Mozilla/5.0 ...'`）。判别法：`echo 标记 > 磁盘文件` 后 curl 看是否返回标记；把 root 改到只含测试文件的目录看是否生效。本会话 E 机\"返回旧版之谜\"就是 curl 默认 UA 触发分流，白查了 open_file_cache/挂载/多实例一整天
10. **limit_req 白名单（管理 IP/自有服务器不计数）**：nginx 的 limit_req_zone 没有 ignoreip，用 geo+map 空 key 方案——白名单 IP 的 key 为空串，limit_req 对空 key 跳过不计数：
    ```nginx
    geo $is_trusted { default 0; 42.193.113.230 1; 82.157.202.24 1; 165.154.224.225 1; 185.239.224.191 1; }
    map $is_trusted $limit_key { 1 ""; 0 $binary_remote_addr; }
    limit_req_zone $limit_key zone=guard:10m rate=30r/s;
    ```
    ⚠️ ①zone 的 key 表达式变更后 **reload 不重建 zone，必须 restart nginx**；②批量替换插入 geo/map 时用 `str.replace` 会每处插入一份，nginx 允许同名 geo 重复定义（-t 能过）但应清理成一份（按行处理保留第一份）；③各 zone 统一用同一个 `$limit_key` 即可，无需每 zone 一份白名单

完整配置模板 + 提取验证脚本见 📖 `references/nginx-malicious-traffic-shunting.md`

## 全服务器安全巡检流程（2026-08 实测 4 台机）⚠️

用户要求"帮我检索并修复服务器安全"时的标准动作：每台机跑一遍扫描，汇总问题再逐项修复。

**扫描清单（每台机）**：
1. `systemctl is-active fail2ban` + `sudo fail2ban-client status sshd`（看 Currently banned——工作正常应有封禁；Total banned 30+ 属常态）
2. `sudo sshd -T | grep -iE '^(passwordauthentication|pubkeyauthentication|permitrootlogin)'`（应为 no / yes / without-password）
3. `ss -tlnp` 公网监听清单——⚠️ **0.0.0.0 监听 ≠ 公网可达**，必须公网实测：`timeout 4 bash -c "echo > /dev/tcp/公网IP/端口"` 逐端口扫（云安全组才是主防线；本机监听但扫不通=已挡）
4. `apt list --upgradable 2>/dev/null | grep -c upgradable` + `ls /var/run/reboot-required`
5. 爆破：`grep 'Failed password' /var/log/auth.log | grep -oE 'from [0-9.]+' | sort|uniq -c|sort -rn|head -5`
6. 挖矿进程：`ps aux | grep -iE 'xmrig|minerd|kinsing'`；⚠️ **`[kdevtmpfs]` 带方括号 = 内核线程，正常**（无括号才可疑）
7. 用户审计：`awk -F: '$3==0{print $1}' /etc/passwd`（应只有 root）+ `grep useradd /var/log/auth.log | tail`（新用户要问用户来历，如 aiecom 跑 PM2+Next.js 属用户 AI 应用非恶意）
8. **authorized_keys 全查**：各机 `cat ~/.ssh/authorized_keys | awk '{print $1,$3}'`——发现 `skey-` 前缀 RSA 密钥 = 某工具密钥，**来历不明需向用户确认**（不在本机私钥库 = 风险点，确认后建议移除）
9. /tmp sticky（drwxrwxrwt）、cron.d 异常、nginx server_tokens

**修复注意**：
- ⚠️ **agent 被硬性禁止执行 reboot**（unconditional blocklist）→ apt upgrade 后 REBOOT_REQUIRED 只能给用户指引手动重启（`sudo reboot` / `ssh root@IP 'reboot'`），重启后回归验证服务
- Ubuntu phasing：upgrade 后剩余少量 `deferred due to phasing` 包属正常分批发布，非故障
- 纵深防御：业务端口即使安全组已挡也可绑 127.0.0.1——改 `app.listen(PORT, '127.0.0.1')` 后 nginx 反代 127.0.0.1:8081 不受影响，公网直连彻底关闭
- 升级大动作（核心服务器 100+ 包）用 `background=true + notify_on_complete=true`，升级后自动跑服务健康检查（mysql/caddy/各端口 health 全 200）
- 扫描脚本可复用：📖 `scripts/security-scan.sh`（fail2ban→sshd→端口→更新→爆破→进程→用户→authorized_keys→cron 全项输出，scp 到目标机 `sudo bash` 执行）



上架/迁移后验证线路质量：ITDog（itdog.cn）提供全国 200+ 节点的 ICMP ping / TCP ping / HTTP 测速，免费免登录：

1. 浏览器打开 `https://www.itdog.cn/tcping/域名:443`（或 `/ping/域名`、`/http/域名`），**URL 带参数会自动触发测试**
2. ⚠️ **页面首屏汇总数据是缓存假数据**（实测显示\"中国香港 2ms\"\"广东中山 9ms\"——到东京不可能），必须**点击\"单次测试\"重新触发**，等 1-2 分钟再提取
3. 提取：`browser_console` 执行 JS 抓表格行（td 含 `ms` 后缀的节点行），按省份映射区域 + 按运营商分组，统计中位数/均值/异常数（>500ms）
4. 解读：正常 50-100ms；电信偶发 1.0-1.1s 异常节点（湖南/河南/湖北/四川/甘肃/辽宁等省家庭节点）是**电信国际出口线路问题，非服务器问题**（同测联通/移动全程正常即可佐证）；港澳台 4ms 但全国 230ms+ = 服务器物理位置近但国内线路绕路
5. 测 IP 用 `165.154.224.225:443` 格式；对比两台服务器用同一批节点才有意义

提取统计的 JS 代码见 📖 `references/site-latency-testing.md`

## Ops自治引擎 — YAML规则驱动自动检测+修复（2026-08-29 部署）

**架构**：Python引擎常驻(systemd) → 每60秒扫描YAML规则 → 自动检测+自动修复 → 只在升级时通知Hermes。
**省token**：routine操作0 token，只在Python无法处理时升级给Hermes（~97% token节省）。

```
/opt/ttdazi/ops/
├── engine.py              # 自治引擎（systemd: ops-engine.service）
├── rules/                 # YAML规则库（声明式，新增规则无需重启引擎）
│   ├── services.yaml      # 5条：后端/支付/AI/MySQL/Caddy存活+自动重启
│   ├── security.yaml      # 3条：SSH爆破封禁/恶意进程/磁盘清理
│   ├── ssl.yaml           # 1条：4域名证书≤14天到期预警
│   ├── database.yaml      # 2条：连接数/碎片自动优化
│   └── finance.yaml       # 3条：负余额/大额/重复订单
├── state/                 # 状态（counters.json/escalation.json）
└── logs/                  # 执行日志（JSONL+摘要）
```

**常用命令**：
```bash
python3 /opt/ttdazi/ops/engine.py              # 单次执行
python3 /opt/ttdazi/ops/engine.py --daemon     # 守护模式
python3 /opt/ttdazi/ops/engine.py --status     # 查看状态
python3 /opt/ttdazi/ops/engine.py --rule services.yaml  # 测试单规则
sudo systemctl restart ops-engine              # 重启引擎
cat /opt/ttdazi/ops/state/escalation.json      # 查看升级队列
```

**YAML规则格式**：规则文件在 `rules/` 下，引擎每周期自动加载（无需重启）。规则结构：
- `check`: 检查类型（http/command/systemd/disk_usage/ssl）+ 参数
- `actions`: 动作列表（restart_systemd/cleanup/block_ip_top/optimize_db/notify/log_event）
- 关键参数：`cooldown`（冷却时间防重复触发）、`max_retries`（最大重试）、`on_failure: escalate`（失败升级）

**⚠️ check逻辑是反转的**：command类型检查中，条件**满足**=有问题(fail)，条件**不满足**=正常(pass)。即 `operator: ">=" threshold: 1` 表示"有>=1个就告警"，0个=正常。这是反直觉的——写规则时注意。

**升级机制**：Python无法处理的问题写入 `state/escalation.json`，Hermes cron可读取该文件决定是否通知用户。

完整架构和规则模板见 📖 `references/ops-engine-architecture.md`。

## pymysql DictCursor + information_schema 列名大小写陷阱 ⚠️

pymysql DictCursor 查询 `information_schema` 时返回**大写列名**（`TABLE_NAME` 而非 `table_name`），但查询普通表时返回**小写**。同一连接内不一致，极易 KeyError。

**修复**：information_schema 查询用别名强制小写：
```sql
SELECT TABLE_NAME as tname, TABLE_ROWS as trows,
       ROUND(DATA_LENGTH/1024/1024, 2) as data_mb
FROM information_schema.tables WHERE table_schema = %s
```
然后用 `t['tname']` 而非 `t['table_name']`。其他表正常用小写列名。

## Server A 数据库列名实测（2026-08-29）

| 表 | 易错列名 | 实际列名 |
|---|---|---|
| money_log | order_id | relate_id |
| withdraw | user_id | companion_id（需JOIN companion表取user_id） |
| software_auth.app_order | created_at | create_time |
| software_auth.app_user | vip_expire | vip_expire_time |
| information_schema.* | table_name | TABLE_NAME（DictCursor大写） |

写SQL前先 `DESCRIBE table_name` 确认列名，别凭经验猜。

## 验证纪律
- 交付结论前必须实测：连上返回 hostname、备份文件真实存在于目标盘
- 报"备份修复完成"前，手动执行一次脚本看日志确认路径，而不是只看 sed 改没改
