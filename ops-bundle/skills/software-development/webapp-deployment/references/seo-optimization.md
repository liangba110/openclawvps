# SPA 网站 SEO 优化要点（Vue + Nginx）

## 适用场景

新站点上线时需要被百度、头条搜索等中文搜索引擎收录和获得自然流量。

## 基础 SEO 配置

### 1. index.html 元标签

```html
<title>品牌名 — 核心关键词 | 辅助关键词</title>
<meta name="description" content="一句话描述：包含核心业务关键词+行业词，120字以内">
<meta name="keywords" content="品牌词,核心业务词,行业词,长尾词">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://域名" />
```

**Title 公式**：`品牌词 + 核心业务词 — 长尾关键词 | 辅助说明`  
**Description 公式**：`品牌介绍 + 核心卖点 + 覆盖行业 + 行动号召`

### 2. Open Graph（微信/社交分享）

```html
<meta property="og:title" content="分享标题" />
<meta property="og:description" content="分享描述" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://域名" />
<meta property="og:site_name" content="站点名称" />
```

### 3. 结构化数据 JSON-LD（百度富摘要）

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "产品名",
  "applicationCategory": "WebApplication",
  "description": "产品描述",
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "CNY" }
}
</script>
```

常用 type：`SoftwareApplication`（工具类）、`Organization`（企业）、`WebSite`（网站）

### 4. robots.txt + sitemap.xml

public/robots.txt:
```
User-agent: *
Allow: /
Sitemap: https://域名/sitemap.xml
```

public/sitemap.xml:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://域名/</loc>
    <lastmod>2026-07-25</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
```

> Vite `public/` 文件自动复制到 `dist/`。部署后检查权限：`chmod 644`（Nginx 以 www-data 运行）。

### 5. Favicon

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<link rel="apple-touch-icon" href="/favicon.svg" />
```

SVG favicon 放 `public/favicon.svg`。

## 页面内容 SEO

### 首页内容结构

```
H1: 核心标题（含关键词）
H2: 为什么选择我们？（含业务关键词）
H3: 具体特性/功能名称
H2: 适用行业（关键词矩阵）
H2: 常见问题 FAQ（覆盖长尾搜索词）
H3: 问题句式（如"AI建站需要会编程吗？"）
```

### FAQ 模块对 SEO 特别重要

百度等搜索引擎会将 FAQ 直接展示在搜索结果中。每对 Q&A 应使用用户真实搜索句式。

### 页脚关键词

页脚文字是百度计算相关性的信号：
```
<p>© 2026 品牌名 — 核心业务描述 | 关键词1 | 关键词2</p>
```

## Nginx 优化

```nginx
# server block 中添加
add_header Last-Modified $date_gmt always;
```

## 搜索引擎提交

1. **百度搜索资源平台** (ziyuan.baidu.com)：验证站点 → 提交 sitemap
2. **头条搜索** (zhanzhang.toutiao.com)：类似流程
3. 验证 meta 标签：`<meta name="baidu-site-verification" content="code-xxx" />`

## Pitfalls

- **Hash路由 SPA 局限**：Vue hash 模式只索引首页，内部页面需 SSR/预渲染。首页 SEO 仍有效。
- **权限问题**：Vite 构建后 public 文件权限 600（仅 owner 可读），Nginx 以 www-data 运行需 `chmod 644`。
- **Nginx 403 for .txt/.xml**：确保没被 `deny all` 规则拦截。
