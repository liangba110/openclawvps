# 为用户配置个人 SSH 访问（非技术用户 + Trae/SFTP）

场景：用户要在自己电脑上用 Trae IDE / WinSCP / Xftp 连服务器。用户是**非技术用户**（Windows，不会命令行），需要傻瓜式步骤，不能只甩一句 ssh-keygen。

## 关键前置：确认服务器认证模式
```bash
grep -iE '^PasswordAuthentication' /etc/ssh/sshd_config
```
- `PasswordAuthentication no`（Server A 现状）= 纯密钥登录，**用户用密码连 SFTP 必失败**，必须先配密钥
- 步骤顺序：用户生成密钥 → 公钥发我 → 我加入 authorized_keys → 用户才能连

## 傻瓜式步骤（给用户的文案，Windows）

**第1步**：按键盘 `Win` 键 → 输入 `powershell` → 回车，打开蓝色窗口

**第2步**：粘贴下面整行，回车（会问问题，**连续按 3 次回车**）：
```
ssh-keygen -t ed25519 -C "ubuntu-sftp" -f $env:USERPROFILE\.ssh\id_sftpa
```

**第3步**：再粘贴这行，回车：
```
Get-Content $env:USERPROFILE\.ssh\id_sftpa.pub
```

**第4步**：屏幕上显示 `ssh-ed25519 AAAA...` 开头的一行，**整行复制发给 agent**。

> 报错（如"文件已存在"）→ 换备用方案：agent 在服务器生成密钥对，打包 zip 用 MEDIA 附件发用户（私钥内容会被安全机制脱敏，不能直接 cat 发文本）。

## Agent 侧：添加用户公钥
```bash
echo 'ssh-ed25519 AAAA... ubuntu-sftp' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
ssh-keygen -lf ~/.ssh/authorized_keys   # 验证新增行（指纹 + 注释名）
```

## Trae 连接配置（用户侧）
**方法一（推荐）：~/.ssh/config 别名**
用户在自己电脑建 `C:\Users\<用户名>\.ssh\config`（无扩展名，记事本打开 `.ssh` 文件夹新建文本文件改名），粘贴：
```ini
Host ttdazi-a
    HostName 42.193.113.230
    User ubuntu
    Port 22
    IdentityFile ~/.ssh/id_sftpa
```
Trae 打开远程资源管理器 → 添加 SSH 主机 → 输 `ttdazi-a` → 回车连接。首次连接输 `yes` 确认指纹。

**方法二：直接连接串**
```
ssh -i ~/.ssh/id_sftpa ubuntu@42.193.113.230
```

## WinSCP/Xftp（SFTP 图形化）
- 协议 SFTP、主机 IP、端口 22、用户 ubuntu、认证选**密钥文件**（WinSCP 需 PuTTYgen 把私钥转 .ppk：Load 私钥 → Save private key）

## 验证
- 添加后从服务器本机无法测用户私钥，只能：① `ssh-keygen -lf` 确认公钥格式有效解析 ② 让用户实际连一次反馈
- 用户报错时先确认：私钥文件路径对、config 无 BOM/扩展名问题（Windows 记事本建 config 可能存成 .txt，需确认无扩展名）

## "用户连不上" — 先做服务器侧诊断（别急着改配置）⚠️（2026-08-28 实测）

用户说"还是连不上"时，**先在服务器侧确认连接是否真的到达**，再判断是用户配置问题还是密钥问题：

```bash
# 1. 看最近有没有连接尝试、是否 Accepted（成功）还是 Failed（失败）
sudo journalctl -u ssh --since '30 min ago' | grep -iE 'Accepted|Failed|Connection' | tail -20
# 2. 确认用户 IP 没被 fail2ban 误封（用户连不上第一嫌疑）
sudo fail2ban-client status sshd | grep -iE 'banned|currently'
# 3. 当前活跃会话
who
```

- `journalctl` 里 **没有任何来自用户 IP 的条目** → 用户根本没发起连接（Trae 只保存了主机配置没点连接 / 本地网络问题），不是密钥问题，让用户检查操作
- 有 `Connection closed by authenticating user ubuntu <用户IP>`（preauth）→ 认证失败，回退查密钥是否配对
- 有 Failed → 私钥没匹配上（路径不对/密钥不配对），不是服务器拒绝
- fail2ban 只显示攻击者 IP 时，明确告知用户**你的 IP 没被封**，排除误封疑虑
- 注意日志里刷屏的 `authenticating user root 110.x`（爆破者）是常态噪音，别当用户连接

## GitHub SSH 密钥 ≠ 服务器密钥 ⚠️（2026-08-28 实测混淆）

用户会把 GitHub 的 SSH 公钥（`ssh-ed25519 AAAA... 邮箱@qq.com`，注释常带 github/邮箱）发来当服务器访问密钥。要点：

- **GitHub 公钥是配置在 GitHub 网站上的**（GitHub → Settings → SSH keys），用途是让 GitHub 验证你的电脑；**加到服务器 authorized_keys 无意义**（对应私钥未必在本机，就算在也不是用户本意）
- 收到带 `github`/邮箱注释的公钥 → 先确认用户意图：发错了（忽略）还是真想让该密钥能连服务器（需对应私钥在本机才行）
- **"让服务器 A 能 push 到用户的 GitHub 仓库"需要的是用户 GitHub 密钥的私钥**（`-----BEGIN OPENSSH PRIVATE KEY-----` 开头），不是公钥——公钥在服务器上毫无用处。用户发公钥过来时明确告知：需要私钥内容（PowerShell：`Get-Content ~/.ssh/id_ed25519`），并提示私钥=密码、配置后建议本地轮换
- 服务器到 GitHub 连通性测试（未配密钥时预期结果）：
  ```bash
  curl -sI https://github.com | head -1                 # HTTP/2 200 = 网络通
  timeout 8 bash -c 'echo > /dev/tcp/ssh.github.com/443' && echo 'TCP 通'  # 443 可达
  ssh -o BatchMode=yes -T git@github.com 2>&1           # "Permission denied (publickey)" = 网络通但无密钥，正常预期
  ```
  网络通 + `Permission denied (publickey)` = 只差部署私钥，不是网络/账号问题。
