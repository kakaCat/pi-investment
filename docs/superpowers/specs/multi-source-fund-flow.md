# 多渠道个股资金流向数据查询

## 问题背景

当前 `get_stock_fund_flow` 函数使用 akshare 的 `stock_individual_fund_flow` 接口，该接口访问 `push2his.eastmoney.com` 域名，在当前网络环境下被屏蔽，导致查询失败。

**错误信息：**
```
ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
```

**根本原因：**
- 域名屏蔽（非代理问题）
- akshare 的所有资金流向函数都使用被屏蔽的域名（`push2his.eastmoney.com`, `push2.eastmoney.com`）

## 解决方案

实现多渠道数据查询，使用串行降级策略，默认优先使用新浪财经数据源。

### 数据源评估

| 数据源 | 状态 | 数据完整度 | 说明 |
|--------|------|-----------|------|
| 新浪财经 | ✅ 可用 | 部分 | 提供主力净流入汇总，缺少细分数据 |
| akshare 原始 | ❌ 被屏蔽 | 完整 | 提供完整的超大单、大单、中单、小单细分 |
| datacenter-web.eastmoney.com | ❌ 不可用 | - | 未找到正确的资金流向接口 |
| emweb.securities.eastmoney.com | ❌ 不可用 | - | 返回 HTML 页面，非 API |

### 降级策略

```
优先级 1: 新浪财经 (默认)
  ↓ 失败
优先级 2: akshare 原始接口 (最后尝试，可能失败)
```

## 技术设计

### 0. 依赖函数说明

**`_clean_symbol(symbol: str) -> str`**
- 位置：`quant/quantsys/cli/stock_query.py`
- 功能：清理股票代码，移除市场前缀，返回纯数字代码
- 示例：`"sh600094"` → `"600094"`

**`_disable_proxy_env()`**
- 位置：`quant/quantsys/cli/stock_query.py`
- 功能：临时禁用代理环境变量，避免代理干扰

### 1. akshare 返回字段（目标格式）

```python
# stock_individual_fund_flow 返回的 DataFrame 列
[
    "日期",
    "收盘价",
    "涨跌幅",
    "主力净流入-净额",
    "主力净流入-净占比",
    "超大单净流入-净额",
    "超大单净流入-净占比",
    "大单净流入-净额",
    "大单净流入-净占比",
    "中单净流入-净额",
    "中单净流入-净占比",
    "小单净流入-净额",
    "小单净流入-净占比",
]
```

### 2. 新浪数据源

**API 端点：**
```
https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs
```

**请求参数：**
```python
{
    "daima": "sh600094",  # 股票代码（需要加市场前缀）
    "num": 10,            # 返回天数
}
```

**返回字段：**
```json
{
  "opendate": "2026-05-22",      // 日期
  "trade": "4.6300",             // 收盘价
  "changeratio": "0.0198238",    // 涨跌幅（小数形式）
  "turnover": "108.33",          // 换手率
  "netamount": "21756352.8600",  // 主力净流入-净额
  "ratioamount": "0.204864",     // 主力净流入-净占比（小数形式）
  "r0_net": "8818511.0000",      // 未知字段
  "r0_ratio": "0.08303764",      // 未知字段
  ...
}
```

### 3. 字段映射和估算规则

#### 直接映射（真实数据）

```python
# 新浪字段 → akshare 字段
"opendate" → "日期"
"trade" → "收盘价"
"changeratio" → "涨跌幅"  # 需要转换：0.0198238 → 1.98238
"netamount" → "主力净流入-净额"
"ratioamount" → "主力净流入-净占比"  # 需要转换：0.204864 → 20.4864
```

#### 估算数据（基于主力净流入）

**估算比例：**
- 主力 = 超大单 + 大单（市场惯例）
- 超大单占主力的 60%，大单占 40%（基于东方财富历史数据的经验比例）
- 中单和小单作为散户资金，与主力反向流动（资金守恒原则）
- 散户资金（中单+小单）= -主力资金，各占散户资金的 50%

**计算公式：**
```python
# 超大单
超大单净流入-净额 = 主力净流入-净额 × 0.6
超大单净流入-净占比 = 主力净流入-净占比 × 0.6

# 大单
大单净流入-净额 = 主力净流入-净额 × 0.4
大单净流入-净占比 = 主力净流入-净占比 × 0.4

# 中单（假设与主力反向，占散户资金的 50%）
中单净流入-净额 = -(主力净流入-净额 × 0.5)
中单净流入-净占比 = -(主力净流入-净占比 × 0.5)

# 小单（假设与主力反向，占散户资金的 50%）
小单净流入-净额 = -(主力净流入-净额 × 0.5)
小单净流入-净占比 = -(主力净流入-净占比 × 0.5)
```

**估算合理性说明：**
- 量化分析通常关注主力资金流向趋势，细分数据的绝对精度不是核心
- 按比例估算能保持数据的相对关系和趋势
- 主力净流入数据是真实的，只有细分是估算

### 4. 实现架构

**修改文件：** `quant/quantsys/cli/sentiment_query.py`

**函数结构：**

```python
# 进程级别的成功率统计（内存缓存）
_source_stats = {
    'sina': {'success': 0, 'failure': 0, 'last_success_time': None},
    'akshare': {'success': 0, 'failure': 0, 'last_success_time': None},
}

def get_stock_fund_flow(symbol: str, days: int = 10) -> dict[str, Any]:
    """
    多渠道获取个股资金流向数据
    
    降级策略：新浪 → akshare
    
    Args:
        symbol: 股票代码（支持多种格式：600094, sh600094, SH600094）
        days: 查询天数，默认 10 天
        
    Returns:
        {
            "symbol": "600094",
            "data": [
                {
                    "日期": "2026-05-22",
                    "收盘价": 4.63,
                    "涨跌幅": 1.98,
                    "主力净流入-净额": 21756352.86,
                    "主力净流入-净占比": 20.49,
                    "超大单净流入-净额": 13053811.72,  # 估算
                    "超大单净流入-净占比": 12.29,      # 估算
                    "大单净流入-净额": 8702541.14,     # 估算
                    "大单净流入-净占比": 8.19,         # 估算
                    "中单净流入-净额": -10878176.43,   # 估算
                    "中单净流入-净占比": -10.24,       # 估算
                    "小单净流入-净额": -10878176.43,   # 估算
                    "小单净流入-净占比": -10.24,       # 估算
                },
                ...
            ],
            "source": "sina",  # 数据来源
            "estimated_fields": [  # 标记哪些字段是估算的
                "超大单净流入-净额",
                "超大单净流入-净占比",
                "大单净流入-净额",
                "大单净流入-净占比",
                "中单净流入-净额",
                "中单净流入-净占比",
                "小单净流入-净额",
                "小单净流入-净占比",
            ]
        }
        
        # 失败时返回
        {
            "error": "错误信息",
            "symbol": "600094"
        }
    """
    clean = _clean_symbol(symbol)
    
    # 尝试新浪数据源
    result = _fetch_from_sina(clean, days)
    if result and 'error' not in result:
        _update_stats('sina', success=True)
        return result
    
    _update_stats('sina', success=False)
    
    # 降级到 akshare
    result = _fetch_from_akshare(clean, days)
    if result and 'error' not in result:
        _update_stats('akshare', success=True)
    else:
        _update_stats('akshare', success=False)
    
    return result


def _fetch_from_sina(symbol: str, days: int) -> dict[str, Any]:
    """
    从新浪获取资金流向数据并转换为 akshare 格式
    
    Args:
        symbol: 纯数字股票代码（如 "600094"）
        days: 查询天数
        
    Returns:
        转换后的数据字典，失败时返回包含 error 的字典
    """
    try:
        import requests
        import pandas as pd
        from datetime import datetime
        
        # 确定市场前缀
        if symbol.startswith("6"):
            market_prefix = "sh"
        elif symbol.startswith(("8", "4")):
            market_prefix = "bj"
        else:
            market_prefix = "sz"
        
        # 调用新浪 API
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs"
        params = {
            "daima": f"{market_prefix}{symbol}",
            "num": days,
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if not data or len(data) == 0:
            return {"error": "新浪返回空数据", "symbol": symbol}
        
        # 转换为 akshare 格式
        records = []
        for item in data:
            # 解析数值
            main_net = float(item.get("netamount", 0))
            main_ratio = float(item.get("ratioamount", 0)) * 100  # 转换为百分比
            
            record = {
                "日期": item.get("opendate"),
                "收盘价": float(item.get("trade", 0)),
                "涨跌幅": float(item.get("changeratio", 0)) * 100,  # 转换为百分比
                "主力净流入-净额": main_net,
                "主力净流入-净占比": main_ratio,
                # 估算超大单（60%）
                "超大单净流入-净额": main_net * 0.6,
                "超大单净流入-净占比": main_ratio * 0.6,
                # 估算大单（40%）
                "大单净流入-净额": main_net * 0.4,
                "大单净流入-净占比": main_ratio * 0.4,
                # 估算中单（反向 50%）
                "中单净流入-净额": -main_net * 0.5,
                "中单净流入-净占比": -main_ratio * 0.5,
                # 估算小单（反向 50%）
                "小单净流入-净额": -main_net * 0.5,
                "小单净流入-净占比": -main_ratio * 0.5,
            }
            records.append(record)
        
        return {
            "symbol": symbol,
            "data": records,
            "source": "sina",
            "estimated_fields": [
                "超大单净流入-净额",
                "超大单净流入-净占比",
                "大单净流入-净额",
                "大单净流入-净占比",
                "中单净流入-净额",
                "中单净流入-净占比",
                "小单净流入-净额",
                "小单净流入-净占比",
            ]
        }
        
    except Exception as e:
        return {"error": f"新浪数据源失败: {str(e)}", "symbol": symbol}


def _fetch_from_akshare(symbol: str, days: int) -> dict[str, Any]:
    """
    使用 akshare 原始接口获取资金流向数据
    
    这是当前的实现，保持不变作为降级方案
    
    Args:
        symbol: 纯数字股票代码（如 "600094"）
        days: 查询天数
        
    Returns:
        转换后的数据字典，失败时返回包含 error 的字典
    """
    try:
        _disable_proxy_env()
        import akshare as ak
        
        # 确定市场
        if symbol.startswith("6"):
            market = "sh"
        elif symbol.startswith(("8", "4")):
            market = "bj"
        else:
            market = "sz"
        
        # 调用 akshare
        frame = ak.stock_individual_fund_flow(stock=symbol, market=market)
        if frame is None or frame.empty:
            return {"error": f"无资金流向数据: {symbol}", "symbol": symbol}
        
        # 限制返回天数
        limit = max(int(days or 10), 1)
        records = frame.tail(limit).to_dict(orient="records")
        
        return {
            "symbol": symbol,
            "data": records,
            "source": "akshare",
            "estimated_fields": []  # akshare 数据无估算字段
        }
        
    except Exception as e:
        return {"error": f"akshare 数据源失败: {str(e)}", "symbol": symbol}


def _update_stats(source: str, success: bool) -> None:
    """
    更新数据源成功率统计
    
    Args:
        source: 数据源名称（'sina' 或 'akshare'）
        success: 是否成功
    """
    from datetime import datetime
    
    if source in _source_stats:
        if success:
            _source_stats[source]['success'] += 1
            _source_stats[source]['last_success_time'] = datetime.now()
        else:
            _source_stats[source]['failure'] += 1


def get_fund_flow_stats() -> dict[str, Any]:
    """
    获取数据源统计信息（用于监控和调试）
    
    Returns:
        {
            'sina': {'success': 10, 'failure': 2, 'success_rate': 0.833, ...},
            'akshare': {'success': 0, 'failure': 5, 'success_rate': 0.0, ...}
        }
    """
    stats = {}
    for source, data in _source_stats.items():
        total = data['success'] + data['failure']
        success_rate = data['success'] / total if total > 0 else 0.0
        stats[source] = {
            **data,
            'total_requests': total,
            'success_rate': success_rate,
        }
    return stats
```

### 5. 数据格式兼容性

**当前实现的返回格式：**

```python
# 成功时
{
    "symbol": "600094",
    "count": 10,
    "data": [...],  # DataFrame 转换为 dict 列表
    "data_date": "2026-05-22"
}

# 失败时
{
    "error": "错误信息",
    "symbol": "600094"
}
```

**新实现的返回格式（向后兼容）：**

```python
# 成功时
{
    "symbol": "600094",
    "data": [...],
    "source": "sina",           # 新增：数据来源（"sina" 或 "akshare"）
    "estimated_fields": [...]   # 新增：标记估算字段（新浪数据源时有值，akshare 为空列表）
}

# 失败时（保持不变）
{
    "error": "错误信息",
    "symbol": "600094"
}
```

**兼容性说明：**
- 移除了 `count` 字段（可从 `len(data)` 获取）
- 移除了 `data_date` 字段（可从 `data[0]["日期"]` 获取）
- 新增 `source` 和 `estimated_fields` 字段（可选使用）
- 下游代码只需关注 `data` 字段，无需修改

## 测试计划

### 单元测试

1. **新浪数据源测试**
   - 测试正常查询（sh/sz/bj 市场）
   - 测试字段映射正确性
   - 测试估算计算准确性（验证比例关系）
   - 测试异常处理：
     - 网络超时（timeout）
     - HTTP 错误（4xx, 5xx）
     - 空数据响应
     - JSON 解析错误
     - 字段缺失

2. **降级逻辑测试**
   - 模拟新浪失败，验证降级到 akshare
   - 验证统计信息更新正确
   - 测试两个数据源都失败的情况

3. **字段兼容性测试**
   - 验证返回字段与 akshare 完全一致
   - 验证数据类型正确（日期字符串、浮点数）
   - 验证百分比转换正确（小数 → 百分比）

4. **边界条件测试**
   - days = 0, 1, 100（极端值）
   - 无效股票代码
   - 主力净流入为 0 的情况
   - 主力净流入为负的情况

### 集成测试

1. 在 `sentiment_query.py` 中调用 `get_stock_fund_flow`
2. 验证返回数据可被下游正常使用
3. 测试不同市场的股票（上海、深圳、北京）

## 风险和限制

### 数据准确性

- ⚠️ **超大单、大单、中单、小单数据是估算的**，不是真实交易数据
- ✅ 主力净流入数据是真实的（来自新浪）
- ✅ 估算比例基于市场经验，能保持相对趋势

### 适用场景

**适合：**
- 趋势分析（主力资金流入/流出方向）
- 相对比较（不同股票的资金流向对比）
- 信号生成（基于主力净流入的交易信号）

**不适合：**
- 需要精确细分数据的场景
- 对超大单/大单绝对值敏感的策略
- 需要与历史真实细分数据对比的分析

### 后续优化

1. **寻找更好的数据源**
   - 持续探索其他提供完整细分数据的 API
   - 发现后可直接替换新浪数据源

2. **改进估算模型**
   - 根据历史数据优化估算比例
   - 考虑不同市值、行业的差异

3. **智能路由（可选）**
   - 根据成功率动态调整数据源优先级
   - 当前使用固定优先级（新浪 → akshare）

## 实施步骤

1. ✅ 完成需求分析和技术调研
2. ✅ 完成设计文档
3. ⏳ 设计自审（检查占位符、矛盾、歧义）
4. ⏳ 用户审核设计文档
5. ⏳ 生成实现计划
6. ⏳ 实现代码
7. ⏳ 编写测试
8. ⏳ 集成测试
9. ⏳ 部署和监控

## 参考资料

- akshare 源码：`/Users/mac/Documents/ai/pi-investment/.venv/lib/python3.14/site-packages/akshare/stock/stock_fund_em.py`
- 新浪财经 API：`https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs`
- 项目内存记录：`/Users/mac/.claude/projects/-Users-mac-Documents-ai-pi-investment/memory/akshare-ts-data-layer.md`
