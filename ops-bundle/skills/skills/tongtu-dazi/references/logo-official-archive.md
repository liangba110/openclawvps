# 同途搭子 官方品牌 Logo 全套（2026-08-03 最终定稿）

## 结论先行

用户最终确认的官方全套在 **`/brand/` 目录**（展示页 `dazi.openai2000.cn/brand/logo-showcase.html`），不是早前的 6 张 `img_*.png` 方案。**所有站点换版一律用 brand 全套**。搭字版/菱形元素版均已被官方全套取代（用户直接提供了全套资源）。

## 资源位置（45 文件）

| 位置 | 路径 |
|---|---|
| 权威源 | Server B `/home/ubuntu/ttdazi-frontend/brand/` |
| 永久存档 | Server A `/opt/ttdazi/logo-official/full-set/`（随每日备份到 /data/disk） |
| 本机镜像 | `~/ttdazi_logo_official/full-set/` |
| 线上前端 | 主站+国际站 `public/brand/`（构建后 `dist/brand/`） |

## 文件清单

- **主 logo**：`logo-horizontal.png`（**最新版 635×220**，早前 880×340 已被替换，md5 `e5f2034d68cb`）、`logo-vertical.png`、`logo-master.svg/png`（蓝紫渐变+搭字+白色圆环，PingFang/Noto/微软雅黑 900 字重）
- **应用图标**：`logo_512.png`、`logo-square.png`、`icon_1024/512/192/180/167/152/144/120/96/72/48/40/32/16.png`
- **网站图标**：`favicon.ico`、`favicon_16~256.png`
- **微信**：`wx_avatar_48/64/96/132/200.png`、`wx_square_120/240.png`、`mp_icon_36~144.png`（小程序）
- **展示/打包**：`logo-showcase.html`、`同途搭子-全套Logo.zip`

## 各页面引用（已上线）

| 页面 | 引用 |
|---|---|
| Home.vue 导航栏 | `/brand/logo-horizontal.png`，`.logo-img { height:42px; max-width:180px }` |
| Login.vue | `/brand/logo-horizontal.png`，`.logo-img { width:150px; max-width:60%; height:auto }`（**用户嫌 200px 大，调为 150px**） |
| pay.html（支付服务 5005） | base64 data URI（icon_512.png 69KB）——5005 无静态路由，不能引 /brand/ 路径 |
| index.html favicon | `/brand/favicon_16.png` + apple-touch-icon `/brand/icon_192.png` |
| manifest.json | icons → `/brand/icon_192.png` + `/brand/icon_512.png` |

## 版本差异陷阱

- 2026-08-03 用户更新了 `logo-horizontal.png`（880×340 → 635×220）。**判断新旧**：`md5sum`——最新 `e5f2034d68cb`，旧 `3d2a68039495`。用户说"更新下logo"时先 md5 对比 Server B brand/ 与服务器A public/brand/，不一致才需同步。
- 只改 public/brand 不够，要**重新 npm run build**（asset 路径进 dist）→ 三端同步（Server B + 服务器D + 支付服务模板）。

## 换版流程

1. 新资源放 `public/brand/`（保留文件名，改内容）
2. `npm run build` → 打包 dist → Server B `/home/ubuntu/ttdazi-frontend/` + 服务器D `/var/www/ttdazi/`（分类型 chmod：目录 755 / 文件 644 / chown www-data）
3. pay.html 内联 base64 需单独更新模板 + `kill -HUP $(pgrep -f 'gunicorn -b 0.0.0.0:5005')`
4. 同步到 `/opt/ttdazi/logo-official/full-set/`（Server A 存档）双保险
5. 用户端需清缓存（immutable + hash 文件名，微信内尤甚）

## 设计教训（用户明确纠正）

- ❌ 不要用品牌名首字造符号（「搭」字版被否决：「不是用搭这个字」）
- ✅ 设计元素 = 用户提供原图里的图形本身（蓝紫渐变方块 + 深灰菱形钻石图案）
- ⚠️ 设计稿**必须先预览（MEDIA 发 PNG 拼图）确认后再替换线上**——用户原话"设计出来我看下，确定没问题再替换"
- ⚠️ 中文 SVG 渲染必须用 PIL + 文泉驿正黑（cairosvg 缺中文字体渲染成豆腐块乱码，见 brand-identity-design pitfalls）
- ⚠️ 用户提到"先前设计的 logo"时先查本存档；`/home/ubuntu/logo`、`logo6`、`logo_v3.svg`、`/opt/aiweb/logo/` 是**汇智云**（☁️云朵+AI）品牌，勿混淆。
