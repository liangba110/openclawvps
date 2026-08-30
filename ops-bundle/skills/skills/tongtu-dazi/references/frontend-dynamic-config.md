# 前端从 site_config 动态读取配置

某些全局配置（如提现手续费率）在管理后台 AdminConfig.vue 中可修改，前端需从 API 动态读取而非硬编码。

## 标准模式

```javascript
// 在 loadData() 中并行读取配置
const [mainData, config] = await Promise.all([
  api.get('/main/api').catch(() => ({})),
  api.get('/config/list').catch(() => ({})),
])

// 解析配置列表
const cfgList = Array.isArray(config) ? config : (config?.list || [])
const feeItem = cfgList.find(c => c.key === 'withdraw_fee_rate')
if (feeItem) withdrawFeeRate.value = Number(feeItem.value) || 3
```

## 已知从 site_config 读取的配置

| site_config key | 默认值 | 用途 | 读取位置 |
|----------------|--------|------|---------|
| `commission_rate` | 20 | 平台抽成比例(%) | 后端 order.py, playmate_api.py |
| `withdraw_fee_rate` | 3 | 提现手续费率(%) | 前端 PlaymateIncome.vue, 后端 playmate_api.py |
| `withdraw_min` | 100 | 最低提现金额 | 前端 PlaymateIncome.vue, 后端 playmate_api.py |
| `backup_password` | wll16562341@ | 备份下载密码 | 后端 main.py download-auth |

## 注意事项

1. **降级策略** — 配置读取失败时使用硬编码默认值，不阻塞主流程
2. **前端缓存** — 配置在 `onMounted` 时读取一次，后续通过自动刷新更新（参考 `references/frontend-auto-refresh-pattern.md`）
3. **安全配置** — `GET /api/config/list` 返回公开配置，`GET /api/config/admin/list` 返回全部配置（需 admin）
4. **管理后台修改后即时生效** — 前端下次自动刷新时读取新值，无需重启
