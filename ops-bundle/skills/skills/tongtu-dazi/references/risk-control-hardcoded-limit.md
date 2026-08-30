# ⚠️ risk_control.py 硬编码限制陷阱

## 问题

`risk_control.py` 有一个**硬编码**的 `RISK_CONF` 字典，独立于 `site_config` 表。

```python
# /opt/ttdazi/backend/app/risk_control.py
RISK_CONF = {
    'max_order_per_user': 10,   # ← 单用户每天最多下单（硬编码！）
    'max_order_per_ip': 20,     # ← 单IP每天最多下单
    'order_interval': 3,        # 用户下单最小间隔(秒)
    ...
}
```

**后果：** 即使管理员在 `site_config` 中将 `max_orders_per_day` 改为 999，`risk_control.py` 仍按硬编码的 `max_order_per_user: 10` 拦截，用户下单第 11 次时报「今日下单次数已达上限」。

## 修复

```python
RISK_CONF = {
    'max_order_per_user': 999,
    'max_order_per_ip': 999,
}
```

或改为从 site_config 读取：
```python
from app.utils import get_site_config
max_order = int(get_site_config('max_orders_per_day', 10))
```

## 排查方法

- 用户反馈下单被拒时，先查 `risk_control.py` 的 `RISK_CONF`，不是查 `site_config`
- `site_config` 的 `max_orders_per_day` 可能看起来很合理，但实际上从未被使用
- 用 `grep -n "max_order" risk_control.py` 确认实际限制值

## 已修改

2026-07-09: 已将 `max_order_per_user` 和 `max_order_per_ip` 从 10/20 改为 999
