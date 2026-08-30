# 前端品牌替换的 hash 缓存坑与重新构建部署流程（2026-08 实测）

## 问题：sed 直接改 dist JS 内容，用户看不到新文案

Vue/Vite 构建产物 chunk 文件名带内容 hash（如 `Home-CsjOjG0H.js`）。
直接 `sed -i` 改文件里的公司名后：
- curl 拉文件内容已是新版 ✅
- 但浏览器/微信仍显示旧版 ❌

原因：Nginx assets 返回 `Cache-Control: public, immutable`（配合 hash 文件名），
文件名没变 → 浏览器认为内容永不变，直接用缓存，永不重新拉取。

## 唯一彻底解法：重新构建，让 hash 变化

构建环境在**服务器A**（42.193.113.230）：
```bash
# 1. 确认 src 已改干净（改 dist 不算，src 才是源）
grep -rn '旧品牌词' /opt/ttdazi/frontend/src/   # 应无输出
# 2. 构建（node v22 + node_modules 已就绪，约 16 秒）
cd /opt/ttdazi/frontend && nohup npm run build > /tmp/ttdazi_build.log 2>&1 &
# 3. 验证新 dist 无残留
grep -rc '旧品牌词' dist/assets/*.js | grep -v ':0'   # 应无输出
```

## 部署三端同步（每端都要做）

| 端 | 目录 | 说明 |
|:---|:-----|:-----|
| 服务器A dist | `/opt/ttdazi/frontend/dist/` | 构建产物，含新 hash chunk |
| 服务器B（主站线上真实服务目录） | `/home/ubuntu/ttdazi-frontend/` | **最容易漏**，主站 dazi.openai2000.cn 实际服务这里 |
| 服务器D（国际站） | `/var/www/ttdazi/` | www.ttdazi.xyz |

服务器A → 服务器B/服务器D 传输：打包 `tar czf /tmp/x.tar.gz -C dist .`
经本地 `/home/ubuntu/transfer/` 中转（本地 /tmp 权限有时拒绝 scp）。
解压替换时**保留 landing.html**（自定义落地页，不在 dist 内）。

## 验证
- 服务器端内容：`curl -sS 域名/assets/Home-xxx.js | grep 新品牌词`
- 浏览器实测页脚：`browser_navigate` 后快照看 `StaticText "同途科技 © 2026"`
- 三站全绿 + 无 JS 错误才算完成
- 用户手机旧缓存：微信退出重进/清缓存，SW 已禁用无需处理 sw.js

## 相关教训
- 主站真正生效的 Nginx 配置是 `sites-enabled/huizhiyunma`（含 dazi server 块），
  不是 `sites-available/ttdazi`（两者并存，改错文件不生效）。记忆口诀"改 huizhiyunma 才持久"。
- 重启 gunicorn 用 `pkill -f 'gunicorn main:app'` 会**误杀 SSH 会话自身**
  （命令行里含同样字符串），exit 130/15 后需要重新连；改用
  `pkill -f 'gunicorn main:app -b'` 精确匹配或按 PID kill。
