# Gender Column Type Mismatch — MySQL TINYINT vs Frontend VARCHAR

## Problem
MySQL `user` table: `gender` is `TINYINT` with values `0/1/2` (0=secret, 1=male, 2=female).
Frontend sends string values: `'male'`/`'female'`/`'secret'`.
Backend `update_profile` passed the string directly to MySQL → `pymysql.err.DataError: (1366, "Incorrect integer value: 'female' for column 'gender'")` → 500 Internal Server Error.

## Fix (user.py)

### 1. update_profile — accept strings and convert to int
```python
GENDER_MAP = {'male': 1, 'female': 2, 'secret': 0}

# gender 单独处理（不放在 FIELD_RULES 循环里）
if 'gender' in data and data['gender'] is not None:
    g = data['gender']
    if isinstance(g, str) and g in GENDER_MAP:
        fields.append("gender=%s")
        params.append(GENDER_MAP[g])
    elif isinstance(g, int) and g in (0, 1, 2):
        fields.append("gender=%s")
        params.append(g)
```

### 2. get_profile / login / register — convert int to string on return
```python
'gender': {0: 'secret', 1: 'male', 2: 'female'}.get(user['gender'], 'secret'),
```

### 3. Key insight
Remove `'gender'` from `FIELD_RULES` dict (which uses string length validation) and handle it separately with the type mapping.

## Affected Frontend
Settings.vue: `genderMap = { '男': 'male', '女': 'female', '保密': 'secret' }` (already correct).
`genderLabel` computed maps back: `{ male: '男', female: '女', secret: '保密' }`.
