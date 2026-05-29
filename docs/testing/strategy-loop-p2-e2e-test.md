# P2 策略循环闭合 — 端到端测试

**测试日期**: 2026-05-29  
**测试范围**: 信号 → 执行 → 盈亏 → 统计 → 经验 完整闭环  
**相关文档**: [P2 完成文档](../superpowers/specs/2026-05-29-strategy-loop-p2-completion.md)

---

## 🎯 测试目标

验证从策略信号生成到经验积累的完整数据流，确保：
1. 信号可追踪（signal_id 贯穿全流程）
2. 盈亏可计算（买入/卖出自动更新）
3. 统计可查询（纸面+实盘综合）
4. 经验可积累（自动生成经验条目）

---

## 📋 测试场景

### 场景 1: 完整闭环 — 从信号到经验

#### 步骤 1: 启动后端服务

```bash
cd quantsys-v2
python start_all.py
```

**预期**: REST API (5001) 和 WebSocket (5003) 都启动成功。

#### 步骤 2: 创建测试数据 — 纸面测试信号

```bash
# 创建 10 条纸面测试信号
curl -X POST http://127.0.0.1:5001/api/signal-test/record-batch \
  -H "Content-Type: application/json" \
  -d '{
    "signals": [
      {
        "symbol": "600519.SH",
        "name": "贵州茅台",
        "strategy_name": "ma_cross",
        "signal_date": "2026-05-20",
        "action": "buy",
        "confidence": 0.85,
        "signal_price": 1800.0,
        "entry_price": 1805.0,
        "stop_loss": 1700.0,
        "reason": "均线金叉"
      },
      {
        "symbol": "600519.SH",
        "name": "贵州茅台",
        "strategy_name": "ma_cross",
        "signal_date": "2026-05-21",
        "action": "buy",
        "confidence": 0.82,
        "signal_price": 1810.0,
        "entry_price": 1815.0,
        "stop_loss": 1710.0,
        "reason": "均线金叉"
      }
    ]
  }'
```

**预期**: 返回 `{"success": true, "recorded": 2}`

#### 步骤 3: 验证纸面测试信号

```bash
# 模拟 T+5 日后验证
curl -X POST http://127.0.0.1:5001/api/signal-test/verify \
  -H "Content-Type: application/json" \
  -d '{"days_after": 5}'
```

**预期**: 
- 返回验证数量
- signal_test_log 表中 status 更新为 'verified'
- pnl_pct 字段有值

#### 步骤 4: 创建实盘订单（带 signal_id）

```python
# 在 Python 环境中执行
from services.order_service import create_order, fill_order
from services.signal_test_log import SignalTestLog

# 创建信号
signal_log = SignalTestLog()
signal_id = signal_log.record_signal({
    'symbol': '600000.SH',
    'name': '浦发银行',
    'strategy_name': 'ma_cross',
    'signal_date': '2026-05-29',
    'action': 'buy',
    'confidence': 0.88,
    'signal_price': 10.0,
    'entry_price': None,
    'stop_loss': 9.0,
    'reason': '实盘测试信号'
})

# 创建订单（关联 signal_id）
order_id = create_order(
    symbol='600000.SH',
    action='buy',
    quantity=1000,
    price=10.2,
    signal_id=signal_id  # 关键：关联信号
)

# 模拟成交
fill_order(order_id, fill_price=10.2, fill_quantity=1000)
```

**预期**:
- 订单创建成功
- signal_test_log 的 entry_price 更新为 10.2

#### 步骤 5: 卖出并计算盈亏

```python
# 创建卖出订单
sell_order_id = create_order(
    symbol='600000.SH',
    action='sell',
    quantity=1000,
    price=11.0,
    signal_id=signal_id  # 同一个 signal_id
)

# 模拟成交
fill_order(sell_order_id, fill_price=11.0, fill_quantity=1000)
```

**预期**:
- signal_test_log 更新:
  - `current_price = 11.0`
  - `pnl_pct = (11.0 - 10.2) / 10.2 * 100 ≈ 7.84`
  - `status = 'verified'`
- strategy_performance 表新增记录:
  - `entry_price = 10.2`
  - `exit_price = 11.0`
  - `pnl_pct ≈ 7.84`
  - `source = 'live'`

#### 步骤 6: 查询统一统计

```bash
curl "http://127.0.0.1:5001/api/signal-test/performance?strategy=ma_cross&symbol=600000.SH"
```

**预期返回**:
```json
{
  "success": true,
  "data": {
    "strategy_name": "ma_cross",
    "symbol": "600000.SH",
    "paper": {
      "total_trades": 0,
      "verified_trades": 0,
      "avg_pnl_pct": 0.0,
      "win_rate": 0.0
    },
    "live": {
      "total_trades": 1,
      "win_trades": 1,
      "loss_trades": 0,
      "avg_pnl_pct": 7.84,
      "win_rate": 100.0,
      "avg_holding_days": 0
    },
    "combined": {
      "total_trades": 1,
      "avg_pnl_pct": 7.84,
      "win_rate": 100.0
    }
  }
}
```

#### 步骤 7: 积累经验

```python
from services.experience_accumulator import ExperienceAccumulator

accumulator = ExperienceAccumulator()

# 单个策略-标的组合（需要 ≥ 10 个样本）
result = accumulator.accumulate_from_performance(
    strategy_name='ma_cross',
    symbol='600519.SH',
    min_samples=10,
    output_file='/tmp/test_experiences.json'
)

print(result)
```

**预期**:
- 如果样本 < 10: `experience_created = False`, `reason = 'Insufficient samples'`
- 如果样本 ≥ 10: `experience_created = True`, 返回经验条目

#### 步骤 8: 验证经验条目格式

```python
import json

with open('/tmp/test_experiences.json', 'r') as f:
    data = json.load(f)

print(json.dumps(data, indent=2, ensure_ascii=False))
```

**预期格式**:
```json
{
  "version": "1.0.0",
  "last_updated": "2026-05-29",
  "experiences": [
    {
      "id": "uuid",
      "scenario": "使用 ma_cross 策略交易 600519.SH",
      "pattern": {
        "conditions": ["策略: ma_cross", "标的: 600519.SH"],
        "action": "buy"
      },
      "outcomes": {
        "total_cases": 15,
        "win_rate": 61.5,
        "avg_return": 3.8,
        "max_gain": 15.2,
        "max_loss": -5.3
      },
      "recommendation": "moderate",
      "reason": "基于 15 个历史案例，胜率 61.5%，平均收益 3.80%",
      "examples": []
    }
  ]
}
```

---

### 场景 2: 批量经验积累

#### 步骤 1: 准备多个策略的测试数据

```python
from services.signal_test_log import SignalTestLog
from datetime import date, timedelta

signal_log = SignalTestLog()

# 创建多个策略的信号
strategies = ['ma_cross', 'rsi_reversal', 'bollinger_breakout']
symbols = ['600519.SH', '000001.SZ', '600036.SH']

for strategy in strategies:
    for symbol in symbols:
        for i in range(12):  # 每个组合 12 条信号
            signal_log.record_signal({
                'symbol': symbol,
                'name': f'测试股票{symbol}',
                'strategy_name': strategy,
                'signal_date': date.today() - timedelta(days=20 - i),
                'action': 'buy',
                'confidence': 0.75 + i * 0.01,
                'signal_price': 100.0 + i * 5,
                'entry_price': 100.0 + i * 5,
                'stop_loss': 90.0 + i * 5,
                'reason': f'测试信号 {i}'
            })

# 更新为已验证状态（模拟盈利和亏损）
conn = signal_log._get_conn()
cursor = conn.cursor()

for strategy in strategies:
    for symbol in symbols:
        # 70% 盈利
        cursor.execute(f"""
            UPDATE {signal_log.TABLE_NAME}
            SET status = 'verified',
                current_price = signal_price * 1.05,
                pnl_pct = 5.0,
                verify_date = CURRENT_DATE
            WHERE strategy_name = %s AND symbol = %s
            AND id IN (
                SELECT id FROM {signal_log.TABLE_NAME}
                WHERE strategy_name = %s AND symbol = %s
                ORDER BY id
                LIMIT 8
            )
        """, (strategy, symbol, strategy, symbol))
        
        # 30% 亏损
        cursor.execute(f"""
            UPDATE {signal_log.TABLE_NAME}
            SET status = 'verified',
                current_price = signal_price * 0.97,
                pnl_pct = -3.0,
                verify_date = CURRENT_DATE
            WHERE strategy_name = %s AND symbol = %s AND status = 'pending'
        """, (strategy, symbol))

conn.commit()
cursor.close()
conn.close()
```

#### 步骤 2: 批量积累经验

```python
from services.experience_accumulator import ExperienceAccumulator

accumulator = ExperienceAccumulator()

result = accumulator.accumulate_all(
    min_samples=10,
    output_file='/tmp/all_experiences.json'
)

print(f"总处理: {result['total_processed']}")
print(f"创建经验: {result['experiences_created']}")
print(f"经验列表: {len(result['experiences'])}")
```

**预期**:
- `total_processed` = 9 (3 策略 × 3 标的)
- `experiences_created` = 9 (所有组合都 ≥ 10 个样本)
- 文件包含 9 条经验

---

### 场景 3: 推荐等级验证

#### 测试不同胜率和收益的推荐等级

```python
from services.experience_accumulator import ExperienceAccumulator

accumulator = ExperienceAccumulator()

# 测试用例
test_cases = [
    (75, 4.0, 'aggressive'),   # 高胜率 + 高收益
    (65, 2.5, 'moderate'),     # 中等胜率 + 中等收益
    (55, 1.2, 'cautious'),     # 低胜率 + 低收益
    (45, 0.5, 'avoid'),        # 很低胜率
    (70, 1.5, 'moderate'),     # 高胜率但低收益
    (55, 3.5, 'cautious'),     # 低胜率但高收益
]

for win_rate, avg_return, expected in test_cases:
    result = accumulator._generate_recommendation(win_rate, avg_return)
    status = '✅' if result == expected else '❌'
    print(f"{status} 胜率={win_rate}%, 收益={avg_return}% → {result} (预期: {expected})")
```

**预期**: 所有测试用例都通过 ✅

---

## 🧪 自动化测试脚本

### 完整端到端测试

```python
#!/usr/bin/env python3
"""
P2 端到端测试脚本
"""
import sys
import json
from datetime import date, timedelta
from services.signal_test_log import SignalTestLog
from services.order_service import create_order, fill_order
from services.experience_accumulator import ExperienceAccumulator
from repositories.strategy_performance_repository import StrategyPerformanceRepository

def test_full_loop():
    """测试完整闭环"""
    print("=" * 60)
    print("P2 端到端测试 — 完整闭环")
    print("=" * 60)
    
    signal_log = SignalTestLog()
    perf_repo = StrategyPerformanceRepository()
    accumulator = ExperienceAccumulator()
    
    # 1. 创建信号
    print("\n[1/7] 创建测试信号...")
    signal_id = signal_log.record_signal({
        'symbol': '600000.SH',
        'name': '浦发银行',
        'strategy_name': 'ma_cross',
        'signal_date': date.today(),
        'action': 'buy',
        'confidence': 0.88,
        'signal_price': 10.0,
        'entry_price': None,
        'stop_loss': 9.0,
        'reason': 'E2E 测试信号'
    })
    print(f"✅ 信号创建成功: signal_id={signal_id}")
    
    # 2. 创建买入订单
    print("\n[2/7] 创建买入订单...")
    buy_order_id = create_order(
        symbol='600000.SH',
        action='buy',
        quantity=1000,
        price=10.2,
        signal_id=signal_id
    )
    print(f"✅ 订单创建成功: order_id={buy_order_id}")
    
    # 3. 成交买入订单
    print("\n[3/7] 成交买入订单...")
    fill_order(buy_order_id, fill_price=10.2, fill_quantity=1000)
    
    # 验证 entry_price 更新
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(f"SELECT entry_price FROM {signal_log.TABLE_NAME} WHERE id = %s", (signal_id,))
    entry_price = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    assert entry_price == 10.2, f"entry_price 应该是 10.2，实际是 {entry_price}"
    print(f"✅ entry_price 更新成功: {entry_price}")
    
    # 4. 创建卖出订单
    print("\n[4/7] 创建卖出订单...")
    sell_order_id = create_order(
        symbol='600000.SH',
        action='sell',
        quantity=1000,
        price=11.0,
        signal_id=signal_id
    )
    print(f"✅ 订单创建成功: order_id={sell_order_id}")
    
    # 5. 成交卖出订单
    print("\n[5/7] 成交卖出订单...")
    fill_order(sell_order_id, fill_price=11.0, fill_quantity=1000)
    
    # 验证盈亏计算
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT pnl_pct, status FROM {signal_log.TABLE_NAME} WHERE id = %s",
        (signal_id,)
    )
    pnl_pct, status = cursor.fetchone()
    cursor.close()
    conn.close()
    
    expected_pnl = (11.0 - 10.2) / 10.2 * 100
    assert abs(float(pnl_pct) - expected_pnl) < 0.01, f"pnl_pct 应该是 {expected_pnl:.2f}，实际是 {pnl_pct}"
    assert status == 'verified', f"status 应该是 'verified'，实际是 {status}"
    print(f"✅ 盈亏计算成功: pnl_pct={pnl_pct:.2f}%, status={status}")
    
    # 6. 验证 strategy_performance 记录
    print("\n[6/7] 验证 strategy_performance 记录...")
    records = perf_repo.get_by_strategy_and_symbol('ma_cross', '600000.SH')
    assert len(records) >= 1, "strategy_performance 应该有至少 1 条记录"
    
    latest = records[-1]
    assert float(latest['entry_price']) == 10.2
    assert float(latest['exit_price']) == 11.0
    assert abs(float(latest['pnl_pct']) - expected_pnl) < 0.01
    assert latest['source'] == 'live'
    print(f"✅ strategy_performance 记录正确")
    
    # 7. 查询统计
    print("\n[7/7] 查询统计...")
    stats = perf_repo.get_statistics('ma_cross', '600000.SH', 'live')
    print(f"✅ 统计查询成功:")
    print(f"   - 总交易数: {stats['total_trades']}")
    print(f"   - 胜率: {stats['win_rate']:.2f}%")
    print(f"   - 平均盈亏: {stats['avg_pnl_pct']:.2f}%")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    
    # 清理测试数据
    print("\n清理测试数据...")
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quant.signal_test_log WHERE symbol = '600000.SH' AND reason = 'E2E 测试信号'")
    cursor.execute("DELETE FROM quant.strategy_performance WHERE symbol = '600000.SH'")
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ 清理完成")

if __name__ == '__main__':
    try:
        test_full_loop()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

**运行测试**:
```bash
cd quantsys-v2
python -c "$(cat << 'EOF'
# 粘贴上面的测试脚本
EOF
)"
```

---

## ✅ 验证清单

- [ ] 信号创建成功（signal_test_log 有记录）
- [ ] 订单关联 signal_id
- [ ] 买入成交后 entry_price 更新
- [ ] 卖出成交后 pnl_pct 计算正确
- [ ] strategy_performance 表有实盘记录
- [ ] 统计 API 返回纸面+实盘综合数据
- [ ] 经验积累生成正确格式的条目
- [ ] 推荐等级符合规则

---

## 📊 性能基准

| 操作 | 预期耗时 |
|------|---------|
| 创建信号 | < 50ms |
| 创建订单 | < 100ms |
| 成交更新 | < 150ms |
| 统计查询 | < 200ms |
| 单个经验积累 | < 500ms |
| 批量经验积累（9个组合） | < 3s |

---

## 🐛 已知问题

无

---

## 📝 相关文档

- [P2 完成文档](../superpowers/specs/2026-05-29-strategy-loop-p2-completion.md)
- [策略循环闭合计划](../plans/strategy-loop-closure-plan.md)
