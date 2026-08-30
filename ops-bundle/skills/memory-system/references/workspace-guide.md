# Workspace文件管理

## 文件清单

| 文件 | 用途 | 更新频率 |
|---|---|---|
| MEMORY.md | 权威记忆（详细版） | 有变更时 |
| ERRORS.md | 犯过的错误+正确做法 | 犯错时 |
| CONTEXT.md | 当前任务状态 | 任务变更时 |
| SKILLS.md | 技能清单 | 技能变更时 |
| HISTORY.md | 已完成事项 | 完成任务时 |

## Git同步
```bash
cd ~/.hermes/workspace
git add -A && git commit -m "更新" && git push b master
```
