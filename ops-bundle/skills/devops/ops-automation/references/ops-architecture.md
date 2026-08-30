# Ops 自动化架构参考

## 文件结构

```
/opt/ttdazi/ops/
├── opsctl.py           # CLI工具(22命令)
├── engine.py           # 自治引擎(16规则YAML)
├── intelligence.py     # 智能分析(5特性)
├── autopilot.py        # 自动开发(扫描→生成→安装)
├── alerts.py           # 实时告警(文件/QQ/微信)
├── preventive.py       # 预防性运维(磁盘/SSL/服务)
├── websearch.py        # 网页搜索(GitHub/PyPI)
├── deploy.sh           # 一键部署
├── sync_skills.sh      # Skills同步到GitHub
├── rules/              # YAML规则(7文件16条)
├── auto_tools/         # 自动生成的工具
├── data/               # 学习数据(SQLite+JSON)
├── state/              # 运行状态(计数器+升级队列)
└── logs/               # 执行日志
```

## Token消耗对比

| | 旧(纯Hermes) | 新(ops自动化) | 节省 |
|---|---|---|---|
| 日均 | ~75,000 | ~2,500 | 97% |

## GitHub仓库

```
https://github.com/liangba110/ops-bundle
部署: git clone + bash deploy.sh
同步: bash sync_skills.sh (每周日4:00自动)
```

## engine.py CHECKERS扩展陷阱

添加新check类型时，必须遵循顺序：
1. 定义函数 `def check_xxx(cfg): ...`
2. 在CHECKERS字典后赋值 `CHECKERS['xxx'] = check_xxx`
3. 两者都必须在 `if __name__ == '__main__':` 之前

错误顺序会导致 `NameError: name 'check_xxx' is not defined`

## pymysql information_schema大小写

DictCursor查询information_schema时返回大写键名：
```python
# 错误：cur.fetchone()['table_name']  → KeyError
# 正确：
cur.execute("SELECT TABLE_NAME as tname FROM information_schema.tables ...")
cur.fetchone()['tname']  # ✓
```
