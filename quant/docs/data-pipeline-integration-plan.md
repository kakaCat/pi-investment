# 数据管道集成方案

## 问题诊断

### 现状
1. **Python量化系统** (`quantsys/`) 每天自动更新数据：
   - 股票列表 → K线数据 → 技术因子 → 信号生成 → ML预测
   - 数据存储在 `quantsys/data/stocks.db` (35MB)
   - 包含3张表：`stocks`, `daily_klines`, `factor_values`
   - 已有31个技术因子（MA, MACD, RSI, BOLL等）
   - 覆盖41只股票，180个交易日，共210,069条因子记录

2. **AI工具层** (`src/infrastructure/tools/`) 每次都调用API：
   - `calculate_technical_indicators()` → 调用 `_sina_stock_history()` 获取90天数据
   - `calculate_buy_range()` → 调用 `_sina_stock_history()` 获取90天数据
   - `analyze_price_action()` → 调用 `_sina_stock_history()` 获取数据
   - 每次都重新计算MA/MACD/RSI等指标

### 问题
- **重复计算**：AI每次都重新获取数据并计算因子，而本地数据库已有
- **速度慢**：网络请求 + 重复计算 vs 直接读数据库
- **数据不一致**：AI实时计算的因子 vs 定时任务计算的因子可能不同
- **资源浪费**：已有的因子数据和信号完全没被利用

## 解决方案

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Agent (TypeScript)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Tools: analyze_technical, get_buy_range, etc.        │ │
│  └────────────────────────────────────────────────────────┘ │
│                            ↓                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Data Access Layer (新增)                       │ │
│  │  - 优先读本地DB (quantsys/data/stocks.db)             │ │
│  │  - 降级到API (数据缺失/过期时)                         │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌──────────────────┴──────────────────┐
        ↓                                      ↓
┌───────────────────┐              ┌──────────────────────┐
│  Local Database   │              │   External APIs      │
│  stocks.db (35MB) │              │  (Sina/AkShare)      │
│  - daily_klines   │              │  - 实时价格          │
│  - factor_values  │              │  - 最新数据          │
│  - stocks         │              │                      │
└───────────────────┘              └──────────────────────┘
```

### 实施步骤

#### Phase 1: 创建数据访问层 (Python)

**文件**: `python/data_access_layer.py`

```python
"""
数据访问层 - 优先使用本地数据库，降级到API
"""
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

class DataAccessLayer:
    """统一数据访问接口"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 默认路径：quantsys/data/stocks.db
            db_path = Path(__file__).parent.parent / "quant" / "quantsys" / "data" / "stocks.db"
        self.db_path = Path(db_path)
        self.conn = None
        if self.db_path.exists():
            self.conn = sqlite3.connect(str(self.db_path))
    
    def get_klines(self, symbol: str, days: int = 90) -> Optional[pd.DataFrame]:
        """
        获取K线数据
        优先从本地数据库读取，如果数据不足或过期则返回None
        """
        if not self.conn:
            return None
        
        try:
            # 读取最近N天的K线数据
            query = """
                SELECT date, open, high, low, close, volume, amount, turnover_rate
                FROM daily_klines
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT ?
            """
            df = pd.read_sql_query(query, self.conn, params=(symbol, days))
            
            if df.empty:
                return None
            
            # 检查数据新鲜度（最新数据不超过3天）
            latest_date = pd.to_datetime(df['date'].iloc[0])
            if (datetime.now() - latest_date).days > 3:
                return None
            
            # 检查数据完整性（至少有30天数据）
            if len(df) < 30:
                return None
            
            return df.sort_values('date')  # 按日期升序
            
        except Exception as e:
            print(f"[DataAccessLayer] 读取K线失败: {e}")
            return None
    
    def get_factors(self, symbol: str, factor_names: List[str] = None) -> Optional[Dict]:
        """
        获取技术因子
        返回最新日期的因子值
        """
        if not self.conn:
            return None
        
        try:
            if factor_names:
                placeholders = ','.join(['?'] * len(factor_names))
                query = f"""
                    SELECT factor_name, factor_value, date
                    FROM factor_values
                    WHERE symbol = ? AND factor_name IN ({placeholders})
                    ORDER BY date DESC
                """
                params = [symbol] + factor_names
            else:
                query = """
                    SELECT factor_name, factor_value, date
                    FROM factor_values
                    WHERE symbol = ?
                    ORDER BY date DESC
                """
                params = [symbol]
            
            df = pd.read_sql_query(query, self.conn, params=params)
            
            if df.empty:
                return None
            
            # 获取最新日期的因子
            latest_date = df['date'].iloc[0]
            latest_factors = df[df['date'] == latest_date]
            
            # 检查数据新鲜度
            if (datetime.now() - pd.to_datetime(latest_date)).days > 3:
                return None
            
            result = {
                'date': latest_date,
                'factors': dict(zip(latest_factors['factor_name'], latest_factors['factor_value']))
            }
            
            return result
            
        except Exception as e:
            print(f"[DataAccessLayer] 读取因子失败: {e}")
            return None
    
    def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """获取股票基本信息"""
        if not self.conn:
            return None
        
        try:
            query = """
                SELECT symbol, name, market, industry, sector, 
                       market_cap, pe, pb, total_mv, circulating_mv,
                       roe, net_profit_growth, gross_margin, debt_ratio,
                       is_st, is_suspended, list_date, updated_at
                FROM stocks
                WHERE symbol = ?
            """
            df = pd.read_sql_query(query, self.conn, params=(symbol,))
            
            if df.empty:
                return None
            
            return df.iloc[0].to_dict()
            
        except Exception as e:
            print(f"[DataAccessLayer] 读取股票信息失败: {e}")
            return None
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None


# 全局实例
_dal_instance = None

def get_dal() -> DataAccessLayer:
    """获取全局数据访问层实例"""
    global _dal_instance
    if _dal_instance is None:
        _dal_instance = DataAccessLayer()
    return _dal_instance
```

#### Phase 2: 修改 akshare_bridge.py 使用本地数据

**修改**: `python/akshare_bridge.py`

在文件开头添加导入：
```python
from data_access_layer import get_dal
```

修改 `calculate_technical_indicators()`:
```python
def calculate_technical_indicators(symbol: str) -> dict:
    import pandas as pd
    import numpy as np
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    
    try:
        # 1. 优先从本地数据库读取因子
        dal = get_dal()
        factors = dal.get_factors(symbol, [
            'MA5', 'MA10', 'MA20', 'MA60',
            'MACD_macd_dif', 'MACD_macd_dea', 'MACD_macd_histogram',
            'RSI14', 'BOLL_bb_upper', 'BOLL_bb_middle', 'BOLL_bb_lower'
        ])
        
        if factors:
            # 使用本地因子数据
            f = factors['factors']
            klines = dal.get_klines(symbol, days=5)
            current_price = float(klines['close'].iloc[-1]) if klines is not None else 0.0
            
            # 生成信号
            signals = []
            ma5, ma10, ma20, ma60 = f.get('MA5'), f.get('MA10'), f.get('MA20'), f.get('MA60')
            if current_price > ma5 > ma20: signals.append("短期多头排列")
            elif current_price < ma5 < ma20: signals.append("短期空头排列")
            if ma60 and current_price > ma60: signals.append("站上60日均线")
            elif ma60 and current_price < ma60: signals.append("跌破60日均线")
            
            rsi = f.get('RSI14', 50)
            if rsi > 70: signals.append("RSI超买")
            elif rsi < 30: signals.append("RSI超卖")
            
            dif, dea = f.get('MACD_macd_dif', 0), f.get('MACD_macd_dea', 0)
            if dif > dea: signals.append("MACD金叉")
            else: signals.append("MACD死叉")
            
            return {
                "symbol": symbol,
                "current_price": _safe_float(current_price),
                "ma": {
                    "ma5": _safe_float(ma5),
                    "ma10": _safe_float(ma10),
                    "ma20": _safe_float(ma20),
                    "ma60": _safe_float(ma60)
                },
                "macd": {
                    "dif": _safe_float(dif),
                    "dea": _safe_float(dea),
                    "histogram": _safe_float(f.get('MACD_macd_histogram', 0))
                },
                "rsi_14": _safe_float(rsi),
                "bollinger": {
                    "upper": _safe_float(f.get('BOLL_bb_upper')),
                    "mid": _safe_float(f.get('BOLL_bb_middle')),
                    "lower": _safe_float(f.get('BOLL_bb_lower'))
                },
                "signals": signals,
                "data_date": factors['date'],
                "data_source": "local_db"  # 标记数据来源
            }
        
        # 2. 降级：从API获取（原有逻辑）
        print(f"[calculate_technical_indicators] 本地数据不可用，使用API: {symbol}")
        raw = _sina_stock_history(symbol, datalen=90, scale=240)
        if not raw or len(raw) < 30:
            return {"error": "历史数据不足"}
        
        # ... 原有计算逻辑 ...
        # (保持不变，但在返回时添加 "data_source": "api")
        
    except Exception as e:
        return {"error": str(e), "symbol": symbol}
```

修改 `calculate_buy_range()`:
```python
def calculate_buy_range(symbol: str, current_price: float = None) -> dict:
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    
    try:
        # 1. 优先从本地数据库读取
        dal = get_dal()
        klines = dal.get_klines(symbol, days=90)
        
        if klines is not None and len(klines) >= 30:
            # 使用本地K线数据
            df = klines
            close = df["close"].astype(float)
            low_col = df["low"].astype(float)
            
            if current_price is None:
                current_price = _safe_float(close.iloc[-1])
            
            # 从本地因子读取MA值（更快）
            factors = dal.get_factors(symbol, ['MA20', 'MA60', 'BOLL_bb_lower'])
            if factors:
                ma20 = _safe_float(factors['factors'].get('MA20'))
                ma60 = _safe_float(factors['factors'].get('MA60', ma20 * 0.95))
                bb_lower = _safe_float(factors['factors'].get('BOLL_bb_lower'))
            else:
                # 降级：自己计算
                ma20 = _safe_float(close.rolling(20).mean().iloc[-1])
                ma60 = _safe_float(close.rolling(60).mean().iloc[-1]) if len(df) >= 60 else ma20 * 0.95
                bb_lower = _safe_float((close.rolling(20).mean() - 2 * close.rolling(20).std()).iloc[-1])
            
            recent_low = _safe_float(low_col.tail(20).min())
            
            # ... 后续计算逻辑保持不变 ...
            # 在返回时添加 "data_source": "local_db"
            
        else:
            # 2. 降级：从API获取
            print(f"[calculate_buy_range] 本地数据不可用，使用API: {symbol}")
            raw = _sina_stock_history(symbol, datalen=90, scale=240)
            # ... 原有逻辑 ...
            
    except Exception as e:
        return {"error": str(e), "symbol": symbol}
```

#### Phase 3: 性能优化

**缓存策略**:
```python
# 在 data_access_layer.py 中添加
from functools import lru_cache
from datetime import date

@lru_cache(maxsize=128)
def _get_klines_cached(symbol: str, days: int, cache_date: date):
    """带日期的缓存，每天自动失效"""
    dal = get_dal()
    return dal.get_klines(symbol, days)

def get_klines_cached(symbol: str, days: int = 90):
    """使用今天日期作为缓存key"""
    return _get_klines_cached(symbol, days, date.today())
```

#### Phase 4: 监控和日志

添加数据源统计：
```python
# 在 akshare_bridge.py 中添加
_data_source_stats = {"local_db": 0, "api": 0}

def log_data_source(source: str):
    _data_source_stats[source] += 1

def get_data_source_stats():
    total = sum(_data_source_stats.values())
    if total == 0:
        return {"local_db_ratio": 0, "api_ratio": 0}
    return {
        "local_db_ratio": _data_source_stats["local_db"] / total,
        "api_ratio": _data_source_stats["api"] / total,
        "total_calls": total
    }
```

## 预期效果

### 性能提升
- **速度**: 从网络请求(1-3秒) → 数据库查询(10-50ms)，提升 **20-100倍**
- **稳定性**: 不受网络波动影响
- **一致性**: AI使用的因子与定时任务计算的因子完全一致

### 数据利用率
- **Before**: 本地35MB数据完全闲置，每次都重新获取
- **After**: 本地数据命中率预计 **>90%**（只有新股或数据过期才调API）

### 资源节省
- **网络请求**: 减少90%+
- **计算资源**: 不再重复计算已有因子
- **API配额**: 节省大量akshare/sina API调用

## 实施计划

### Week 1: 基础设施
- [ ] 创建 `data_access_layer.py`
- [ ] 单元测试数据访问层
- [ ] 集成到 `akshare_bridge.py`

### Week 2: 工具迁移
- [ ] 迁移 `calculate_technical_indicators`
- [ ] 迁移 `calculate_buy_range`
- [ ] 迁移 `analyze_price_action`
- [ ] 迁移其他分析工具

### Week 3: 优化和监控
- [ ] 添加缓存层
- [ ] 添加数据源统计
- [ ] 性能基准测试
- [ ] 文档更新

## 风险和缓解

### 风险1: 数据新鲜度
- **问题**: 本地数据可能不是最新的
- **缓解**: 
  - 检查数据时间戳，超过3天自动降级到API
  - 定时任务确保每天更新
  - 实时价格仍从API获取

### 风险2: 数据库锁
- **问题**: 读写并发可能导致锁
- **缓解**:
  - 使用只读连接
  - 设置合理的timeout
  - 考虑使用WAL模式

### 风险3: 数据不完整
- **问题**: 新股或特殊情况下本地数据缺失
- **缓解**:
  - 完善的降级机制
  - 返回数据时标记来源
  - 监控API调用比例

## 后续优化

1. **增量更新**: 只更新变化的数据
2. **分布式缓存**: 使用Redis缓存热点数据
3. **数据预热**: 启动时预加载常用股票数据
4. **智能降级**: 根据数据质量自动选择数据源
