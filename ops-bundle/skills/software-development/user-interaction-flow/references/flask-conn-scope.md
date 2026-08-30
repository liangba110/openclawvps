# Flask conn 变量作用域 Bug

## 问题模式
变量定义在 `if` 块内，使用在块外 → `NameError`

## 错误代码
```python
if 'phone' in data:
    conn = get_connection()  # ❌ 只在 if 内定义
    # ...
    conn.close()

# 很多行之后...
cur2 = conn.cursor()  # ❌ NameError: conn is undefined!
```

## 根因
- Python `if` 不创建新作用域，但变量赋值必须执行到该行才绑定
- 当请求没有 phone 字段时，`conn` 从未被赋值

## 正确做法
- 在第一次使用 conn 之前获取新连接：`conn = get_connection()`
- 或者把变量定义在 if 块外面

## 前端表现
- 用户操作时 Toast 显示"保存失败"
- 后端返回 `code=1, msg='服务器内部错误'`
- 日志显示 `NameError`

## 排查
→ 后端日志→ `NameError: name 'conn' is not defined`
→ 检查函数执行路径，看是否有变量在条件分支中定义但被后面的代码使用
