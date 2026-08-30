# 域名过期导致网站打不开 — 实战案例（ttdazi.xyz, 2026-08）

## 背景
同途搭子国际站 www.ttdazi.xyz（服务器D 165.154.224.225，阿里云国际）突然全站打不开。
用户报障，最终定位为 **Namecheap 域名 ttdazi.xyz 过期**，而非服务器问题。

## 诊断路径（按序执行，全部实测）
1. `curl -sS -o /dev/null -w "HTTP:%{http_code}" -m 15 https://www.ttdazi.xyz/`
   → `curl: (6) Could not resolve host` + `dig +short www.ttdazi.xyz A` 返回空 = **DNS 层问题**
2. `dig +trace ttdazi.xyz` → 权威 NS 显示 `premium-ns1/2/3.dnsowl.com`（带 NSEC3 NXDOMAIN 签名）
   → **确认域名被 Namecheap 转入过期停放**（dnsowl.com 是 Namecheap 的停放服务）
3. 用 `--resolve` 绕过 DNS 验证服务器：`curl -sk --resolve www.ttdazi.xyz:443:165.154.224.225 https://www.ttdazi.xyz/`
   → HTTP 200，标题 `<title>同途搭子 - 旅游搭子,同城达人</title>` = **服务器完全正常**
4. 结论：等用户续费/赎回域名，DNS 恢复后残留记录需要清理

## 续费后的坑：残留停放 A 记录
域名恢复后，`dig +short www.ttdazi.xyz A` 返回 **4 个 IP**（轮询）：
- `165.154.224.225` ✅ 服务器D（curl 200）
- `45.77.75.133` / `45.77.92.157` / `207.246.78.75` ❌ Vultr 机房 IP，返回 "Welcome to ttdazi.xyz" 停放页

→ 用户访问时 DNS 随机轮询，**时好时坏**：抽中真 IP 正常，抽中停放 IP 打不开。
根因：过期期间 Namecheap 自动生成的停放 A 记录，续费后不会自动删除。

## 解决动作（需要用户操作注册商控制台，不可代理）
1. Namecheap → Domain List → ttdazi.xyz → Advanced DNS
2. 删除指向 Vultr 停放 IP 的 3 条 A 记录，只保留 `www → 165.154.224.225`（根域 `@` 也指向它）
3. Nameservers 改回 Namecheap 默认（`dns1/dns2.registrar-servers.com`）或原 CF CDN NS
   —— 切勿留在 dnsowl 停放 NS

## 验证删除生效 + 缓存滞后（2026-08 实测补充）
- 删除停放记录后，直查权威 NS 验证（带 TTL、不受递归缓存影响）：`dig +noall +answer www.ttdazi.xyz A @ns1.dnsowl.com` → 只剩 `165.154.224.225` 即删除已生效
- 生效≠全网可见：8.8.8.8 已干净时，国内 DNS（223.5.5.5 / 119.29.29.29）仍返回旧停放 IP，**需 1-2h TTL 自然过期**，期间用户时好时坏属正常，告知用户清浏览器缓存/切网络
- 本机 `curl` 超时可能是 systemd-resolved 缓存了过期期间的 NXDOMAIN：`sudo resolvectl flush-caches` 后 `getent hosts` 确认
- 模拟国内用户视角：SSH 到腾讯云服务器（如 Server A 42.193.113.230）执行 `dig @223.5.5.5 www.ttdazi.xyz A` + `curl https://www.ttdazi.xyz/`

## 要点
- 本机 resolv（127.0.0.53）对国外域名经常超时，`dig @8.8.8.8` / `@1.1.1.1` / `@114.114.114.114` 交叉验证最稳
- `--resolve` 直连是"DNS 挂了也想确认服务器是否健康"的利器
- 域名类问题先让用户看控制台状态（Active/Expired/Redemption），别让用户乱点（域名操作不可逆）
- 该域名注册于 Namecheap；若用户提到之前接 CF CDN，NS 应改回 CF 的 NS 而非 Namecheap 默认
