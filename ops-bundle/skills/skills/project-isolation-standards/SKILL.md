---
name: project-isolation-standards
description: 共享服务器上多项目并行开发的隔离规范。每个新项目必须完全独立，零影响现有系统。
---

# 项目隔离标准

## 铁律

> **新项目严禁修改现有项目的任何代码、数据库、配置和支付系统。**

## 隔离清单

每个新项目必须使用以下维度实现完全隔离：

| 维度 | 旧项目（ttdazi） | 新项目（aiweb） | 下一个项目 |
|:----:|:---------------:|:---------------:|:----------:|
| 📁 **代码目录** | `/opt/ttdazi/` | `/opt/aiweb/` | **新目录** |
| 🗄️ **数据库** | `huizhiyun` | `aiweb` | **新库名** |
| 🔌 **端口** | `5002` | `5003` | **新端口** |
| 🌐 **域名** | `dazi.openai2000.cn` | `aiweb.openai2000.cn` | **新域名/子域名** |
| 📄 **Nginx 配置** | `sites-available/ttdazi` | `sites-available/aiweb` | **新配置** |
| ⚙️ **systemd 服务** | `ttdazi.service` | `aiweb.service` | **新服务名** |
| 🐍 **虚拟环境** | 系统 Python | `/opt/aiweb/venv/` | **新 venv** |

## 启动新项目的步骤

```bash
# 1. 创建独立目录
mkdir -p /opt/新项目名/{backend,frontend,logs,scripts}

# 2. 创建独立数据库
mysql -uroot -p'huizhiyun2026' -e "CREATE DATABASE 新库名 CHARACTER SET utf8mb4"

# 3. 创建独立 Python 虚拟环境
cd /opt/新项目名 && python3 -m venv venv
source venv/bin/activate && pip install flask flask-REDACTED pymysql pyjwt requests gunicorn

# 4. 选择空闲端口（检查现有端口占用）
sudo ss -tlnp | grep -E '5002|5003|5005|8080'

# 5. 放行 iptables（Server A 默认 DROP）
sudo iptables -I INPUT -p tcp -s 82.157.202.24 --dport 新端口 -j ACCEPT
sudo iptables -I INPUT -p tcp -s 0.0.0.0/0 --dport 新端口 -j ACCEPT
# ⚠️ 注意：即使添加了 iptables 规则，腾讯云安全组可能仍会拦截
#    现象：127.0.0.1 通，公网 IP 不通 → 需用户在云控制台放行

# 6. 创建独立的 Nginx 配置 + systemd 服务
#    从 server_b_nginx.conf 或 ttdazi.service 复制修改

# 7. 申请独立 SSL 证书（需先停 Nginx）
ssh ubuntu@82.157.202.24 "sudo systemctl stop nginx"
sudo certbot certonly --standalone -d 新域名 --non-interactive --agree-tos -m admin@openai2000.cn
ssh ubuntu@82.157.202.24 "sudo systemctl start nginx"

# 8. 同步前端到 Server B
rsync -avz --delete /opt/新项目名/frontend/dist/ ubuntu@82.157.202.24:/var/www/新项目名/frontend/dist/
ssh ubuntu@82.157.202.24 "sudo chmod 644 /var/www/新项目名/frontend/dist/*.*"
```

## Server A 现行部署模式（Caddy 统一入口时代，2026-08-28 softapi 实测）⚠️

> 上文的 Nginx/certbot/iptables 流程是旧双服务器架构（B 反代时代）遗留。**当前 Server A 新项目部署已统一走 Caddy**：公网只开 22/80/443，业务端口全绑 127.0.0.1，域名按 Host 分流。新项目**不需要**开新安全组端口、**不需要** iptables、**不需要**手动申请证书（Caddy 自动 ACME）。B 仅做静态/反代。

**实测完整流程（softapi.openai2000.cn，FastAPI 项目）**：

1. **代码目录**：`/opt/<项目>/`（独立，从 GitHub 克隆或上传）
2. **独立数据库**：`mysql -uroot -p'<pass>' < sql/init.sql` 建新库（只含新表，不碰 huizhiyun/aiweb）；确认 `SHOW TABLES`
3. **独立 venv**：`cd /opt/<项目> && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt`；`./venv/bin/python -c 'import 框架; print("OK")'` 验证
4. **独立端口**：`ss -tlnp | grep ':新端口'` 确认空闲（5002/5003/5005/5006 已占用，新项目用 5007+）
5. **systemd 服务**：`/etc/systemd/system/<项目>.service`，监听 **127.0.0.1:新端口**（⚠️ write_file 拒写该路径且 heredoc 被误判为长驻进程 → 先 `write_file` 到 `/tmp/xxx.service` 再 `sudo cp`，详见 webapp-deployment 工具坑）
6. **Caddy 新 site block**（**独立块，不动现有多 Host 块**，改前 `sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak_<项目>`）：
   ```caddy
   <新域名> {
       reverse_proxy 127.0.0.1:<新端口>
   }
   ```
   `sudo caddy validate --config /etc/caddy/Caddyfile` → `sudo systemctl reload caddy`
7. **证书自动签发**：Caddy 在**第一次 HTTPS 请求**时自动 ACME——刚 reload 完 curl 可能返回 000（证书未就绪），等几秒重试；`sudo journalctl -u caddy --since '5 min ago' | grep 'certificate obtained successfully'` 确认签发
8. **全站回归（铁律）**：新站 + 现有全部站点逐个 curl 200：
   ```bash
   for u in "https://<新域名>/" "https://api.openai2000.cn/" "https://www.ttdazi.xyz/" "https://dazi.openai2000.cn/" "https://aiweb.openai2000.cn/" "https://pay.openai2000.cn/"; do
     code=$(curl -s -o /dev/null -w '%{http_code}' -m 8 -A 'Mozilla/5.0' "$u"); echo "$u → $code"
   done
   ```
9. **功能走通测试**：从 `/openapi.json` 列接口 → 注册→登录→核心 API 全链路 curl 验证 → 确认落库 → **清理测试数据**
10. **备份覆盖**：新库加入 `daily_backup.sh` 的 mysqldump 列表

**与旧流程的差异**：①无 iptables/安全组操作（443 已开）②无 certbot 手动申请（Caddy 自动）③无 Server B Nginx 操作 ④新站接统一支付网关时回调前缀路由须新增映射（见 unified-payment-gateway skill）

## 已有基础设施

| 服务器 | IP | 用途 |
|:------:|:---:|:----:|
| A | 42.193.113.230 | Flask 后端 + MySQL + gunicorn |
| B | 82.157.202.24 | Nginx 反代 + 前端静态文件 + SSL |

## 常见陷阱

### 1. iptables/YJ-FIREWALL 放行端口
- Server A 的 iptables 默认策略是 DROP，需要手动放行新端口
- 两步操作：
```bash
sudo iptables -I INPUT -p tcp -s 82.157.202.24 --dport 新端口 -j ACCEPT
sudo iptables -I INPUT -p tcp -s 0.0.0.0/0 --dport 新端口 -j ACCEPT
```
- 即使添加了 iptables 规则，如果云安全组未放行，外部仍不可达（表现为本地 127.0.0.1 通，公网 IP 不通）
- 需要用户在腾讯云控制台安全组中手动添加端口

### 2. 域名解析 + SSL
- 每个独立域名需要单独的 Let's Encrypt 证书
- 申请前需确认 DNS 已解析到 Server B
- 临时停 Nginx -> certbot standalone -> 重启 Nginx

### 3. 前端文件同步
- 在 Server A 构建前端，`rsync` 到 Server B 的 `/var/www/` 下
- 记得 `sudo chown -R ubuntu:ubuntu /var/www/新项目目录`

### 4. 备份覆盖
- 新项目上线后，更新 `daily_backup.sh` 加入新数据库备份
