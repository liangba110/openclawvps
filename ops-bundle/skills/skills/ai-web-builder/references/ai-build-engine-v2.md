# AI Build Engine v2 - 架构文档

## 文件结构

- `backend/app/ai_build.py` — 生成引擎（行业检测 + API调用 + 智能模板 + 精化）
- `backend/app/publish.py` — HTML 渲染引擎（内联CSS + 13种组件渲染器）

## ai_build.py 核心流程

```
generate_site(prompt)
  → detect_industry(prompt)  # 14行业关键词匹配
  → call_ai_api()            # DeepSeek API（有Key时）
  → gen_mock_site()          # 智能模板（无Key时）
    → gen_home_components()
    → gen_about_components()
    → gen_service_components()
    → gen_news_components()
    → gen_contact_components()
    → gen_admin_panel()
```

## 行业检测

14 个行业，每个有 icon + keywords 列表。检测逻辑: `any(kw in prompt for kw in keywords)`。

## 生成多样性（随机化引擎）

### 首页组件随机化

`gen_home_components()` 使用以下策略确保每次生成不一样：

| 策略 | 实现 |
|:----|:------|
| 标语随机 | `SLOGANS` 字典每行业多条，用 `pick()` 随机选 |
| 功能点随机 | `features` 列表 `random.shuffle()` 后取前3~4 |
| 组件组合随机 | hero始终在首，cta始终在尾，中间组件顺序 `random.shuffle()` |
| 组件出现概率 | features 100%、showcase 70%、testimonials 60%、stats 50% |
| 统计数字行业化 | 餐饮→合作餐厅、宠物→服务宠物、教育→培训学员 |
| 按钮文字随机 | `pick(['了解更多','免费咨询','立即体验'])` |
| 标题文案随机 | `pick(['我们的优势','为什么选择我们','核心价值'])` |

### 页面数量随机化

| 条件 | 页面 |
|:----|:-----|
| 始终存在 | 首页、关于我们、最新动态、联系我们 |
| 80%概率 | 服务项目 |
| 50%概率 | 案例展示 |
| 含"商城/电商"关键词 | 在线商城 |
| 非首页页面顺序 | `random.shuffle()` |

前端传入 `action=refine` + `current_result` + 反馈文字:
1. 尝试调用 DeepSeek API 用 `AI_REFINE_PROMPT` 修改
2. API 不可用时走 `modify_result()` 简单规则（颜色关键词匹配、名称替换）

## HTML 渲染引擎

### 导航锚点生成

导航链接使用页面 slug 作为锚点（`<a href="#about">关于我们</a>`），因此 `generate_html()` 中必须为每个页面的第一个 `<section>` 添加 `id` 属性：

```python
for page in pages:
    page_id = page.get('slug', 'page')
    for i, comp in enumerate(page.get('components', [])):
        r = RENDERERS.get(comp['type'])
        if r:
            comp_html = r(comp['props'])
            if i == 0:
                comp_html = comp_html.replace('<section', f'<section id="{page_id}"', 1)
            content += comp_html
```

CSS 中需添加 `scroll-margin-top` 补偿固定导航栏：

```css
section { scroll-margin-top: 70px; }
```

### CSS 模板变量

| 变量 | 说明 | 来源 |
|:----|:------|:------|
| `{ff}` | font_family | `theme.font_family` |
| `{p}`  | primary_color | `theme.primary_color` |

### 渲染函数注册表

```python
RENDERERS = {
    'hero': render_hero, 'features': render_features, 'showcase': render_showcase,
    'testimonials': render_testimonials, 'cta': render_cta, 'page_header': render_page_header,
    'about': render_about, 'team': render_team, 'services': render_services,
    'pricing': render_pricing, 'blog': render_blog, 'contact': render_contact,
    'contact_info': render_contact, 'footer': render_footer,
}
```

每个渲染函数接收 `props` 字典，返回 HTML 字符串。使用 `h()` 转义函数防止 XSS。

## API 路由

| 方法 | 路径 | 说明 |
|:----|:-----|:------|
| POST | `/api/ai/generate` | 生成/精化网站（需登录） |
| GET | `/api/ai/conversations` | 查询对话历史（需登录） |
| POST | `/api/publish/preview` | 生成预览HTML（需登录） |
| GET | `/api/publish/view/<filename>` | 查看预览HTML（公开） |
| POST | `/api/publish/deploy` | 部署到Server B（需登录） |

## 关键陷阱

1. **render_hero 的 `.format()` 必须包含 `btn=btn`** — 变量在字符串中被引用但没传参会 KeyError
2. **render_cta 同样需要 `btn=btn`**
3. **f-string 中不能有反斜杠** — `f'<span class="tag">{t}</span>'` 会报错，改用 ''.join()
4. **预览页 `conversations` API 必须 SELECT `response` 字段** — 否则 previewHtml 为 undefined
