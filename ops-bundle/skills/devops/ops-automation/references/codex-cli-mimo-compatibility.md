# Codex CLI + MiMo 兼容性（已验证可用 ✅）

## 结论：可用，需要正确配置

Codex CLI v0.150.1 **可以对接 MiMo Token Plan**。

## 正确配置

### ~/.codex/config.toml

```toml
model = "mimo-v2.5-pro"
model_provider = "mimo"
web_search = "disabled"
approval_policy = "never"

[model_providers.mimo]
name = "MiMo"
base_url = "https://token-plan-cn.xiaomimimo.com/v1"
wire_api = "responses"
env_key = "OPENAI_API_KEY"
```

### 环境变量

```bash
export OPENAI_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
export OPENAI_API_KEY="tp-c2hcz66we5sd0xbpgeuqf0vjqvyq1ix2wsyvdpve7ktv2wj8"
```

## 关键发现

| 配置项 | 作用 | 缺失后果 |
|---|---|---|
| `name = "MiMo"` | provider名称 | "provider name must not be empty" |
| `env_key = "OPENAI_API_KEY"` | API Key来源 | 401 Unauthorized |
| `web_search = "disabled"` | 禁用web_search tool | 400 "web_search not supported" |
| `wire_api = "responses"` | API格式 | MiMo支持此格式 |

## 调试过程

1. 最初报 "provider name must not be empty" → 缺少`name`字段
2. 加name后报 401 → 缺少`env_key`配置
3. 加env_key后报 400 web_search → 需要禁用web_search
4. 全部配好后成功：`codex exec -m mimo-v2.5-pro "hello"` → "hello" ✅

## MiMo Responses API 格式

MiMo支持OpenAI Responses API：
```
POST /v1/responses
{"model": "mimo-v2.5-pro", "input": [{"role":"user","content":"hello"}]}
→ {"object":"response","status":"completed","output":[...]}
```

## 验证结果

```bash
$ codex exec -m mimo-v2.5-pro "输出hello world"
hello world  ✅

$ codex exec -m mimo-v2.5-pro "MySQL Too many connections怎么修"
# 详细6步修复方案  ✅
```

## 注意事项

- MiMo是推理模型，`content`字段可能为空，实际在`reasoning_content`
- Codex sandbox模式限制文件读取，加`approval_policy = "never"`跳过
- `web_search = "disabled"`必须在全局（不在model_providers内）
- 配置文件路径：`~/.codex/config.toml`
