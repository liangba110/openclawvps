# 构建与 Patch 工具问题排查

## Vue 模板缺少 `</template>` 标签

### 症状
```
error during build:
SyntaxError: [plugin vite:vue] src/views/MyDemands.vue (1:1): Element is missing end tag.
```
报错指向文件第一行，但实际问题在模板末尾。

### 原因
频繁使用 `patch` 工具替换 HTML 模板内容时，`</template>` 行可能被误删除。

### 排查
```bash
grep -c "<template>" MyDemands.vue    # 应为1
grep -c "</template>" MyDemands.vue   # 应为1（不匹配则缺标签）
# 检查模板末尾
tail -5 MyDemands.vue | grep -n "template\|script"
```

### 修复
在 `<script setup>` 前插入 `</template>`：
```python
content = content.replace('\n<script setup>', '\n</template>\n\n<script setup>')
```

---

## `patch` 工具 CSS 多行转义 Bug

### 症状
构建报 CSS 语法错误。查看文件发现类似：
```css
.class {\n  property: value;\n}
```
其中 `\n` 是字面量反斜杠+n，而不是换行符。

### 原因
`patch` 工具的参数序列化机制会将换行符编码为 `\n` 字面量。当 old_string/new_string 中包含 CSS 多行内容时，写入文件的是 `\\n` 而非真正换行。

### 修复（二进制替换法）
```python
with open('file.vue', 'rb') as f:
    data = f.read()
data = data.replace(b'\\\\n', b'\n').replace(b'\\n', b'\n')
with open('file.vue', 'wb') as f:
    f.write(data)
```

#### 更稳定的修复方案：二进制替换（当 Python 文本模式仍无法修复时）

如果 `data.replace(b'\\\\n', b'\\n')` 无效，尝试分两步：

```bash
# 第一步：将所有 literal \n（反斜杠+n）替换为唯一占位符
sed -i 's/\\\\n/__NEWLINE__/g' file.vue
# 第二步：将占位符替换为真实换行
sed -i 's/__NEWLINE__/\\n/g' file.vue
```

或使用 Python 二进制模式分步替换：

```python
with open('file.vue', 'rb') as f:
    data = f.read()
# 替换 literal backslash-n (两个字节: 0x5C 0x6E) 为实际换行
data = data.replace(b'\\\\n', b'\n')
# 如果仍有残留，再替换一级
data = data.replace(b'\\n', b'\n')
with open('file.vue', 'wb') as f:
    f.write(data)
```

### 快速验证法

替换后立即检查是否仍有残留：

```bash
grep -c '\\\\n' file.vue    # 返回0则全部修复
```

---

## 预防
**不要**用 `patch` 工具替换带多行 CSS/HTML 的内容。以下操作安全：
- ✅ `patch` 单行字符串替换（属性值、变量名、函数名）
- ✅ `patch` 模板中单行 JS 表达式
- ❌ `patch` CSS 代码块（多行）
- ❌ `patch` HTML 结构（多行标签）

替代方案：
- 用 `terminal` + `python3` 执行 `content.replace('old', 'new')` + `with open(path, 'w')`
- 用 `execute_code` 工具做文件读写
- 用 `write_file` 整个重写文件（当内容变化大时）

---

## CSS `overflow: hidden` 裁剪 `absolute` 子元素

### 症状
`position: absolute` 的子元素不可见，即使有 `z-index` 和正确的位置值。

### 原因
父元素有 `overflow: hidden` 且 `position: relative`。如果子元素使用 `position: absolute` 定位在父元素内部，不会裁剪。但如果子元素的尺寸或位置超过父元素边界，会被裁剪。

### 排查
1. 检查父元素是否有 `overflow: hidden`
2. 检查子元素的 `top/left/right/bottom` 是否超出父元素的内边距区域
3. 检查父元素的 `::before`/`::after` 伪元素是否覆盖了子元素

### 修复
- 移除父元素的 `overflow: hidden`
- 或确保子元素完全在父元素 padding 区域内

---

## 内联 style 与 scoped CSS 冲突

### 问题
同时使用内联 style 和 scoped CSS 选择器定位同一元素时，内联 style 优先级更高。未被内联覆盖的属性从 scoped CSS 继承。

示例：
```html
<span class="back" style="position:absolute;top:12px;font-size:22px">‹</span>
```
```css
/* scoped */
.back { font-size: 28px; color: red; z-index: 10; }
```

实际生效：font-size=22px（内联）, color=#fff（内联）, z-index=10（CSS，因为内联未设）。

**策略**：要么全用内联 style，要么全用 scoped CSS。**不要混用**统一元素的同一属性。
