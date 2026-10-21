# WebSocket 实时行情和事件驱动架构

## 概述

本文档介绍 QuantSys V2 的 WebSocket 实时行情支持和事件驱动架构实现。

## 架构组件

### 1. 事件总线 (Event Bus)

**文件**: `events/event_bus.py`

事件总线是事件驱动架构的核心，支持发布-订阅模式。

**特性**:
- 支持同步和异步事件处理
- 自动检测运行环境（异步/同步）
- 事件历史记录（最多1000条）
- 多订阅者支持
- 异常隔离（一个处理器失败不影响其他）

**主要方法**:
```python
# 订阅事件
event_bus.subscribe("quote_update", handler_function)

# 发布事件（自动选择同步/异步）
event_bus.publish("quote_update", {"symbol": "000001.SZ", "price": 10.5})

# 异步发布
await event_bus.publish_async("signal_generated", data)

# 同步发布
event_bus.publish_sync("risk_alert", data)

# 获取事件历史
history = event_bus.get_history(event_type="quote_update", limit=100)
```

### 2. WebSocket 连接管理器

**文件**: `api/websocket.py`

管理 WebSocket 连接和订阅关系。

**特性**:
- 基于房间的订阅机制（每个股票一个房间）
- 会话管理
- 广播消息到特定股票订阅者
- 全局广播支持

**主要方法**:
```python
# 初始化管理器
manager = init_connection_manager(socketio)

# 客户端连接
manager.connect(session_id, symbol)

# 断开连接
manager.disconnect(session_id, symbol)

# 广播消息
manager.broadcast(symbol, message_dict)

# 全局广播
manager.broadcast_to_all(message_dict)
```

### 3. 事件处理器

**文件**: `events/handlers.py`

连接事件总线和 WebSocket，将事件转发给订阅的客户端。

**支持的事件类型**:

| 事件类型 | 说明 | 数据字段 |
|---------|------|---------|
| `quote_update` | 行情更新 | symbol, price, volume, change, change_pct |
| `signal_generated` | 信号生成 | symbol, signal, strategy, confidence, reason |
| `risk_alert` | 风险告警 | symbol, risk_type, level, message, value, threshold |
| `trade_executed` | 交易执行 | symbol, action, price, quantity, status, execution_id |
| `backtest_completed` | 回测完成 | backtest_id, strategy, total_return, sharpe_ratio |
| `data_updated` | 数据更新 | source, status, symbols_count |

### 4. WebSocket 服务器

**文件**: `api/server_websocket.py`

Flask-SocketIO 实现的 WebSocket 服务器。

**WebSocket 事件**:

| 事件名 | 方向 | 说明 | 数据格式 |
|-------|------|------|---------|
| `connect` | 客户端→服务器 | 建立连接 | - |
| `connected` | 服务器→客户端 | 连接确认 | `{session_id, message, timestamp}` |
| `disconnect` | 客户端→服务器 | 断开连接 | - |
| `subscribe` | 客户端→服务器 | 订阅股票 | `{symbol}` |
| `subscribed` | 服务器→客户端 | 订阅确认 | `{symbol, message, timestamp}` |
| `unsubscribe` | 客户端→服务器 | 取消订阅 | `{symbol}` |
| `unsubscribed` | 服务器→客户端 | 取消订阅确认 | `{symbol, message, timestamp}` |
| `ping` | 客户端→服务器 | 心跳检测 | - |
| `pong` | 服务器→客户端 | 心跳响应 | `{timestamp}` |
| `get_subscriptions` | 客户端→服务器 | 获取订阅列表 | - |
| `subscriptions` | 服务器→客户端 | 订阅列表 | `{symbols[], count, timestamp}` |
| `message` | 服务器→客户端 | 推送消息 | `{type, ...}` |
| `broadcast` | 服务器→客户端 | 全局广播 | `{type, ...}` |
| `error` | 服务器→客户端 | 错误消息 | `{message}` |

**HTTP API 端点**:

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/api/ws/health` | GET | 健康检查 |
| `/api/ws/stats` | GET | 连接统计 |
| `/api/ws/test/publish_quote` | POST | 测试：发布行情更新 |
| `/api/ws/test/publish_signal` | POST | 测试：发布信号生成 |
| `/api/ws/test/publish_risk` | POST | 测试：发布风险告警 |
| `/api/events/history` | GET | 获取事件历史 |

## 使用示例

### 启动 WebSocket 服务器

```bash
cd quantsys-v2
python api/server_websocket.py
```

服务器将在 `http://localhost:5000` 启动。

### Python 客户端示例

```python
import socketio

# 创建客户端
sio = socketio.Client()

# 连接事件
@sio.on('connect')
def on_connect():
    print('已连接到服务器')
    # 订阅股票
    sio.emit('subscribe', {'symbol': '000001.SZ'})

# 接收消息
@sio.on('message')
def on_message(data):
    msg_type = data.get('type')
    if msg_type == 'quote':
        print(f"行情: {data['symbol']} 价格: {data['price']}")
    elif msg_type == 'signal':
        print(f"信号: {data['symbol']} {data['signal']} 置信度: {data['confidence']}")

# 连接服务器
sio.connect('http://localhost:5000')
sio.wait()
```

### JavaScript 客户端示例

```javascript
const socket = io('http://localhost:5000');

// 连接成功
socket.on('connect', () => {
    console.log('已连接');
    // 订阅股票
    socket.emit('subscribe', { symbol: '000001.SZ' });
});

// 接收消息
socket.on('message', (data) => {
    if (data.type === 'quote') {
        console.log(`行情: ${data.symbol} 价格: ${data.price}`);
    } else if (data.type === 'signal') {
        console.log(`信号: ${data.symbol} ${data.signal}`);
    }
});

// 心跳
setInterval(() => {
    socket.emit('ping');
}, 30000);
```

### 发布事件示例

```python
from events.event_bus import event_bus
from datetime import datetime

# 发布行情更新
event_bus.publish('quote_update', {
    'symbol': '000001.SZ',
    'price': 10.5,
    'volume': 1000000,
    'change': 0.5,
    'change_pct': 5.0,
    'timestamp': datetime.now().isoformat()
})

# 发布信号生成
event_bus.publish('signal_generated', {
    'symbol': '000001.SZ',
    'signal': 'buy',
    'strategy': 'ma_crossover',
    'confidence': 0.85,
    'price': 10.5,
    'reason': 'MA5 上穿 MA20',
    'timestamp': datetime.now().isoformat()
})

# 发布风险告警
event_bus.publish('risk_alert', {
    'symbol': '000001.SZ',
    'risk_type': 'concentration',
    'level': 'high',
    'message': '仓位集中度超过30%',
    'value': 35.5,
    'threshold': 30.0,
    'timestamp': datetime.now().isoformat()
})
```

## 测试

### 运行单元测试

```bash
cd quantsys-v2
pytest tests/test_websocket.py -v
```

### 使用 HTML 测试客户端

1. 启动 WebSocket 服务器:
```bash
python api/server_websocket.py
```

2. 在浏览器中打开:
```
quantsys-v2/examples/websocket_client.html
```

3. 测试功能:
   - 连接/断开服务器
   - 订阅/取消订阅股票
   - 发送测试事件（行情、信号、风险）
   - 查看实时消息推送
   - 心跳测试

### 测试端点

```bash
# 健康检查
curl http://localhost:5000/api/ws/health

# 连接统计
curl http://localhost:5000/api/ws/stats

# 发布测试行情
curl -X POST http://localhost:5000/api/ws/test/publish_quote \
  -H "Content-Type: application/json" \
  -d '{"symbol": "000001.SZ", "price": 10.5, "volume": 1000000}'

# 发布测试信号
curl -X POST http://localhost:5000/api/ws/test/publish_signal \
  -H "Content-Type: application/json" \
  -d '{"symbol": "000001.SZ", "signal": "buy", "confidence": 0.85}'

# 获取事件历史
curl "http://localhost:5000/api/events/history?event_type=quote_update&limit=10"
```

## 集成到现有系统

### 在策略中发布事件

```python
from events.event_bus import event_bus

class MyStrategy:
    def generate_signal(self, symbol, klines):
        # 策略逻辑
        signal = self.calculate_signal(klines)
        
        # 发布信号事件
        event_bus.publish('signal_generated', {
            'symbol': symbol,
            'signal': signal,
            'strategy': self.__class__.__name__,
            'confidence': 0.8,
            'timestamp': datetime.now().isoformat()
        })
        
        return signal
```

### 在数据更新时发布事件

```python
from events.event_bus import event_bus

def update_klines(symbol):
    # 更新K线数据
    klines = fetch_klines(symbol)
    save_to_db(klines)
    
    # 发布数据更新事件
    event_bus.publish('data_updated', {
        'source': 'klines',
        'symbol': symbol,
        'status': 'success',
        'timestamp': datetime.now().isoformat()
    })
```

### 在风险检查时发布事件

```python
from events.event_bus import event_bus

def check_risk(symbol, position_value, account_value):
    concentration = (position_value / account_value) * 100
    
    if concentration > 30:
        event_bus.publish('risk_alert', {
            'symbol': symbol,
            'risk_type': 'concentration',
            'level': 'high',
            'message': f'仓位集中度 {concentration:.1f}% 超过30%',
            'value': concentration,
            'threshold': 30.0,
            'timestamp': datetime.now().isoformat()
        })
```

## 性能考虑

1. **事件历史限制**: 默认保留最近1000条事件，避免内存溢出
2. **异常隔离**: 一个事件处理器失败不影响其他处理器
3. **异步处理**: 支持异步事件处理，避免阻塞
4. **房间机制**: 使用 SocketIO 房间机制，只向订阅者推送消息
5. **心跳机制**: 客户端应定期发送 ping，保持连接活跃

## 安全建议

1. **生产环境**: 修改 `SECRET_KEY`
2. **CORS**: 限制允许的源（`cors_allowed_origins`）
3. **认证**: 添加 WebSocket 认证机制
4. **限流**: 添加消息频率限制
5. **SSL/TLS**: 生产环境使用 HTTPS/WSS

## 故障排查

### 连接失败

1. 检查服务器是否启动: `curl http://localhost:5000/api/ws/health`
2. 检查防火墙设置
3. 查看服务器日志

### 消息未收到

1. 确认已订阅股票: 发送 `get_subscriptions` 事件
2. 检查事件是否发布: `curl http://localhost:5000/api/events/history`
3. 查看连接统计: `curl http://localhost:5000/api/ws/stats`

### 连接断开

1. 实现自动重连机制
2. 定期发送心跳（建议30秒）
3. 检查网络稳定性

## 扩展建议

1. **Redis 支持**: 使用 Redis 作为消息队列，支持多服务器部署
2. **消息持久化**: 将重要事件持久化到数据库
3. **消息过滤**: 支持客户端自定义消息过滤规则
4. **消息压缩**: 对大量数据使用压缩
5. **认证授权**: 实现基于 JWT 的 WebSocket 认证
