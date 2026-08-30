# 公众号内容站（同途资讯）完整配方

2026-08-05 实测上线：info.openai2000.cn → Server B 纯静态站 /var/www/info-site/
**零数据库、零后端进程、零外部依赖**（微信内加载快、无 CDN 被墙问题、无安全面）。

## 站点结构
```
/var/www/info-site/
├── index.html      # 唯一页面 + SPA 容器 + 固定底部导流条
├── css/style.css   # 移动端优先（max-width 720px 容器，body padding-bottom 76px 给导流条留位）
├── js/data.js      # 全部内容数据（CATS/ARTICLES/TALENTS/DESTINATIONS/SITE）
└── js/app.js       # hash 路由 + 渲染 + 复制导流
```

## 关键实现模式
- **hash 路由**：`location.hash` 解析 → renderHome/renderList/renderDetail/renderAbout，卡片 onclick 直接写 `location.hash='#/article/3'`；hashchange 监听重渲染
- **数据驱动**：内容全部在 data.js 的 JS 对象里，**新增文章 = 编辑 data.js + scp 覆盖**，无需构建/重启
- **零图片占位**：封面/头像/目的地卡全部 emoji + CSS 渐变（linear-gradient 背景 + 大号 emoji 居中），首版零图片依赖；后续真实照片直接换成 `<img>`/背景图
- **复制导流（零跳转，规避微信风控）**：固定底部 cta-bar + 「复制链接」按钮 → `navigator.clipboard.writeText` 失败降级 `execCommand` + 隐藏 textarea；toast「已复制，请打开浏览器访问」。**页面不放任何直接外链**（微信内跳境外未备案域名必触发风控）
- **关联站第三方口径（用户铁律）**：导流目标（www.ttdazi.xyz）文案**严禁**"我们的国际站/上同途搭子国际站"；统一写"更多旅游内容，欢迎访问相关网站"，关于页"以下为第三方网站，与本站无任何关联，请自行判断访问"，免责声明加"本站与任何第三方网站均无关联，不为其内容及服务负责"
- **品牌视觉**：同途紫渐变 #667EEA→#764BA2，白底卡片+圆角 16px+轻阴影；banner 渐变大图 + 装饰 emoji

## 部署流程（Server B，腾讯云境内）
1. `sudo mkdir -p /var/www/info-site && sudo chown ubuntu:ubuntu /var/www/info-site`
2. 本机开发 → `scp -r index.html css js ubuntu@B:/var/www/info-site/`
3. **权限（必做）**：`sudo chown -R www-data:www-data /var/www/info-site && sudo chmod -R 755`（scp 过来默认 600，nginx 读不了 → 403）
4. Nginx conf：80 块（acme-challenge + return 301）+ 443 块（root + try_files）→ sites-available + `ln -sf` → `nginx -t && reload`
5. `sudo certbot --nginx -d info.openai2000.cn --non-interactive --agree-tos --redirect`
6. ⚠️ **certbot 后必须重写 conf**（详见 linux-server-ops「新站点上线」节）：--nginx 会把 80 块的 `return 301` 原样留在 443 块 → 443 自己 301 自己（症状：HEAD 200 但 GET 301）。重写为「443 try_files + 80 return 301」再 reload

## 公众号菜单（API 直改，menu/create 直接生效）
- 一级菜单满 3 个 → 把某级升级为带 sub_button 的二级结构（view 菜单有子菜单后点击只展开不跳转）
- 菜单 URL 必须是**已备案域名**（主域名备案的子域名同主体可用）
- 流程：`GET /cgi-bin/token?grant_type=client_credential&appid=APPID&secret=SECRET` → `POST /cgi-bin/menu/create` → `GET /cgi-bin/menu/get` 验证
- 结构示例：`{"button":[{"name":"同途搭子","sub_button":[{"type":"view","name":"搭子首页","url":"https://dazi.openai2000.cn/landing"},{"type":"view","name":"同途资讯","url":"https://info.openai2000.cn"}]},{"type":"click","name":"获取验证码","key":"GET_VERIFY_CODE"},{"type":"click","name":"业务公告","key":"NOTICE"}]}`

## 验证清单
- Server B 本机：`curl -skI https://域名/` 的 content-length = index.html 真实字节数；css/js 200
- 本机 A 公网：全 200、80→301、`curl -w '%{redirect_url}'` 正确
- 浏览器：线上打开渲染、点文章进详情（hash 正确）、点复制出 toast、**控制台零错误**
- Git 提交（本地 ~/info-site/ 有仓库，commit 记录稳定节点）

## 合规要点（完整版见 SKILL.md 第十一节）
- 站名/分类全用纯内容词，规避微信婚恋/交友联想词（单身/搭子/向导/地陪/结伴/带队全不用）
- 达人简介禁向导/领路字眼 → 「风景分享达人」
- 政策资讯只引用官方来源 + 标注「以官方发布为准」；免责声明页必备
