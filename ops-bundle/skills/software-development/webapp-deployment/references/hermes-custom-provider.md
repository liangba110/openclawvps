# Hermes Custom OpenAI-Compatible Provider (SiliconFlow)

**Applies to**: Any OpenAI-compatible API provider — SiliconFlow, DeepSeek (via custom
endpoint), Together AI, Fireworks, Groq, etc.

## Config

Update `~/.hermes/config.yaml` (or use `hermes config set`):

```yaml
model:
  default: <model-name>       # e.g. deepseek-ai/DeepSeek-V3
  provider: openai            # NOT 'custom:<name>' — always use 'openai'
  base_url: https://api.siliconflow.cn/v1
  api_mode: chat_completions
  api_key_env: SILICONFLOW_API_KEY
```

### Key Rules

| Setting | Must be | Why |
|---------|---------|-----|
| `provider` | `openai` | `custom:siliconflow` is NOT a valid provider — Hermes rejects it |
| `base_url` | Provider's `/v1` endpoint | Must end in `/v1` (OpenAI-compatible suffix) |
| `api_key_env` | Env var name | Store the actual API key in `~/.hermes/.env` |
| `default` | Exact model ID | Use the provider's model identifier string |

## Shell Commands

```bash
# Set provider config
hermes config set model.provider openai
hermes config set model.base_url https://api.siliconflow.cn/v1
hermes config set model.default deepseek-ai/DeepSeek-V3
hermes config set model.api_key_env SILICONFLOW_API_KEY

# Remove old api_key from config if present
sed -i '/^  api_key:/d' ~/.hermes/config.yaml

# Add key to .env
echo 'SILICONFLOW_API_KEY=sk-REDACTED' >> ~/.hermes/.env
```

## Verification

Test the API directly to confirm credentials work before restarting the gateway:

```bash
curl -s https://api.siliconflow.cn/v1/chat/completions \
  -H "Authorization: Bearer $SILICONFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-ai/DeepSeek-V3","messages":[{"role":"user","content":"ok"}],"max_tokens":10}'
```

Expected response: `{"id":"...","object":"chat.completion","choices":[...]}`

## Apply Changes

Config takes effect on **next gateway restart**:

```bash
hermes gateway restart
```
Or from within a DM: `/restart` slash command.

## Supported SiliconFlow Free Models (2026-07)

| Model | Notes |
|-------|-------|
| `deepseek-ai/DeepSeek-V3` | Strong general-purpose |
| `Qwen/Qwen2.5-72B-Instruct` | Good Chinese support |
| `THUDM/glm-4-9b-chat` | Lightweight |

Full list: `curl -s https://api.siliconflow.cn/v1/models -H "Authorization: Bearer $KEY"`

## Common Failures

| Error | Cause | Fix |
|-------|-------|-----|
| `Unknown provider 'custom:siliconflow'` | Using `custom:` prefix as provider | Change to `provider: openai` |
| `Provider authentication failed` | Wrong API key or key env var not found | Check `~/.hermes/.env` has the key |
| `Connection refused` | Gateway not restarted after config change | Run `hermes gateway restart` |
| `model not found` | Wrong model ID | Check provider's /v1/models endpoint |
