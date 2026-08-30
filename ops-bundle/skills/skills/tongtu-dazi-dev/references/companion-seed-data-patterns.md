# 同城达人 / 游戏达人 种子数据模式

## 数据库结构

### companion 表核心字段

| 字段 | 说明 | 同城达人(travel) | 游戏达人(game) |
|------|------|-----------------|---------------|
| `user_id` | 关联用户 ID | 必须 | 必须 |
| `game_id` | 分类 ID | ≥8 (8~14 或 ≥23) | <8 或 15~22 |
| `expires_at_travel` | 同城达人有效期 | 必须 > NOW() | NULL |
| `expires_at_game` | 游戏达人有效期 | NULL | 必须 > NOW() |
| `expires_at` | 通用有效期 | 设同 `expires_at_travel` | 设同 `expires_at_game` |
| `status` | 审核状态 | 1=通过 | 1=通过 |
| `is_online` | 上架状态 | 1=上架 | 1=上架 |
| `intro` | 个人简介 | 建议 50~100 字 | 建议 50~100 字 |
| `tags` | JSON 数组标签 | 3 个左右 | 3 个左右 |
| `price_1h` | 1小时价格 | 设置合理价格 | 设置合理价格 |
| `life_photos` | 生活照 JSON | 留空 `[]` 或填图片路径 | 同上 |

### 同城 vs 游戏分类判断

```sql
-- 同城达人: game_id 8~14 或 ≥23
-- 游戏达人: game_id <8 或 15~22
```

同城达人类目列表 (game_id 8~14): 景点讲解(8)、行程规划(9)、美食向导(10)、结伴徒步(11)、旅拍(12)、自驾带路(13)、景区协助(14)
同城达人扩展 (game_id ≥23): 出行翻译(23)、包车向导(24)、户外跟拍(25)、露营向导(26)、出海体验(27)、文化讲解(28)、骑行陪骑(29)、滑雪陪练(30)、徒步领队(31)、探店向导(32)、台球交流(33)、羽毛球交流(34)、声乐交流(35)、乒乓球交流(36)、乐器指导(37)、绘画交流(38)、舞蹈指导(39)、健身指导(40)

### 用户表关联

`companion.user_id → user.id`

达人展示需要 `user` 表字段：`nickname`, `avatar`, `city`, `gender`, `score`, `order_count`
用户必须 `status=1` 且 `is_companion=1`

## 列表 API 过滤逻辑

后端 `companion_list()` 的 SQL 过滤：

```python
if service_type == "travel":
    where.append("(c.expires_at_travel IS NOT NULL AND c.expires_at_travel > NOW())")
    where.append("((c.game_id>=8 AND c.game_id<=14) OR c.game_id>=23)")
elif service_type == "game":
    where.append("(c.expires_at_game IS NOT NULL AND c.expires_at_game > NOW())")
    where.append("(c.game_id<8 OR (c.game_id>=15 AND c.game_id<=22))")
else:
    where.append("((c.expires_at_game ...) OR (c.expires_at_travel ...))")
```

**关键**: expires_at_travel 必须**非 NULL**且**在未来**，否则同城达人不显示。

## 种子数据模式

### 新建同城达人步骤

1. **创建 user 记录** — 唯一 phone，设置 `is_companion=1`, `city`, `avatar`, `gender`
2. **创建 companion 记录** — `game_id` 选 8~14 或 ≥23 范围，设置 `expires_at_travel=DATE_ADD(NOW(), INTERVAL 1 YEAR)`
3. **不设置 `expires_at_game`** — 保持 NULL 避免干扰游戏达人的类型判断

### 种子数据 Python 模板

```python
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

expires = datetime.now() + timedelta(days=365)

# 1. 创建用户
phone = '13900000XXX'
cur.execute("""
    INSERT INTO user (phone, username, password, nickname, avatar, gender, city, 
                      intro, score, status, is_companion, role)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 1, 'user')
""", (phone, f'travel_{phone}', generate_password_hash('123456'),
      '昵称', '/avatars/xxx.jpg', 1, '青岛市', '简介', 5.0))
user_id = cur.lastrowid

# 2. 创建 companion
cur.execute("""
    INSERT INTO companion (user_id, game_id, rank_title, tags, price_1h, price_2h,
                           price_night, intro, is_online, status, chat_paid,
                           life_photos, good_rate, response_time,
                           expires_at_travel, expires_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 1, 0, %s, '95%%', '5s', %s, %s)
""", (user_id, 8, '标签', '["标签1","标签2","标签3"]',
      68, 122, 238, '详细介绍...', '[]', expires, expires))
```

### 价格计算参考

```python
price_2h = round(price_1h * 1.8)
price_night = round(price_1h * 3.5)
```

### 更新已有同城达人

```python
cur.execute("""
    UPDATE companion SET 
        price_1h=%s, price_2h=%s, price_night=%s,
        intro=%s, tags=%s, life_photos=%s,
        status=1, is_online=1,
        expires_at_travel=DATE_ADD(NOW(), INTERVAL 1 YEAR)
    WHERE id=%s
""", (price_1h, price_2h, price_night, intro, tags_json, photos_json, companion_id))

# 同步更新用户信息
cur.execute("UPDATE user SET nickname=%s, city=%s, avatar=%s, gender=%s, status=1, is_companion=1 WHERE id=%s",
           (nickname, city, avatar, gender, user_id))
```

### 验证方法

```bash
# 检查 API 返回
curl -s "http://127.0.0.1:5002/api/companion/list?type=travel&page=1&page_size=30" \
  | python3.12 -c "import sys,json;d=json.load(sys.stdin);items=d.get('data',{}).get('list',[]);print(f'{len(items)}条')"

# 直接查询 DB
cd /opt/ttdazi/backend && python3.12 -c "
from db import get_connection
conn = get_connection()
with conn.cursor() as cur:
    cur.execute('''SELECT c.id, u.nickname, c.game_id, g.name, c.price_1h, c.intro
                   FROM companion c JOIN user u ON c.user_id = u.id
                   JOIN game g ON c.game_id = g.id
                   WHERE g.id>=8 LIMIT 5''')
    for r in cur.fetchall(): print(r)
conn.close()
"
```

## 已知陷阱

1. **`%` 字面量转义**: PyMySQL 中 SQL 字符串内的 `%` 必须写成 `%%`（如 `'95%%'`），否则 Python `%` 格式化报错
2. **expires_at_travel 必须显式设置**: 默认 NULL，留空则同城达人不显示
3. **phone 必须唯一**: 种子数据的 phone 不能用已存在的号码，建议用 13900000XXX 保留段
4. **game_id 边界**: 注意 `>=23` 的扩展类目（骑行/滑雪/绘画等）也属于同城达人
5. **前端 isTravel 判断**: `game.id >= 8 && game.id <= 14 || game.id >= 23`，首页 `goTravelList()` 跳转 `/list?type=travel`
