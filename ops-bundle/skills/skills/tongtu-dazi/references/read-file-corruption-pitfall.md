# `read_file` 内容污染陷阱

## 问题

用 `execute_code` 读取文件做字符串替换时，如果使用终端输出（带行号）而非结构化返回的原始内容，会导致文件被污染——行号被写入文件。

## 错误做法

```python
# ❌ 从 terminal 输出中复制带行号的内容
text = """1|<template>
2|  <div>...
``` 
# 直接 write_file 会写入 "1|"、"2|" 到文件内容中
```

## 正确做法

```python
# ✅ 使用 read_file 的 content 字段（无行号）
from hermes_tools import read_file, write_file

result = read_file('/path/to/file.vue', limit=200)
content = result['content']  # 这是纯文件内容，没有行号前缀

# 做替换
old = '旧文本'
new = '新文本'
content = content.replace(old, new)

write_file('/path/to/file.vue', content)
```

## 根源

`read_file()` 的终端显示格式为 `LINE_NUM|CONTENT`，如果误把这个显示文本当作文件内容保存回去，就会把行号也写进去。

## 检测方法

被污染的文件会显示类似：
```
100|100|      <div class="xxx">
```
其中 `100|` 是行号，第二个 `100|` 是被写入的污染内容。

## 修复

文件被污染后，只能用 `write_file()` 完全重写（不能靠 patch 修复）。所以务必在第一次写入前就确认 content 来源正确。
