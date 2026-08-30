# Server B Baota 宝塔面板运维

## 架构

- **面板端口**: 30551（配置在 `/www/server/panel/data/port.pl`）
- **安全入口**: `/95fe9adb`（配置在 `admin_path.pl`）
- **面板服务**: `Bt-Panel` + `Bt-Task`
- **控制命令**: `sudo bt`（交互菜单）
- **获取登录信息**: `sudo bt default`
- **重置密码**: `echo '新密码' | sudo bt 5`
- **重置安全入口**: `echo '/' | sudo bt 12`
- **Nginx 代理入口**: `https://openai2000.cn/bt/`（huizhiyunma 站点配置）

## 🔴 常见问题

### Python 3.7 环境被删除（磁盘清理后）

**症状**: Bt-Panel 进程运行但所有页面返回 404（显示 nginx 样式 404 页）。
日志报: `ModuleNotFoundError: No module named 'psutil'` 或 `No module named 'six'`

**根因**: 宝塔面板依赖独立的 Python 3.7 虚拟环境（`/www/server/panel/pyenv/`）。
磁盘清理时若删除了该目录，面板无法加载路由和模板。

**恢复步骤**:

```bash
# 1. 安装 Python 3.7（Ubuntu 24.04 需 deadsnakes PPA）
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.7 python3.7-venv

# 2. 重建虚拟环境
sudo rm -rf /www/server/panel/pyenv
sudo python3.7 -m venv /www/server/panel/pyenv
sudo chmod -R 755 /www/server/panel/pyenv

# 3. 安装面板所需依赖
sudo /www/server/panel/pyenv/bin/pip install --upgrade pip setuptools wheel
sudo /www/server/panel/pyenv/bin/pip install psutil flask pyinotify flask-REDACTED \
  gevent gevent-websocket requests six 'urllib3<2' cryptography pyOpenSSL

# 4. 更新面板（下载完整包恢复模板和配置文件）
curl -skO https://download.bt.cn/install/update_panel.sh
sudo bash update_panel.sh

# 5. 重启面板
sudo /etc/init.d/bt restart
```

### iptables 拦截端口

面板监听 30551，需确保 iptables 放行：
```bash
sudo iptables -A INPUT -p tcp --dport 30551 -j ACCEPT
```

### Nginx 冲突

Server B 上的 Nginx 监听 8888 端口（bt-panel 配置），不要与面板端口混淆。
面板通过 `https://openai2000.cn/bt/` 路径访问（Nginx 反向代理）。

### 面板数据库

路径: `/www/server/panel/data/default.db`（SQLite）
表: users, config, sites, ftps, databases, crontab, firewall, logs, tasks, domain
