# ⚠️ 子代理覆盖 token 文件陷阱

## 问题

子代理（delegate_task / sibling subagent）可能在后台执行期间**覆盖共享文件**，最常见的是 `/tmp/user_token.txt`。

**发生条件：**
1. 当前会话生成 token→`/tmp/user_token.txt`（用户 10001 小甜心）
2. 你提交了 `delegate_task` 给子代理并行工作
3. 子代理也调用了同一账号或不同账号的 API，生成了新 token 写入相同路径
4. 父代理后续用 `/tmp/user_token.txt` 发请求 → 身份变成了其他用户（如 10046）
5. 如果目标用户不是陪玩师 → API 返回「您还不是陪玩师」
6. 调试半天发现 SQL 正确、代码正确 → 但结果不对

## 症状

- `/companion/my` 返回「您还不是陪玩师」
- API 全部正常，但 `user_id` 不是预期的用户
- `journalctl` 无任何错误日志
- 直接 SQL 查询返回正确数据

## 排查

```bash
curl -s -H "Authorization: Bearer $(cat /tmp/user_token.txt)" http://82.157.202.24/api/user/profile \
  | python3 -c "import sys,json;print(json.load(sys.stdin).get('data',{}).get('id'))"
```

输出不是预期的 user_id（如 10001）→ token 被覆盖。

## 修复

```bash
# 重新生成正确 token
/usr/bin/python3.12 -c "
import sys
sys.path.insert(0, '/opt/ttdazi/backend')
from app.utils import create_token
t = create_token(10001, '13800138000')
with open('/tmp/user_token.txt', 'w') as f: f.write(t)
print('ok')
"
```

## 预防

1. 子代理执行前后 `cat /tmp/user_token.txt` 验证 token 未被覆盖
2. 多个子代理不要共享 `/tmp/user_token.txt`
3. 每个子代理自己生成 token，不用共享文件
