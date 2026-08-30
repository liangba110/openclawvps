# 品牌文字全站替换（公司名/版权名改版）

场景：把网站上显示的公司/品牌名（如「胶州市汇智云互联网工作室」「汇智云科技」）全站替换为新名（如「同途科技」）。
用户说"网站上所有 X 换成 Y" = 必须覆盖 **前端 + 数据库 + 后端代码**，只改 dist 不算完成。

## 涉及位置清单（ttdazi 项目）

| 位置 | 文件/表 |
|---|---|
| 国际站前端 | 服务器D `/var/www/ttdazi/assets/{About,Agreement,Home,Settings}-*.js`（hash chunk，sed 直接改） |
| 主站前端 dist | 服务器A `/opt/ttdazi/frontend/dist/assets/` 同名 hash 文件（两站构建产物相同，都要改） |
| 主站前端源码 | `/opt/ttdazi/frontend/src/views/{Home,Agreement,Settings,About}.vue`（**必改，否则下次构建回退**） |
| 数据库 | `agreement` 表 `content` 字段（5 条协议页脚如 `汇智云科技 · 同途搭子平台`） |
| 后端代码 | `/opt/ttdazi/backend/app/{faq.py, user.py, wx_code.py, wx_message.py}`（FAQ 回复、验证码消息【汇智云同途搭子】、关注欢迎语） |

## 执行流程

1. **备份先行**：前端 `.bak/` 目录；数据库 `mysqldump -uroot -pXXX huizhiyun agreement > backup_xxx.sql`；后端 `.bak/`。
2. **替换**：sed 逐文件替换。注意变体：`汇智云科技（深圳）有限公司`、`>汇智云科技</`（标签内写法）、`汇智云科技 · 同途搭子` 等，都需覆盖。
3. **残留检查**：`grep -rc '旧名' 目录/ | grep -v ':0'` 应为空（前端 dist、服务器D assets、src、后端 app 四处都要查）。
4. **语法验证**：服务器无 node 时 `scp` 文件到本地 `node --check`；后端 `python3 -m py_compile`。
5. **重启后端**：gunicorn 重启后代码才生效，`ps aux | grep 'gunicorn main:app'` 确认新 PID。
6. **接口验证**：`curl http://127.0.0.1:5002/api/agreement/get?type=user_service` 检查返回 content 无旧名（type 值如 user_service / platform_rules）。

## 坑

- **只改 dist 不改 src** → 下次 `npm run build` 回退旧文案，必须 src + dist 同步。
- **pkill 误杀 SSH**：`pkill -f 'gunicorn main:app'` 会把远程 SSH 会话一起杀掉（本地 exit -15，连接中断）。拆成两条命令执行，断后重连确认进程和健康检查。
- 验证码/客服消息抬头【汇智云同途搭子】要一起换，否则用户收到旧品牌短信。
- 数据库替换用 `UPDATE agreement SET content = REPLACE(content, '旧名', '新名') WHERE content LIKE '%旧名%'`，不要手动改 HTML。
- 协议页接口参数：`agreement.py` 的 `/api/agreement/get` 用 `type=user_service` / `type=platform_rules`（有 TYPE_MAP），传错返回"缺少协议类型"或 code 0。
