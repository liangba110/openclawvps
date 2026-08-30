# WebSocket Decimal Crash — Full Error Transcript

## Error
```
TypeError: Object of type Decimal is not JSON serializable
```

## Call Stack
```
socket_events.py:100 handle_admin_join → emit('admin_users', ...)
flask_socketio/__init__.py:933 emit()
socketio/server.py:167 emit() → self.manager.emit()
socketio/manager.py:44 emit() → pkt.encode()
socketio/packet.py:64 encode() → self.json.dumps(data)
json/encoder.py:180 default() → TypeError
```

## Root Cause
`get_admin_user_list()` returns MySQL `Decimal` objects from companion_game.price_1h.
SocketIO's `emit()` calls `json.dumps()` which can't serialize Python `Decimal`.

## Why It Crashes Gunicorn
- 2 gunicorn workers → each worker processes events → any event triggering emit crashes that worker
- Worker crash → gunicorn restarts worker → boot loop → `HaltServer: Worker failed to boot`
- All workers dead → 502 Bad Gateway

## Fix Attempts That Failed
- Wrapping Decimal → float in get_admin_user_list: works but other Decimal fields in companion table
- Using json.dumps with default=str: SocketIO controls serialization, can't inject custom
- Monkey-patching: too fragile

## Working Solution: REST Polling
Replace WebSocket with 3-second setInterval HTTP polling.
```js
onMounted(() => { load(); timer = setInterval(load, 3000) })
onUnmounted(() => clearInterval(timer))
```
