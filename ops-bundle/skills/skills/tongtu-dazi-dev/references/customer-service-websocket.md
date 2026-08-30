# 在线客服 WebSocket 实现参考

## 数据库表
```sql
CREATE TABLE customer_service (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    content TEXT NOT NULL,
    is_admin TINYINT NOT NULL DEFAULT 0,
    is_read TINYINT NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_read (is_read)
);
```

## 后端架构

### 依赖
```bash
pip install flask-REDACTED --break-system-packages
```

### main.py 初始化
```python
from flask_socketio import SocketIO
from app.socket_events import register_socket_events

# In create_app():
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
register_socket_events(socketio)
```

### 事件设计
| 事件 | 方向 | 说明 |
|------|------|------|
| `connect` | client→server | 认证token, join_room(`user_{id}`) |
| `user_join` | client→server | 推送离线历史消息 |
| `user_send` | client→server | 存DB, emit `new_message`给自己, emit `admin_new_message`给admin_room |
| `admin_join` | client→server | join `admin_room`, 推送用户列表+未读数 |
| `admin_load_conversation` | client→server | 加载指定用户对话 |
| `admin_reply` | client→server | 存DB, emit给用户+管理端确认 |

### Nginx 配置（必须在 /api/ 之前）
```nginx
location /socket.io/ {
    proxy_pass http://42.193.113.230:5002;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400s;
}
```

## 前端
```bash
npm install socket.io-client
```

### 连接管理
```js
import { io } from 'socket.io-client'

socket = io('/', {
  query: { token },
  transports: ['websocket', 'polling'],
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000
})

socket.on('connect', () => { connected.value = true })
socket.on('disconnect', () => { connected.value = false })
socket.on('connect_error', () => setTimeout(() => socket?.connect(), 3000))
```

### 文件清单
| 文件 | 说明 |
|------|------|
| `backend/app/customer_service.py` | REST API + 辅助函数 |
| `backend/app/socket_events.py` | WebSocket 事件处理 |
| `frontend/src/views/CustomerService.vue` | 用户端 WS 聊天 |
| `frontend/src/views/admin/AdminService.vue` | 管理端 WS 聊天 |
