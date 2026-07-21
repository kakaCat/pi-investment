# WebSocket 快速开始指南

## 安装依赖

```bash
cd quantsys-v2
pip install flask-socketio python-socketio eventlet
```

## 启动服务器

```bash
python api/server_websocket.py
```

服务器将在 `http://localhost:5000` 启动。

## 快速测试

### 方法1: 使用 HTML 客户端（推荐）

1. 启动服务器
2. 在浏览器打开: `examples/websocket_client.html`
3. 点击"连接"
4. 输入股票代码（如 000001.SZ）并点击"订阅"
5. 点击"发送行情"测试实时推送

### 方法2: 使用 curl 测试

```bash
# 健康检查
curl http://localhost:5000/api/ws/health

# 发布测试行情（需要先有客户端订阅）
curl -X POST http://localhost:5000/api/ws/test/publish_quote \
  -H "Content-Type: application/json" \
  -d '{"symbol": "000001.SZ", "price": 10.5, "volume": 1000000}'

# 查看事件历史
curl http://localhost:5000/api/events/history
```

### 方法3: Python 客户端

```python
import socketio
import time

sio = socketio.Client()

@sio.on('connect')
def on_connect():
    print('✅ 已连接到服务器')
    sio.emit('subscribe', {'symbol': '000001.SZ'})

@sio.on('subscribed')
def on_subscribed(data):
    print(f'✅ 订阅成功: {data["symbol"]}')

@sio.on('message')
def on_message(data):
    msg_type = data.get('type')
    if msg_type == 'quote':
        print(f'📈 行情: {data["symbol"]} 价格: {data["price"]} 成交量: {data["volume"]}')
    elif msg_type == 'signal':
        print(f'🎯 信号: {data["symbol"]} {data["signal"]} 置信度: {data["confidence"]}')
    elif msg_type == 'risk_alert':
        print(f'⚠️  风险: {data["symbol"]} {data["message"]}')

sio.connect('http://localhost:5000')

# 保持连接
try:
    sio.wait()
except KeyboardInterrupt:
    print('\n断开连接')
    sio.disconnect()
```

## 在代码中发布事件

### 发布行情更新

```python
from events.event_bus import event_bus
from datetime import datetime

event_bus.publish('quote_update', {
    'symbol': '000001.SZ',
    'price': 10.5,
    'volume': 1000000,
    'change': 0.5,
    'change_pct': 5.0,
    'timestamp': datetime.now().isoformat()
})
```

### 发布交易信号

```python
event_bus.publish('signal_generated', {
    'symbol': '000001.SZ',
    'signal': 'buy',
    'strategy': 'ma_crossover',
    'confidence': 0.85,
    'price': 10.5,
    'reason': 'MA5 上穿 MA20',
    'timestamp': datetime.now().isoformat()
})
```

### 发布风险告警

```python
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

## 集成到策略

```python
from events.event_bus import event_bus
from datetime import datetime

class MyStrategy:
    def on_bar(self, symbol, klines):
        # 策略逻辑
        signal = self.calculate_signal(klines)
        
        if signal in ['buy', 'sell']:
            # 发布信号事件（自动推送给订阅的客户端）
            event_bus.publish('signal_generated', {
                'symbol': symbol,
                'signal': signal,
                'strategy': self.__class__.__name__,
                'confidence': 0.8,
                'price': klines[-1]['close'],
                'timestamp': datetime.now().isoformat()
            })
        
        return signal
```

## 支持的事件类型

| 事件类型 | 说明 | 必需字段 |
|---------|------|---------|
| `quote_update` | 行情更新 | symbol, price, volume |
| `signal_generated` | 信号生成 | symbol, signal, strategy, confidence |
| `risk_alert` | 风险告警 | symbol, risk_type, level, message |
| `trade_executed` | 交易执行 | symbol, action, price, quantity |
| `backtest_completed` | 回测完成 | backtest_id, strategy |
| `data_updated` | 数据更新 | source, status |

## 常见问题

### Q: 如何查看有多少客户端连接？

```bash
curl http://localhost:5000/api/ws/stats
```

### Q: 如何查看事件历史？

```bash
# 查看所有事件
curl http://localhost:5000/api/events/history

# 查看特定类型事件
curl "http://localhost:5000/api/events/history?event_type=quote_update&limit=10"
```

### Q: 客户端如何保持连接？

发送心跳:
```python
# Python
sio.emit('ping')

# JavaScript
socket.emit('ping');
```

建议每30秒发送一次心跳。

### Q: 如何取消订阅？

```python
# Python
sio.emit('unsubscribe', {'symbol': '000001.SZ'})

# JavaScript
socket.emit('unsubscribe', { symbol: '000001.SZ' });
```

## 运行测试

```bash
# 测试事件总线
pytest tests/test_event_bus.py -v

# 测试 WebSocket（需要先安装依赖）
pytest tests/test_websocket.py -v
```

## 更多信息

详细文档请参考:
- `docs/WEBSOCKET_GUIDE.md` - 完整使用指南
- `WEBSOCKET_IMPLEMENTATION_REPORT.md` - 实现报告
