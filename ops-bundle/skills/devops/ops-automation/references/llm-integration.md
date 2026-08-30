# LLM集成参考 — MiMo推理模型

## API配置

```python
API_CONFIG = {
    'base_url': 'https://token-plan-cn.xiaomimimo.com/v1',
    'api_key': 'tp-c2hcz66we5sd0xbpgeuqf0vjqvyq1ix2wsyvdpve7ktv2wj8',
    'model': 'mimo-v2.5',
}
```

## ⚠️ MiMo推理模型陷阱

MiMo是推理模型，响应格式特殊：
- `content`字段：**始终为空**（或只有最终结论）
- `reasoning_content`字段：包含完整思考过程（可能很长）
- `finish_reason`: `stop` 或 `length`（token用完）

**正确用法**：
```python
msg = data['choices'][0]['message']
content = msg.get('content', '') or ''
reasoning = msg.get('reasoning_content', '') or ''
result = content if content.strip() else reasoning  # 优先content
```

**不要**假设content一定有值。调用时max_tokens建议800+，否则reasoning被截断。

## 替代方案

如果需要更快/更便宜的决策：
- **DeepSeek Flash**：`api.deepseek.com/v1`，速度快，无推理token开销
- **本地规则引擎**：`decision_engine.py`（知识库+因果链，零API调用）
- **混合模式**：简单问题走规则引擎，复杂问题调LLM
