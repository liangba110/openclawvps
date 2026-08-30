# 记忆系统管理

## 双轨记忆架构

| 层 | 容量 | 存储 | 用途 |
|---|---|---|---|
| Hermes记忆 | 4000字符 | ~/.hermes/memories/MEMORY.md | 高频核心，每轮注入 |
| workspace | 无限制 | ~/.hermes/workspace/*.md | 详细记录，按需读取 |

## Hermes记忆操作

```python
# 读取
memory(action=None)  # 返回当前记忆

# 添加
memory(action="add", content="新条目", target="memory")

# 替换
memory(action="replace", content="新内容", old_text="旧内容", target="memory")

# 删除
memory(action="remove", old_text="要删除的内容", target="memory")
```

## 容量管理
- memory_char_limit: 4000（config.yaml）
- user_char_limit: 2000（config.yaml）
- 满了→精简旧条目→腾空间→加新条目
- 详细内容放workspace，不要塞Hermes记忆

## workspace操作

```bash
# 查看
cat ~/.hermes/workspace/MEMORY.md
cat ~/.hermes/workspace/ERRORS.md
cat ~/.hermes/workspace/CONTEXT.md

# 编辑（用write_file或patch）
# 提交git
cd ~/.hermes/workspace && git add -A && git commit -m "更新" && git push b master
```
