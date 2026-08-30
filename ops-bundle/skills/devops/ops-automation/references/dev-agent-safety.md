# Dev Agent 安全护栏架构

## 核心原则
AI改代码 = 高风险。必须有5层安全护栏。

## 5层安全护栏

### 1. Git快照（自动回滚）
```python
# 修改前自动commit
git add -A && git commit -m "🔧 dev_agent快照"
# 失败时自动回滚
git reset --hard HEAD~1
```

### 2. 文件白名单
```python
SAFE_PATTERNS = [
    r'ops/.*\.py$',           # 运维脚本
    r'ops/.*\.yaml$',         # 规则文件
    r'backend/app/config\.py$',  # 配置
]
BLOCKED_PATTERNS = [
    r'payment_service/.*',    # 支付相关
    r'main\.py$',             # 入口文件
    r'.*secret.*',            # 密钥
]
```

### 3. 语法检查
```python
# Python
python3 -m py_compile <file>
# YAML
python3 -c "import yaml; yaml.safe_load(open('<file>'))"
```

### 4. LLM审查（Reviewer Agent）
修改后让另一个LLM实例审查：
- 安全漏洞检查
- 逻辑正确性
- 不可逆操作检测

### 5. 人工确认（高风险时）
`need_human: true` 的工单必须用户确认后才执行。

## 工单状态机
```
open → analyzing → fixing → testing → reviewing → deploying → done
  └──────── 任何阶段失败 → failed → 需人工介入
```

## MiMo API 特殊处理
- MiMo是推理模型，content字段可能为空
- 实际输出在reasoning_content字段
- brain.py已适配：优先content，为空则用reasoning_content
- JSON解析需用括号深度匹配（简单find可能截断）

## Codex CLI 不兼容
- Codex需要OpenAI Responses API格式
- MiMo只支持Chat Completions格式
- 解决方案：用Python直接调MiMo API（dev_agent.py）
