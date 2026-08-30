# CSS 颜色风格批量替换

## 场景

需要将全站颜色从一套主题切换为另一套（如绿色→紫色），涉及多个 `.vue` 文件中的 CSS 值。

## 推荐方法

使用 `execute_code` 配合 Python 的 `read_file` + 字符串 `replace`，每对颜色替换做一次 `.replace()`。

```python
with open('/path/to/Home.vue', 'r') as f:
    text = f.read()

replacements = [
    ('#11998e', '#667eea'),
    ('#38ef7d', '#764ba2'),
    ('rgba(17,153,142,0.08)', 'rgba(102,126,234,0.08)'),
]

for old, new in replacements:
    text = text.replace(old, new)

with open('/path/to/Home.vue', 'w') as f:
    f.write(text)
```

## 注意事项

1. **精确匹配**：确保旧颜色值不会匹配到注释或字符串中的颜色名
2. **按顺序替换**：如果 `#11998e` 出现在多个上下文中，确保只替换应该替换的地方
3. **分文件操作**：每个 `.vue` 文件单独处理
4. **构建验证**：替换后必须 `npm run build` 确认编译通过
5. **要覆盖的文件**：Home.vue、List.vue、Detail.vue、PlaymateHome.vue 等页面级组件

## 颜色映射表（紫色→绿色迁移案例）

| 用途 | 旧值(绿色) | 新值(紫色) |
|------|-----------|-----------|
| 主色 | #11998e | #667eea |
| 渐变色 | #38ef7d | #764ba2 |
| Hero背景 | linear-gradient(135deg,#11998e,#38ef7d) | linear-gradient(135deg,#667eea,#764ba2) |
| 选中态 | #11998e | #667eea |
| 阴影 | rgba(17,153,142,...) | rgba(102,126,234,...) |
