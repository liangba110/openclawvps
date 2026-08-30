# site_config 数据库覆盖 HTML 标题

## 问题

修改 `index.html` 中的 `<title>` 后，浏览器标签页依然显示旧标题。

## 根因

`App.vue` 的 `loadSiteConfig()` 在 `onMounted` 中调用：

```javascript
async function loadSiteConfig() {
  try {
    const r = await api.get('/config/list')
    if (r) {
      const name = r.site_name?.value
      if (name) document.title = name    // ← 数据库值覆盖 HTML <title>
      const color = r.primary_color?.value
      if (color) document.documentElement.style.setProperty('--primary-color', color)
    }
  } catch(e) {}
}
```

因此网站标题的最终来源是 `site_config` 表的 `site_name` 行，不是 `index.html`。

## 修复

直接更新数据库：

```sql
UPDATE site_config SET value='新标题' WHERE `key`='site_name';
UPDATE site_config SET value='新副标题' WHERE `key`='site_subtitle';
```

刷新页面后生效（无需重启后端）。

## 相关字段

| key | 作用 | 
|-----|------|
| `site_name` | 浏览器标签页标题 + 可能用于分享卡片 |
| `site_subtitle` | 网站副标题（某些页面展示） |
| `primary_color` | CSS 变量 `--primary-color`，覆盖主题色 |

## 验证

```bash
curl -s http://127.0.0.1:5002/api/config/list | python3 -c "
import json,sys
d = json.load(sys.stdin)
for k in ['site_name','site_subtitle','primary_color']:
    if k in d.get('data',{}):
        print(f'{k}: {d[\"data\"][k][\"value\"]}')
"
```
