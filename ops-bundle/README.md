# ops-bundle 安全加固补丁

## 修复项（11个文件）

| 文件 | 修复内容 |
|------|----------|
| brain.py | API Key改环境变量 + MySQL命令注入修复 |
| opsctl.py | shlex.quote防命令注入 |
| preventive.py | shlex.quote防命令注入 |
| daily_health.py | 补 import os |
| alerts.py | shebang顺序修复 |
| websearch.py | GITHUB_TOKEN环境变量 |
| database.yaml | 3处明文密码改环境变量 |
| finance.yaml | 3处明文密码改环境变量 |
| devloop.yaml | 标记 enabled: false |
| llm_decision.yaml | 标记 enabled: false |
| .env.example | 配置模板 |

## 部署步骤

1. 解压到 ops-bundle 目录覆盖原文件
2. 创建 .env 文件：`cp .env.example .env` 然后填入真实密码
3. Git commit: `git add -A && git commit -m "安全加固"`
