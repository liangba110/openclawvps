# 新项目端口不可达排错

## 现象
- `curl http://127.0.0.1:新端口` ✅ 通
- `curl http://公网IP:新端口` ❌ 不通
- Server B 连 Server A 新端口 ❌ 不通

## 排查步骤

```bash
# 1. 检查端口监听（Server A 上执行）
sudo ss -tlnp | grep 新端口

# 2. 检查 iptables 规则
sudo iptables -L INPUT -n | grep 新端口

# 3. 如果 iptables 有规则但公网不通 → 云安全组拦截
#    表现：curl http://127.0.0.1:新端口 ✅ 通
#          curl http://公网IP:新端口 ❌ 不通
#    解决：腾讯云控制台 → 安全组 → 添加入站规则（TCP:新端口）

# 4. 测试 Server B 连通性
ssh ubuntu@82.157.202.24 "curl -s --connect-timeout 5 http://42.193.113.230:新端口/api/health"
```

## 已知开放端口
| 端口 | 用途 | 开放范围 |
|:----:|:----|:--------:|
| 22 | SSH | 所有 |
| 80 | HTTP (Caddy) | 所有 |
| 443 | HTTPS (Caddy) | 所有 |
| 5002 | ttdazi 后端 | Server B 专用 |
| 5003 | aiweb 后端 | 所有（已添加） |
| 5005 | 支付系统 | 所有 |
| 8080 | HTTP server | 所有 |
