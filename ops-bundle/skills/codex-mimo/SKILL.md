# Codex CLI + MiMo 配置

## 配置文件
```toml
# ~/.codex/config.toml
model = "mimo-v2.5-pro"
model_provider = "mimo"
web_search = "disabled"

[model_providers.mimo]
name = "MiMo"
base_url = "https://token-plan-cn.xiaomimimo.com/v1"
wire_api = "responses"
env_key = "OPENAI_API_KEY"
```

## 环境变量
```bash
export OPENAI_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
export OPENAI_API_KEY="tp-c2hcz66we5sd0xbpgeuqf0vjqvyq1ix2wsyvdpve7ktv2wj8"
```

## 使用
```bash
# 基本对话
codex exec -m mimo-v2.5-pro "你的问题"

# 代码审查（需绕过沙箱）
codex exec -m mimo-v2.5-pro --dangerously-bypass-approvals-and-sandbox "审查xxx"

# 修复建议
codex exec -m mimo-v2.5-pro --dangerously-bypass-approvals-and-sandbox "修复xxx问题"
```

## 注意
- 必须设置web_search = "disabled"（MiMo不支持）
- 必须设置env_key（否则API Key不附带）
- 沙箱需用--dangerously-bypass-approvals-and-sandbox绕过
