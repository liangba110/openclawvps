# 同途搭子后端 import 速查

## 各模块正确导入方式

| 装饰器/函数 | 正确来源 | 错误来源（会导致502） |
|------------|---------|-------------------|
| `login_required` | `from app.utils import login_required` | — |
| `admin_required` | `from app.admin import admin_required` | ~~`from app.utils import admin_required`~~ |
| `success` | `from app.utils import success` | — |
| `fail` | `from app.utils import fail` | — |
| `get_connection` | `from db import get_connection` | — |
| `decode_token` | `from app.utils import decode_token` | — |
| `hash_password` | `from app.utils import hash_password` | — |

## 曾被此 bug 影响并修复的文件

1. `backend/app/customer_service.py` — 最初写错，commit `2bf59e6` 修复
2. `backend/app/config_api.py` — 重写时再次写错，commit `9c4fcf5` 修复

## 排查方法

```bash
# 出现 502 时立即检查
sudo journalctl -u ttdazi --no-pager -n 20 | grep 'ImportError'
# 或逐模块测试导入
cd /opt/ttdazi/backend && python3.12 -c "from main import app; print('OK')"
```
