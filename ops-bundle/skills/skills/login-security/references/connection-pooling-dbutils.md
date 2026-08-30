# Database Connection Pooling with DBUtils

## Why

Without connection pooling, each API request creates a **new MySQL connection** (TCP handshake + auth). Under load (10+ concurrent users), this causes:
- Connection storms that overwhelm MySQL
- Increased latency (each new connection takes ~50ms)
- MySQL hitting `max_connections` limits
- Application errors: `Too many connections`

## Implementation

Replace `pymysql.connect()` with `PooledDB` from `dbutils`:

```python
# db.py — before (no pooling):
import pymysql
def get_connection():
    return pymysql.connect(host=..., cursorclass=DictCursor, ...)

# db.py — after (with pooling):
from dbutils.pooled_db import PooledDB
import pymysql

_pool = None

def get_connection():
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=True,
            mincached=2,       # Keep 2 connections warm
            maxcached=10,      # Cache up to 10
            maxconnections=20, # Hard limit
            blocking=True,     # Wait if all in use
        )
    return _pool.connection()
```

## Installation

```bash
pip3 install DBUtils PyMySQL
```

## Backward Compatibility

The function signature stays the same: `conn = get_connection()`. The caller still does `conn.close()` — but with pooling, `close()` returns the connection to the pool instead of destroying it. All existing code works without changes.

## Multi-Worker Safety

Each gunicorn worker process gets its own `_pool` instance (process-level singleton). This is safe because:
- Workers don't share connections across processes
- Each worker maintains its own pool of up to 10 connections
- Total connections = workers × maxcached_per_worker

## Verification

```bash
# Check connection count after load
mysql -e "SHOW PROCESSLIST;" | grep aiweb | wc -l
```

Should show stable connection count, not growing with each request.
